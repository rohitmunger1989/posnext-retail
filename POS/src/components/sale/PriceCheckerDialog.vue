<template>
  <dialog ref="modal" class="price-checker-modal" :class="{'pc-modal-dark':cardTheme==='Dark'}" aria-labelledby="price-checker-title" @cancel.prevent="show=false" @close="show=false" @click="closeOnBackdrop">
    <header class="price-checker-header"><h2 id="price-checker-title">{{ __('Price Checker') }}</h2><button type="button" :aria-label="__('Close price checker')" class="price-checker-x" @click="show=false">×</button></header>
    <div class="price-checker-body" @keydown.stop>
      <div class="price-checker-search">
        <form class="flex gap-2" @submit.prevent="onEnter">
          <label class="sr-only" for="price-check-query">{{ __('Barcode, item code or name') }}</label>
          <input id="price-check-query" ref="input" v-model="query" type="search" autocomplete="off" class="min-w-0 flex-1 rounded-xl border border-indigo-200 px-4 py-3 text-base focus:ring-2 focus:ring-indigo-500" :placeholder="__('Scan barcode or search item code / name')" @input="invalidate" @keydown.enter.prevent="onEnter" @keydown.down.prevent="moveMatch(1)" @keydown.up.prevent="moveMatch(-1)" role="combobox" :aria-expanded="matches.length>0" aria-controls="price-check-matches" :aria-activedescendant="matches.length ? `price-match-${activeMatch}` : undefined" />
          <button type="submit" class="rounded-xl bg-indigo-600 px-5 py-3 text-white font-semibold disabled:opacity-50" :disabled="!query.trim()">{{ __('Check Price') }}</button>
        </form>
      </div>
      <div class="price-checker-content" tabindex="0" :aria-label="__('Price checker results')">

        <p v-if="busy" role="status" class="text-sm text-indigo-700">{{ __('Checking prices...') }}</p>
        <p v-if="error" role="alert" class="rounded-xl bg-red-50 p-3 text-sm text-red-700">{{ error }}</p>
        <ul v-if="matches.length" id="price-check-matches" role="listbox" class="max-h-52 overflow-auto rounded-xl border divide-y">
          <li v-for="(item,index) in matches" :key="item.name" :id="`price-match-${index}`" role="option" :aria-selected="index===activeMatch" :class="{'bg-indigo-50':index===activeMatch}"><button type="button" class="w-full text-start px-4 py-3 hover:bg-indigo-50" @click="select(item)"><strong>{{ item.item_name }}</strong><span class="text-xs text-gray-500 block">{{ item.name }} · {{ item.stock_uom }}</span></button></li>
        </ul>
        <PriceComparisonCard :data="result" :theme="cardTheme" />

      </div>
    </div>
    <footer class="price-checker-footer"><button type="button" class="rounded-lg border px-4 py-2 text-sm text-gray-700" @click="show=false">{{ __('Close') }}</button></footer>
  </dialog>
</template>
<script setup>
import {computed,nextTick,onBeforeUnmount,ref,watch} from 'vue';
import {call} from '@/utils/apiWrapper';
import {parseError} from '@/utils/errorHandler';
import {useSystemTheme} from '@/composables/useSystemTheme';
import {useCustomerDisplayStore} from '@/stores/customerDisplay';
import PriceComparisonCard from '@/components/priceChecker/PriceComparisonCard.vue';
const props=defineProps({modelValue:Boolean,posProfile:String});
const emit=defineEmits(['update:modelValue']);
const show=computed({get:()=>props.modelValue,set:v=>emit('update:modelValue',v)});
const modal=ref(null);
const input=ref(null),query=ref(''),result=ref(null),matches=ref([]),error=ref(''),busy=ref(false);
const display=useCustomerDisplayStore(),owner=`price-check-${crypto.randomUUID()}`;
const cardTheme=useSystemTheme();
const activeMatch=ref(0);
let generation=0;
async function focus(){await nextTick();if(show.value){input.value?.focus();input.value?.select();}}
function invalidate(){activeMatch.value=0;generation++;busy.value=false;result.value=null;matches.value=[];error.value='';if(show.value)display.setPriceCheckPreview(owner,null);}
async function request(method,args){
 const token=++generation;busy.value=true;result.value=null;matches.value=[];error.value='';display.setPriceCheckPreview(owner,null);
 try{
  if(!navigator.onLine)throw new Error(__('Price checking requires an internet connection.'));
  const response=await call(`pos_next.api.price_checker.${method}`,{pos_profile:props.posProfile,...args});
  if(token!==generation||!show.value)return;
  const data=response?.message || response;
  if(data?.kind==='price'){result.value=data;display.setPriceCheckPreview(owner,data);}
  else{
   const rows=data?.items || [];
   if(rows.length===1){await request('get_price',{item_code:rows[0].name});return;}
   matches.value=rows;activeMatch.value=0;
   if(!rows.length)error.value=__('No matching sales item found.');
  }
 }catch(exc){if(token===generation&&show.value)error.value=parseError(exc).message;}
 finally{if(token===generation){busy.value=false;await focus();}}
}
function onEnter(){
 if(busy.value)return;
 if(matches.value.length)return select(matches.value[activeMatch.value] || matches.value[0]);
 return lookup();
}
function moveMatch(delta){if(matches.value.length)activeMatch.value=(activeMatch.value+delta+matches.value.length)%matches.value.length;}
function lookup(){if(query.value.trim())return request('lookup',{query:query.value.trim()});}
function select(item){return request('get_price',{item_code:item.name});}
watch(()=>props.modelValue,async open=>{
 generation++;query.value='';result.value=null;matches.value=[];error.value='';busy.value=false;
 if(open){
  await nextTick();
  if(!show.value)return;
  if(modal.value && !modal.value.open)modal.value.showModal();
  display.setPriceCheckPreview(owner,null);await focus();
 }else{
  if(modal.value?.open)modal.value.close();
  display.clearPriceCheckPreview(owner);
 }
});
watch(()=>props.posProfile,()=>{generation++;show.value=false;display.clearPriceCheckPreview(owner);});
function closeOnBackdrop(event){
 const el=modal.value;if(!el || event.target!==el)return;
 const r=el.getBoundingClientRect();
 if(event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom)show.value=false;
}
onBeforeUnmount(()=>{generation++;if(modal.value?.open)modal.value.close();display.clearPriceCheckPreview(owner);});
</script>

