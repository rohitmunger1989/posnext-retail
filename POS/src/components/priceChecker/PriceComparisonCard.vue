<template>
  <article class="price-comparison-card" :class="String(theme).toLowerCase()==='dark' ? 'pc-dark' : 'pc-light'" aria-live="polite">
    <template v-if="data?.item">
      <header class="pc-heading">
        <div class="pc-heading-copy">
          <h2>{{ data.item.item_name || data.item.item_code }}</h2>
          <div class="pc-meta">
            <span v-if="data.store?.label">{{ __('Store') }}: {{ data.store.label }}</span>
            <span>{{ __('Item') }}: {{ data.item.item_code }}</span>
            <span v-if="data.item.barcode">{{ __('Barcode') }}: {{ data.item.barcode }}</span>
            <span v-if="data.item.brand">{{ __('Brand') }}: {{ data.item.brand }}</span>
            <span v-for="row in data.item.attributes || []" :key="row.attribute">{{ row.attribute }}: {{ row.value }}</span>
          </div>
        </div>
        <div class="pc-image-container">
          <img v-if="data.item.image && !imageFailed" :key="`${data.item.item_code}:${data.item.image}`" :src="data.item.image" :alt="data.item.item_name || data.item.item_code" @error="imageFailed=true" />
          <div v-else class="pc-image-empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"><path stroke-width="1.5" d="M4 4h16v16H4zM4 16l5-5 4 4 3-3 4 4M15 8h.01" /></svg><span>{{ __('Image not available') }}</span></div>
        </div>
      </header>
      <section class="pc-price-panel">
        <div class="pc-price-caption"><strong>{{ __('NOW') }} · {{ __('SELLING PRICE') }}</strong><span>{{ __('per') }} {{ data.item.uom }}</span></div>
        <div class="pc-current" :class="{'pc-unavailable':data.selling?.rate==null}">{{ money(data.selling?.rate, data.selling?.currency) }}</div>
        <div v-if="data.comparison" class="pc-before-label">{{ __('BEFORE') }} · {{ data.comparison.price_list }}</div>
        <div v-if="data.comparison" class="pc-reference">
          <span :class="{'pc-strike':!!data.offer}">{{ money(data.comparison.rate, data.comparison.currency) }}</span>
        </div>
        <div v-if="data.offer" class="pc-saving-badge">
          <template v-if="data.offer.savings != null">{{ __('SAVE') }} {{ money(data.offer.savings, data.offer.currency) }}</template>
          <span v-if="data.offer.savings != null && data.offer.discount_percentage != null" aria-hidden="true"> | </span>
          <template v-if="data.offer.discount_percentage != null">{{ percent(data.offer.discount_percentage) }} {{ __('OFF') }}</template>
        </div>
      </section>
      <div v-if="data.stock" class="pc-stock" :class="{'pc-stock-empty':data.stock.available_qty!=null && Number(data.stock.available_qty)<=0}">
        <template v-if="data.stock.available_qty!=null">{{ __('This Store Available Qty') }}: <strong>{{ quantity(data.stock.available_qty) }}</strong> <small>{{ data.stock.uom }}</small></template>
        <template v-else>{{ data.stock.tracked ? __('Stock unavailable') : __('Stock not tracked') }}</template>
      </div>
      <p class="pc-footnote">{{ __('Price-list prices for 1') }} {{ data.item.uom }}. {{ __('Customer, coupon and cart discounts are not included.') }}</p>
    </template>
    <div v-else class="pc-waiting"><div class="pc-waiting-icon">⌕</div><h2>{{ __('Price Checker') }}</h2><p>{{ __('Scan or select an item to see its price') }}</p></div>
  </article>
