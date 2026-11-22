<template>
  <div class="space-y-3">
    <p class="text-sm font-semibold">{{ __('Advertising Video Playlist') }}</p>
    <p class="text-xs text-gray-600">{{ __('Videos play in this order and repeat. Up to 500 MB per uploaded video, sent in small chunks. MP4 is recommended. 4:3 and 16:9 screens fit automatically without cropping.') }}</p>
    <p v-if="legacyVideo && !rows.length" class="text-xs text-gray-600">{{ __('Your existing single video remains active until you add playlist videos.') }} <button type="button" class="underline" @click="append([{video:legacyVideo,title:'Existing video',enabled:1}])">{{ __('Add it to playlist') }}</button></p>
    <div class="flex flex-wrap gap-2">
      <label class="rounded border px-3 py-2 text-xs cursor-pointer" :class="{'opacity-50':uploading}">{{ __('Upload Videos') }}
        <input type="file" multiple accept="video/mp4,video/webm,video/ogg,.mp4,.webm,.ogg,.ogv,.m4v,.mov" class="hidden" :disabled="uploading || !settingsName" @change="uploadSelected" />
      </label>
      <button type="button" class="rounded border px-3 py-2 text-xs" :disabled="uploading" @click="openPicker">{{ __('Select Existing Videos') }}</button>
      <button v-if="uploading" type="button" class="rounded border px-3 py-2 text-xs" @click="cancelUploads">{{ __('Cancel Upload') }}</button>
    </div>
    <p v-if="!settingsName" class="text-xs text-amber-700">{{ __('Save POS Settings once before uploading.') }}</p>
    <p v-if="progress" role="status" class="text-xs text-blue-700">{{ progress }}</p>
    <p v-if="error" role="alert" class="text-xs text-red-700">{{ error }}</p>
    <div v-if="pickerOpen" class="border rounded p-3 space-y-2">
      <p class="text-xs text-gray-600">{{ __('Select multiple videos from the latest 200 public video files.') }}</p>
      <p v-if="loadingFiles" class="text-xs">{{ __('Loading...') }}</p>
      <div class="max-h-48 overflow-auto space-y-2">
        <label v-for="file in availableFiles" :key="file.name" class="flex items-center gap-2 text-xs"><input v-model="chosen" type="checkbox" :value="file.file_url" /><span>{{ file.file_name }} · {{ (Number(file.file_size || 0)/1024/1024).toFixed(1) }} MB</span></label>
      </div>
      <p v-if="!loadingFiles && !availableFiles.length" class="text-xs">{{ __('No public videos found.') }}</p>
      <button type="button" class="rounded border px-3 py-2 text-xs" :disabled="!chosen.length" @click="addChosen">{{ __('Add Selected Videos') }}</button>
      <button type="button" class="px-3 py-2 text-xs" @click="pickerOpen=false">{{ __('Close') }}</button>
    </div>
    <ol class="space-y-2">
      <li v-for="(row,index) in rows" :key="row.name || row.video" class="border rounded p-2 space-y-2">
        <div class="flex items-center gap-2">
          <input type="checkbox" :checked="videoEnabled(row.enabled)" @change="edit(index,'enabled',$event.target.checked ? 1 : 0)" :aria-label="__('Enable video')" />
          <span class="text-xs">{{ index + 1 }}.</span>
          <input :value="row.title" class="border rounded p-1 text-xs min-w-0 flex-1" :placeholder="__('Video title')" @input="edit(index,'title',$event.target.value)" />
          <button type="button" class="text-xs px-1" :disabled="index===0" @click="move(index,-1)" :aria-label="__('Move up')">↑</button>
          <button type="button" class="text-xs px-1" :disabled="index===rows.length-1" @click="move(index,1)" :aria-label="__('Move down')">↓</button>
          <button type="button" class="text-xs text-red-700" @click="remove(index)">{{ __('Remove') }}</button>
        </div>
        <p class="text-xs break-all text-gray-500">{{ row.video }}</p>
      </li>
    </ol>
    <p class="text-xs text-gray-500">{{ __('Click Save Settings to apply playlist changes. Removing a row does not delete the uploaded file.') }}</p>
  </div>
