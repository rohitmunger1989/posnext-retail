<template>
  <div class="advertising-video-player">
    <video v-if="currentVideo" ref="videoElement" :key="currentVideo.url" :src="currentVideo.url"
      autoplay muted playsinline preload="metadata" @ended="advance(false, $event)" @error="advance(true, $event)"
      class="advertising-video" aria-label="Promotional video"></video>
    <div v-else class="advertising-fallback"><slot /></div>
  </div>
</template>
<script setup>
import {computed, nextTick, ref, watch} from 'vue';
import {normalizeVideoPlaylist, nextPlayableIndex} from '@/utils/advertisingVideos';
const props = defineProps({videos:{type:Array,default:()=>[]},legacyVideo:{type:String,default:''}});
const playlist = computed(()=>normalizeVideoPlaylist(props.videos,props.legacyVideo));
const videoElement = ref(null), index = ref(0), failed = ref(new Set());
const currentVideo = computed(()=>index.value >= 0 ? playlist.value[index.value] : null);
let generation = 0;
watch(()=>JSON.stringify(playlist.value),()=>{generation++;failed.value=new Set();index.value=playlist.value.length ? 0 : -1;},{immediate:true});
async function advance(isError, event = null) {
  if (event?.target && event.target !== videoElement.value) return;
  const active = currentVideo.value;
  if (!active) return;
  const token = generation;
  if (isError) failed.value = new Set([...failed.value,active.url]);
  const previous = index.value;
  index.value = nextPlayableIndex(playlist.value,index.value,failed.value);
  await nextTick();
  // One remaining video can loop without changing its src/key.
  if (token === generation && index.value === previous && currentVideo.value && videoElement.value) {
    videoElement.value.currentTime=0;
    videoElement.value.play()?.catch(()=>{});
  }
}
</script>
<style scoped>
.advertising-video-player { width:100%; height:100%; min-width:0; min-height:0; background:#000; overflow:hidden; }
.advertising-video { display:block; width:100%; height:100%; object-fit:contain; object-position:center; }
.advertising-fallback { width:100%; height:100%; display:flex; align-items:center; justify-content:center; }
</style>
