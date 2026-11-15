<template>
  <Dialog v-model="show" :options="{ title: __('Add Float / Cash History'), size: '3xl' }">
    <template #body-content>
      <div class="space-y-4">
        <p class="text-sm text-gray-600">{{ __('Each addition is recorded separately. The original opening balance stays unchanged.') }}</p>
        <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
        <p v-if="notice" role="status" class="text-sm text-emerald-700">{{ notice }}</p>

        <p v-if="!online" class="text-sm text-amber-700">{{ __('Offline: use the same cash-drawer manager PIN. Cash entries are saved on this terminal and sync when reconnected.') }}</p>
        <p v-if="!online && !data.can_add && !readOnly" role="alert" class="text-sm text-red-700">{{ __("Offline manager access is not available on this terminal yet. Reconnect POSNext once to download it automatically.") }}</p>
        <div v-if="loading">{{ __('Loading...') }}</div>
        <form v-else-if="data.can_add && !readOnly" class="space-y-3" @submit.prevent="requestPin">
          <label class="block text-sm">{{ __('Cash Mode') }}
            <select v-model="mode" :disabled="busy || uncertain" class="w-full rounded border p-2" required>
              <option v-for="item in data.cash_modes" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>
          <label class="block text-sm">{{ __('Amount') }} ({{ data.currency }})
            <input v-model="amount" :disabled="busy || uncertain" type="number" min="0.001" step="0.001" required class="w-full rounded border p-2" />
          </label>
          <label class="block text-sm">{{ __('Reason') }}
            <input v-model="reason" :disabled="busy || uncertain" maxlength="500" required class="w-full rounded border p-2" />
          </label>

          <p class="text-xs text-gray-500">{{ __('Place the cash in the drawer after saving. The drawer opens automatically using this terminal setup.') }}</p>
          <button type="submit" :disabled="busy || !mode" class="float-primary-button">{{ busy ? __('Saving...') : uncertain ? __('Check / Retry Same Addition') : __('Save and Open Drawer') }}</button>
          <p v-if="uncertain" class="text-xs text-amber-700">{{ __('The response was not confirmed. Keep the same details and retry to avoid adding cash twice.') }}</p>
        </form>
        <div class="overflow-x-auto">
          <table class="w-full text-sm"><thead><tr class="text-left"><th>{{ __('Time') }}</th><th>{{ __('Amount') }}</th><th>{{ __('Reason') }}</th><th>{{ __('Cashier / Approver') }}</th></tr></thead>
            <tbody><tr v-for="row in data.rows" :key="row.name" class="border-t"><td class="p-2">{{ row.occurred_at || row.creation }}<div class="text-xs">{{ row.name }}</div></td><td class="p-2 whitespace-nowrap">{{ row.currency }} {{ Number(row.amount).toFixed(3) }}<div class="text-xs">{{ row.mode_of_payment }}</div></td><td class="p-2">{{ row.reason }}<div v-if="row.offline" class="text-xs text-amber-700">{{ row.sync_status || __('Synced from offline') }}</div><div v-if="row.sync_error" class="text-xs text-red-700">{{ row.sync_error }}</div></td><td class="p-2">{{ row.cashier }}<div class="text-xs">{{ row.authorized_by }}</div></td></tr></tbody>
          </table>
          <p v-if="!data.rows?.length" class="py-3 text-sm text-gray-500">{{ __('No float additions for this shift.') }}</p>
        </div>
        <button type="button" :disabled="busy" class="rounded border px-3 py-2" @click="load">{{ __('Refresh History') }}</button>
      </div>
    </template>
  </Dialog>
<Dialog v-model="showPin" :options="{ title: __('Manager Approval'), size: 'sm' }">
    <template #body-content>
      <form class="space-y-3" @submit.prevent="approve">
        <p class="text-sm">{{ __('Enter the same manager PIN used for Open Drawer to approve this cash addition.') }}</p>
        <label class="block text-sm">{{ __('Manager POS PIN') }}<input v-model="pin" type="password" inputmode="numeric" autocomplete="off" pattern="[0-9]{4,6}" required :disabled="busy" class="w-full rounded border p-2" /></label>
        <p v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</p>
        <button type="submit" :disabled="busy" class="float-primary-button">{{ busy ? __('Processing...') : __('Approve') }}</button>
      </form>
    </template>
  </Dialog>