</template>
<script setup>
import {computed, onUnmounted, ref, watch} from 'vue';
import {call} from 'frappe-ui';
import {validateAdvertisingFile, videoEnabled} from '@/utils/advertisingVideos';
import {uploadAdvertisingVideo} from '@/utils/uploadAdvertisingVideo';
const props=defineProps({modelValue:{type:Array,default:()=>[]},legacyVideo:{type:String,default:''},posProfile:String,settingsName:String});
const emit=defineEmits(['update:modelValue','uploading']);
const rows=computed(()=>Array.isArray(props.modelValue) ? props.modelValue : []);
const uploading=ref(false),progress=ref(''),error=ref(''),pickerOpen=ref(false),loadingFiles=ref(false),availableFiles=ref([]),chosen=ref([]);
let activeRequest=null,cancelled=false,generation=0;
function append(values) {
  const next=rows.value.map(r=>({...r})); const known=new Set(next.map(r=>r.video));
  for(const row of values)if(row.video && !known.has(row.video)){next.push({...row});known.add(row.video);}
  emit('update:modelValue',next);
}
function edit(index,field,value){emit('update:modelValue',rows.value.map((r,i)=>i===index ? {...r,[field]:value}:r));}
function move(index,delta){const next=rows.value.map(r=>({...r}));const other=index+delta;if(other<0||other>=next.length)return;[next[index],next[other]]=[next[other],next[index]];emit('update:modelValue',next);}
function remove(index){emit('update:modelValue',rows.value.filter((_,i)=>i!==index));}
async function openPicker(){
  pickerOpen.value=true;loadingFiles.value=true;error.value='';chosen.value=[];const token=generation;
  try{const data=await call('pos_next.customer_display_media.list_advertising_videos',{pos_profile:props.posProfile});if(token===generation)availableFiles.value=data?.message || data || [];}
  catch(exc){if(token===generation)error.value=exc?.messages?.[0] || exc.message || 'Could not load videos.';}
  finally{if(token===generation)loadingFiles.value=false;}
}
function addChosen(){append(availableFiles.value.filter(f=>chosen.value.includes(f.file_url)).map(f=>({video:f.file_url,title:f.file_name,enabled:1})));pickerOpen.value=false;}
function uploadOne(file,docname,onProgress){
 return uploadAdvertisingVideo(file,{
  docname,csrfToken:window.csrf_token || window.frappe?.csrf_token,
  cancelled:()=>cancelled,
  onRequest:xhr=>{activeRequest=xhr;},
  onProgress,
  onStatus:message=>{progress.value=message;},
  findSaved:(upload_filename,total_file_size)=>call('pos_next.customer_display_media.find_advertising_upload',{
    settings_name:docname,upload_filename,total_file_size,
  }),
 });
}
async function uploadSelected(event){
 const files=Array.from(event.target.files || []);event.target.value='';if(!files.length||uploading.value)return;
 error.value='';if(!props.settingsName){error.value='Save POS Settings first.';return;}
 try{files.forEach(validateAdvertisingFile);}catch(exc){error.value=exc.message;return;}
 const token=generation,docname=props.settingsName;cancelled=false;uploading.value=true;emit('uploading',true);
 try{for(let i=0;i<files.length;i++){
  if(cancelled||token!==generation)break;const file=files[i];
  const url=await uploadOne(file,docname,pct=>{if(token===generation)progress.value=`${i+1}/${files.length} · ${file.name} · ${pct}%`;});
  if(cancelled||token!==generation)break;append([{video:url,title:file.name,enabled:1}]);
  // Allow the v-model parent to apply each successful addition before the next one.
  await new Promise(resolve=>setTimeout(resolve,0));
 }
 if(!cancelled&&token===generation)progress.value='Uploads complete. Click Save Settings to apply the playlist.';
 }catch(exc){if(token===generation)error.value=exc.message;}
 finally{uploading.value=false;emit('uploading',false);}
}
function cancelUploads(){cancelled=true;activeRequest?.abort();}
watch(()=>[props.posProfile,props.settingsName],()=>{generation++;cancelUploads();pickerOpen.value=false;availableFiles.value=[];chosen.value=[];progress.value='';error.value='';});
onUnmounted(()=>{generation++;cancelUploads();emit('uploading',false);});
</script>
