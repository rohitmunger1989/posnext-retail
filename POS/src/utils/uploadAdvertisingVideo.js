import {validateAdvertisingFile} from './advertisingVideos';
export const AD_CHUNK_BYTES = 5 * 1024 * 1024;
export const AD_CHUNK_TIMEOUT_MS = 300000;
export function createAdvertisingUploadName(file) {
  const name=String(file.name || 'video.mp4').split(/[\\/]/).at(-1).replace(/[^a-zA-Z0-9._-]/g,'_');
  return `posnext-ad-${crypto.randomUUID().replaceAll('-','')}-${name.slice(-140)}`;
}
function error(message,status=0,kind='response') {const e=new Error(message);e.status=status;e.kind=kind;return e;}
export function sendAdvertisingChunk(part, options) {
 return new Promise((resolve,reject)=>{
  const xhr=new XMLHttpRequest(),body=new FormData();
  body.append('file',part,options.filename);body.append('is_private','0');body.append('folder','Home/Attachments');
  body.append('doctype','POS Settings');body.append('docname',options.docname);
  body.append('total_file_size',String(options.total));body.append('chunk_index',String(options.index));
  body.append('total_chunk_count',String(options.count));body.append('chunk_byte_offset',String(options.offset));
  xhr.open('POST','/api/method/upload_file');xhr.responseType='json';xhr.timeout=AD_CHUNK_TIMEOUT_MS;
  xhr.setRequestHeader('Accept','application/json');
  const csrf=options.csrfToken;if(csrf)xhr.setRequestHeader('X-Frappe-CSRF-Token',csrf);
  xhr.upload.onprogress=e=>{if(e.lengthComputable)options.onProgress?.(Math.min(e.loaded,part.size));};
  xhr.onload=()=>{options.onRequest?.(null);const data=xhr.response || {};
   if(xhr.status>=200&&xhr.status<300&&!data.exc&&!data.exception)resolve(data);
   else reject(error(xhr.status===413 ? 'A server/proxy rejected this 5 MB request. Check its upload limit.' : 'Video upload was rejected by the server.',xhr.status));
  };
  xhr.onerror=()=>{options.onRequest?.(null);reject(error('Connection lost during upload.',0,'network'));};
  xhr.ontimeout=()=>{options.onRequest?.(null);reject(error('Upload request timed out.',0,'timeout'));};
  xhr.onabort=()=>{options.onRequest?.(null);reject(error('Upload cancelled.',0,'abort'));};
  options.onRequest?.(xhr);
  if(options.cancelled?.()){xhr.abort();reject(error('Upload cancelled.',0,'abort'));return;}
  xhr.send(body);
 });
}
export async function uploadAdvertisingVideo(file, options) {
 validateAdvertisingFile(file);
 const request=options.request || sendAdvertisingChunk;
 const nameFactory=options.nameFactory || createAdvertisingUploadName;
 const chunkSize=options.chunkSize || AD_CHUNK_BYTES;
 const wait=options.wait || (ms=>new Promise(resolve=>setTimeout(resolve,ms)));
 const checkCancel=()=>{if(options.cancelled?.())throw error('Upload cancelled.',0,'abort');};
 const isSaved=doc=>doc?.file_url && Number(doc.file_size)===file.size;
 // Frappe's later chunks append: never retry a chunk at the same offset.
 // An ambiguous final response must be recovered, not blindly re-posted.
 for(let attempt=0;attempt<2;attempt++){
  checkCancel();const filename=nameFactory(file),count=Math.ceil(file.size/chunkSize);
  if(attempt)options.onStatus?.('Connection interrupted. Restarting this video safely with a new upload ID.');
  let restart=false;
  for(let index=0;index<count;index++){
   checkCancel();const offset=index*chunkSize,part=file.slice(offset,Math.min(file.size,offset+chunkSize),file.type);
   const final=index===count-1;
   try{
    const response=await request(part,{...options,filename,index,count,offset,total:file.size,
      onProgress:loaded=>options.onProgress?.(Math.min(99,Math.floor((offset+loaded)/file.size*100)))});
    checkCancel();
    if(!final)continue;
    const doc=response?.message || response;
    if(isSaved(doc)){options.onProgress?.(100);return doc.file_url;}
    throw error('Final upload response did not confirm the complete file.',0,'unconfirmed');
   }catch(exc){
    checkCancel();if(exc.kind==='abort')throw exc;
    const transient=['network','timeout','unconfirmed'].includes(exc.kind) || [408,502,503,504].includes(exc.status);
    if(!transient)throw exc;
    if(final){
      options.onStatus?.('Checking whether the completed video was saved...');
      for(let poll=0;poll<3;poll++){
       checkCancel();
       try{const found=await options.findSaved?.(filename,file.size);checkCancel();const doc=found?.message || found;if(isSaved(doc)){options.onProgress?.(100);return doc.file_url;}}catch(_){checkCancel();}
       if(poll<2)await wait(1500);
      }
      throw error('Upload result is unconfirmed. Check Select Existing Videos before retrying; the final chunk was not sent again.',0,'unconfirmed');
    }
    if(attempt===0){restart=true;break;}
    throw error('Connection interrupted again. Upload stopped; reconnect and try again.',0,'network');
   }
  }
  if(!restart)break;
 }
 throw error('Video upload did not finish.',0,'unconfirmed');
}