<style scoped>
.price-checker-modal{box-sizing:border-box;width:min(960px,calc(100vw - 24px));max-width:calc(100vw - 24px);max-height:calc(100vh - 24px);max-height:calc(100dvh - 24px);margin:auto;padding:0;border:1px solid #dbe3ee;border-radius:20px;background:#fff;color:#172033;box-shadow:0 24px 80px #0f172a40;overflow:hidden}
.price-checker-modal[open]{display:flex;flex-direction:column}
.price-checker-modal::backdrop{background:#0f172a66}
.price-checker-header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 22px 8px;flex-shrink:0}.price-checker-header h2{font-size:20px;font-weight:750;line-height:1.3;margin:0}.price-checker-x{border:0;background:transparent;font-size:27px;line-height:1;padding:6px 10px;border-radius:8px;color:inherit;cursor:pointer}.price-checker-x:hover{background:#f1f5f9}
.price-checker-body{display:flex;flex-direction:column;min-height:0;min-width:0;flex:1 1 auto;overflow:hidden}.price-checker-search{padding:12px 22px;flex-shrink:0;min-width:0}.price-checker-search form{margin:0;display:flex;gap:8px;min-width:0}.price-checker-search input{width:100%;box-sizing:border-box;flex:1;min-width:0;min-height:42px;border:1px solid #cbd5e1;border-radius:10px;padding:10px 14px;font-size:15px;line-height:1.35}.price-checker-search button[type=submit]{background:#4f46e5;color:#fff;border:1px solid #4f46e5;border-radius:10px;padding:10px 16px;cursor:pointer;font-weight:650;flex-shrink:0}.price-checker-search button:disabled{opacity:.5;cursor:default}.price-checker-content{padding:0 22px 4px;min-height:0;min-width:0;flex:1 1 auto;overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable}.price-checker-content:focus-visible{outline:2px solid #818cf8;outline-offset:-2px}.price-checker-content>p,.price-checker-content>ul{margin-top:0;margin-bottom:12px}.price-checker-footer{display:flex;justify-content:flex-end;align-items:center;padding:10px 22px 14px;flex-shrink:0}.price-checker-footer button{cursor:pointer;background:#f8fafc;border:1px solid #cbd5e1;border-radius:8px;color:#334155;padding:8px 16px;font-size:13px}
.price-checker-modal.pc-modal-dark{background:#172233;color:#f1f5f9;border-color:#405168}.pc-modal-dark .price-checker-x:hover{background:#334155}.pc-modal-dark .price-checker-search input{background:#243244;color:#f8fafc;border-color:#64748b}.pc-modal-dark .price-checker-footer button{background:#243244;color:#f1f5f9;border-color:#64748b}.pc-modal-dark [role=option][aria-selected=true],.pc-modal-dark [role=option] button:hover{background:#334155;color:#f1f5f9}.pc-modal-dark [role=option] .text-gray-500{color:#cbd5e1}.pc-modal-dark .price-checker-content>p[role=status]{color:#a5b4fc}
@media(max-width:600px){.price-checker-modal{width:calc(100vw - 12px);max-width:calc(100vw - 12px);max-height:calc(100dvh - 12px);border-radius:14px}.price-checker-header{padding:10px 12px 4px}.price-checker-header h2{font-size:18px}.price-checker-search{padding:8px 12px}.price-checker-search form{gap:6px}.price-checker-search button{padding:10px;font-size:12px;white-space:nowrap}.price-checker-search input{padding:10px;font-size:14px}.price-checker-content{padding:0 10px 2px}.price-checker-footer{padding:8px 12px 10px}}
@media(max-height:600px){.price-checker-header{padding-top:8px}.price-checker-search{padding-top:6px;padding-bottom:6px}.price-checker-search input{padding-top:8px;padding-bottom:8px}.price-checker-search button{padding-top:8px;padding-bottom:8px}.price-checker-footer{padding-top:6px;padding-bottom:8px}}
</style>
