export const MAX_AD_VIDEO_BYTES = 500 * 1024 * 1024;
export const VIDEO_EXTENSIONS = /\.(mp4|webm|ogg|ogv|m4v|mov)$/i;
export function videoEnabled(value) { return value == null || value === true || value === 1 || value === '1'; }
export function normalizeVideoPlaylist(rows, legacy = '') {
  const configured = Array.isArray(rows) ? rows : [];
  const seen = new Set();
  const result = [];
  for (const row of configured) {
    const url = String(row.video || '').trim();
    if (!url || !videoEnabled(row.enabled) || seen.has(url)) continue;
    seen.add(url); result.push({url,title:String(row.title || '')});
  }
  // An explicitly configured all-disabled playlist must not resurrect the old ad.
  if (!configured.length && legacy) result.push({url:String(legacy).trim(),title:''});
  return result;
}
export function nextPlayableIndex(videos, current, failed = new Set()) {
  for (let step = 1; step <= videos.length; step++) {
    const index = (Math.max(current,-1) + step) % videos.length;
    if (!failed.has(videos[index].url)) return index;
  }
  return -1;
}
export function validateAdvertisingFile(file) {
  if (!VIDEO_EXTENSIONS.test(file.name || '')) throw new Error('Select an MP4, WebM, OGG, M4V or MOV video.');
  if (file.size > MAX_AD_VIDEO_BYTES) throw new Error('Each video must be 500 MB or smaller.');
  if (!(file.size > 0)) throw new Error('The video file is empty.');
}