</template>
<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { isOffline, offlineState } from '@/utils/offline/offlineState';
import { Dialog, call } from 'frappe-ui';
import { encryptManagerPin } from '@/utils/securePin';
import { getPendingFloatRequest, savePendingFloatRequest, clearPendingFloatRequest, ensureOfflineFloatDefaults, cacheFloatHistory, localFloatHistory, queueOfflineFloat, updateOfflineDrawer, syncFloatQueue } from '@/utils/offline/floatQueue';
const props = defineProps({ modelValue: Boolean, shift: String, readOnly: Boolean, openDrawer: Function, profile: String });
const emit = defineEmits(['update:modelValue']);
const busy = ref(false), loading = ref(false), error = ref(''), notice = ref('');
const data = ref({ rows: [], cash_modes: [], can_add: false });
const amount = ref(''), reason = ref(''), pin = ref(''), mode = ref('');
const key = ref(''), uncertain = ref(false), showPin = ref(false);
const online = ref(!isOffline());
let unsubscribeOffline;
onMounted(() => { unsubscribeOffline = offlineState.subscribe(() => { online.value = !isOffline(); if (show.value) load(); }); });
onBeforeUnmount(() => unsubscribeOffline?.());
const show = computed({get: () => props.modelValue, set: value => { if (!busy.value) emit('update:modelValue', value); }});
function newKey() { return crypto.randomUUID(); }
function message(exc) { return exc?.messages?.[0] || exc?.message || 'Request failed.'; }
async function load() {
  online.value = !isOffline();
  if (!props.shift || props.shift.startsWith('OFFLINE-')) {
    data.value = { rows: [], cash_modes: [], can_add: false }; error.value = 'Open this shift online once before adding float.'; return;
  }
  loading.value = true;
  try {
    const pending = await getPendingFloatRequest(props.shift);
    if (pending && !key.value) { key.value = pending.event_key; amount.value = pending.amount; reason.value = pending.reason; mode.value = pending.mode_of_payment; uncertain.value = true; }
    if (!isOffline()) {
      await syncFloatQueue(props.shift);
      try { await ensureOfflineFloatDefaults(props.shift, props.profile); } catch (exc) { console.warn("Automatic offline manager cache needs connection:", exc); }
      const result = await call('pos_next.api.float_additions.get_float_history', {pos_opening_shift: props.shift});
      const server = result?.message || result;
      await cacheFloatHistory(props.shift, server);
    }
    data.value = await localFloatHistory(props.shift, props.profile);
    // Online additions use live PIN verification even without a prepared grant.
    if (!isOffline()) {
      const result = await call('pos_next.api.float_additions.get_float_history', {pos_opening_shift: props.shift});
      const server = result?.message || result;
      data.value.can_add = server.can_add; data.value.cash_modes = server.cash_modes;
    }
    if (!data.value.cash_modes.includes(mode.value)) mode.value = data.value.cash_modes[0] || '';
  } catch (exc) { error.value = message(exc); } finally { loading.value = false; }
}
function requestPin() { pin.value = ''; error.value = ''; showPin.value = true; }
async function approve() {
  if (busy.value) return;
  await save();
}
async function save() {
  if (busy.value) return;
  busy.value = true; error.value = ''; notice.value = '';
  let saved;
  try {
    if (!key.value) key.value = newKey();
    await savePendingFloatRequest(props.shift, {event_key: key.value, amount: amount.value, reason: reason.value, mode_of_payment: mode.value});
    if (!isOffline()) {
      const context = {pos_opening_shift: props.shift, amount: amount.value, reason: reason.value,
        mode_of_payment: mode.value, event_key: key.value};
      const pin_approval = await encryptManagerPin('add_float', context, pin.value);
      const result = await call('pos_next.api.float_additions.add_float', {...context, pin_approval});
      saved = result?.message || result;
    } else {
      const row = await queueOfflineFloat({pos_opening_shift: props.shift, amount: amount.value,
        reason: reason.value, mode_of_payment: mode.value, event_key: key.value}, props.profile, pin.value);
      saved = {name: row.event_key, offline: true, drawer_status: row.drawer_status};
    }
    if (!saved?.name) throw new Error('No saved float reference returned.');
  } catch (exc) {
    // Unknown network outcomes retain the same ID and immutable form details.
    uncertain.value = !isOffline(); error.value = message(exc);
    // Validation rejections are known not to have saved a row.
    if (exc?.exc_type || (Array.isArray(exc?.messages) && exc.messages.length) || isOffline()) { uncertain.value = false; await clearPendingFloatRequest(props.shift); }
  } finally { pin.value = ''; }
  if (saved) {
    await clearPendingFloatRequest(props.shift);
    uncertain.value = false; key.value = ''; amount.value = ''; reason.value = ''; showPin.value = false;
    notice.value = (saved.offline ? 'Float saved offline — pending sync: ' : 'Float saved: ') + saved.name;
    try {
      if (!props.openDrawer) throw new Error('Drawer controls are unavailable. Use Open Drawer.');
      if (saved.offline) {
        if (saved.drawer_status !== 'Not requested') throw new Error('Drawer request was already issued. Use Open Drawer.');
        await updateOfflineDrawer(saved.name, 'Requested');
      }
      await props.openDrawer(saved.name, Boolean(saved.offline));
      if (saved.offline) await updateOfflineDrawer(saved.name, 'Opened');
      notice.value += '. Cash drawer opened.';
    } catch (exc) { if (saved.offline) await updateOfflineDrawer(saved.name, 'Failed', message(exc)); error.value = 'Float is saved. ' + message(exc) + ' Use Open Drawer; do not add the cash again.'; }
    await load();
  }
  busy.value = false;
}
watch(showPin, value => { if (!value) pin.value = ''; });
watch(() => [props.modelValue, props.shift], ([opened]) => { if (opened) { error.value = ''; notice.value = ''; pin.value = ''; load(); } });
</script>

<style scoped>
.float-primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 10px 18px;
  border: 1px solid #047857;
  border-radius: 8px;
  background: #047857;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.float-primary-button:hover:not(:disabled) { background: #065f46; }
.float-primary-button:focus-visible { outline: 3px solid #6ee7b7; outline-offset: 2px; }
.float-primary-button:disabled { background: #64748b; border-color: #64748b; color: #fff; cursor: not-allowed; }
</style>