</template>
<script setup>
import {ref,watch} from 'vue';
const props=defineProps({data:{type:Object,default:null},theme:{type:String,default:'Light'}});
const imageFailed=ref(false);
watch(()=>[props.data?.item?.item_code,props.data?.item?.image],()=>{imageFailed.value=false;});
function money(value,currency){
  if(value===null||value===undefined||!Number.isFinite(Number(value)))return __('Price unavailable');
  if(!currency)return Number(value).toLocaleString(undefined,{maximumFractionDigits:3});
  try{return new Intl.NumberFormat(undefined,{style:'currency',currency,currencyDisplay:'code'}).format(Number(value));}
  catch(_){return `${currency} ${Number(value).toFixed(3)}`;}
}
function percent(value){const n=Number(value);return n>0&&n<0.01 ? '<0.01%' : `${new Intl.NumberFormat(undefined,{maximumFractionDigits:2}).format(n)}%`;}
function quantity(value){return new Intl.NumberFormat(undefined,{maximumFractionDigits:3}).format(Number(value));}
</script>
<style scoped>
.price-comparison-card{--pc-bg:#eef3f9;--pc-text:#152238;--pc-muted:#53657d;--pc-chip:#dfe7f2;--pc-border:#d5deeb;background:var(--pc-bg);color:var(--pc-text);border:1px solid var(--pc-border);border-radius:26px;padding:clamp(16px,2vw,24px);width:100%;max-width:1400px;margin:auto;box-sizing:border-box;box-shadow:0 16px 50px #12243a15}
.pc-dark{--pc-bg:#243244;--pc-text:#f8fafc;--pc-muted:#c3cfdf;--pc-chip:#465468;--pc-border:#405168;box-shadow:0 18px 60px #0003}
.pc-heading{display:flex;gap:20px;align-items:center;justify-content:space-between;margin-bottom:14px}.pc-heading-copy{min-width:0;flex:1}.pc-heading h2{font-size:clamp(24px,3vw,36px);line-height:1.15;font-weight:900;margin:0 0 10px;overflow-wrap:anywhere;letter-spacing:-.02em}.pc-image-container{width:clamp(90px,12vw,150px);height:clamp(90px,12vw,150px);flex-shrink:0;background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:8px;box-sizing:border-box;overflow:hidden}.pc-heading img{width:100%;height:100%;object-fit:contain}.pc-image-empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;color:#64748b;text-align:center;font-size:11px}.pc-image-empty svg{width:38px;height:38px}.pc-meta{display:flex;gap:8px;flex-wrap:wrap}.pc-meta>span{background:var(--pc-chip);color:var(--pc-text);font-size:clamp(11px,1.1vw,13px);font-weight:750;border-radius:999px;padding:6px 11px;overflow-wrap:anywhere;max-width:100%;box-sizing:border-box}
.pc-price-panel{background:#fafcfe;color:#12532d;border-radius:24px;padding:clamp(16px,2vw,24px);border:1px solid #e2e8f0}.pc-price-caption{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.pc-price-caption strong{color:#087936;font-size:clamp(15px,1.7vw,19px);font-weight:900}.pc-price-caption>span{color:#53657d;font-size:13px}.pc-current{font-size:clamp(36px,6vw,72px);font-weight:950;line-height:1.1;letter-spacing:-.035em;color:#087936;margin:10px 0 14px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.pc-current.pc-unavailable{font-size:clamp(24px,4vw,42px);color:#64748b}.pc-before-label{font-size:12px;font-weight:750;color:#64748b;margin:2px 0 6px;overflow-wrap:anywhere}.pc-reference{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;color:#707986;margin-bottom:18px;font-size:clamp(18px,2.4vw,28px);font-weight:800;line-height:1.2}.pc-reference small{font-size:12px;font-weight:500;color:#64748b}.pc-strike{text-decoration:line-through;text-decoration-thickness:2px}.pc-saving-badge{display:inline-flex;gap:7px;align-items:center;flex-wrap:wrap;background:#df1020;color:#fff;border-radius:999px;padding:12px 18px;font-size:clamp(15px,2vw,22px);font-weight:900;line-height:1.25;box-shadow:0 6px 18px #dc26261a;max-width:100%;box-sizing:border-box}.pc-stock{margin-top:20px;font-size:clamp(16px,1.9vw,22px);font-weight:800;line-height:1.4}.pc-stock strong{font-variant-numeric:tabular-nums}.pc-stock small{font-size:.6em;font-weight:600;color:var(--pc-muted)}.pc-stock-empty strong{color:#c62828}.pc-dark .pc-stock-empty strong{color:#fda4af}.pc-footnote{font-size:11px;line-height:1.5;margin:14px 0 0;color:var(--pc-muted)}.pc-waiting{text-align:center;padding:45px 10px}.pc-waiting h2{font-size:30px;font-weight:850}.pc-waiting p{color:var(--pc-muted);margin-top:10px}.pc-waiting-icon{font-size:60px;color:#818cf8}
@media(max-width:480px){.price-comparison-card{padding:16px;border-radius:18px}.pc-heading{gap:10px;margin-bottom:16px}.pc-heading h2{font-size:26px}.pc-meta{gap:5px}.pc-meta>span{padding:6px 9px;font-size:11px}.pc-price-panel{padding:18px;border-radius:18px}.pc-current{font-size:clamp(35px,10vw,48px)}.pc-saving-badge{padding:12px 14px;border-radius:18px;font-size:16px}.pc-image-container{width:90px;height:110px}}
@media(max-height:850px){.price-comparison-card{padding:16px;border-radius:18px}.pc-heading{gap:14px;margin-bottom:12px}.pc-heading h2{font-size:clamp(24px,3.2vw,36px);margin-bottom:10px}.pc-image-container{width:104px;height:112px}.pc-meta{gap:6px}.pc-meta>span{padding:6px 10px;font-size:12px}.pc-price-panel{padding:16px 20px;border-radius:18px}.pc-price-caption strong{font-size:18px}.pc-current{font-size:clamp(34px,5.8vw,60px);margin:6px 0 10px}.pc-reference{font-size:24px;margin-bottom:12px}.pc-saving-badge{padding:10px 16px;font-size:20px}.pc-stock{margin-top:12px;font-size:21px}.pc-footnote{margin-top:10px;font-size:10px}}
@media(max-height:600px){.price-comparison-card{padding:12px}.pc-heading{margin-bottom:10px}.pc-heading h2{font-size:clamp(22px,3vw,30px);margin-bottom:8px}.pc-image-container{width:84px;height:90px}.pc-meta>span{font-size:11px;padding:4px 8px}.pc-price-panel{padding:12px 16px}.pc-current{font-size:clamp(30px,5.2vw,50px);margin:4px 0 8px}.pc-reference{font-size:21px;margin-bottom:8px}.pc-saving-badge{font-size:17px;padding:8px 12px}.pc-stock{font-size:18px;margin-top:10px}.pc-footnote{font-size:10px;margin-top:8px}}
@media(max-width:380px){.pc-heading{flex-wrap:wrap}.pc-image-container{width:84px;height:90px}.pc-heading-copy{flex-basis:calc(100% - 100px)}.pc-current{font-size:clamp(30px,10vw,38px)}.pc-saving-badge{font-size:15px;padding:9px 11px}}
@media(prefers-reduced-motion:reduce){.price-comparison-card{scroll-behavior:auto}}
</style>
