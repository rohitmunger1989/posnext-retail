import { db } from './db';
import { isOffline } from './offlineState';
import { call } from 'frappe-ui';
import { OFFLINE_AUTH_PUBLIC_KEY } from './offlinePublicKey';
import { getSignedOfflineAuthorization } from './offlineAuthorization';
import { verifyOfflineAuthorization } from './verifyOfflineAuthorization';
import { loadCashDrawerTerminalSettings, getCashDrawerMethodLabel } from '../cashDrawerHardware';
const encoder = new TextEncoder();
function bytes(value) { return Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/')), c => c.charCodeAt(0)); }
function b64(value) { return btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); }
function payload(token) { return JSON.parse(new TextDecoder().decode(bytes(token.payload))); }
function unwrap(value) { return value?.message || value; }
async function user() {
  const token = getSignedOfflineAuthorization();
  const name = token ? payload(token).user : '';
  if (!await verifyOfflineAuthorization(token, name)) {
    if (!isOffline()) return unwrap(await call('frappe.auth.get_logged_user'));
    throw new Error('Reconnect to refresh cashier offline authorization.');
  }
  return name;
}
async function verifyGrant(grant, shift, terminal, cashier, allowExpired = false) {
  const key = await crypto.subtle.importKey('raw', bytes(OFFLINE_AUTH_PUBLIC_KEY), {name: 'Ed25519'}, false, ['verify']);
  if (!await crypto.subtle.verify('Ed25519', key, bytes(grant.signature), bytes(grant.payload))) throw new Error('Invalid manager offline approval.');
  const c = payload(grant), now = Math.floor(Date.now() / 1000);
  if (!['posnext_float_drawer_approval_v2', 'posnext_float_drawer_defaults_v3', 'posnext_cash_drawer_defaults_v4'].includes(c.purpose) || c.site !== location.hostname || c.user !== cashier || c.shift !== shift || c.terminal_id !== terminal || c.issued_at > now + 30 || (!allowExpired && c.expires_at <= now) || c.expires_at - c.issued_at > 72 * 3600) throw new Error('Offline manager access expired or belongs to another shift/terminal. Reconnect POSNext to refresh it automatically.');
  return c;
}
async function pinKey(pin, salt) {
  const material = await crypto.subtle.importKey('raw', encoder.encode(pin), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({name: 'PBKDF2', hash: 'SHA-256', salt, iterations: 310000}, material, {name: 'AES-GCM', length: 256}, false, ['encrypt', 'decrypt']);
}
const preparingDefaults = new Map();
let defaultsGeneration = 0;
export async function ensureOfflineFloatDefaults(shift, profile) {
  if (isOffline() || !shift || !profile || shift.startsWith('OFFLINE-')) return;
  const terminal = loadCashDrawerTerminalSettings(profile);
  if (terminal.mode === 'disabled' || !terminal.terminal_id) return;
  const cashier = await user();
  const marker = `float_defaults:${cashier}:${shift}:${terminal.terminal_id}`;
  if (preparingDefaults.has(marker)) return preparingDefaults.get(marker);
  const cached = await db.settings.get(marker);
  if (preparingDefaults.has(marker)) return preparingDefaults.get(marker);
  if (cached?.revision === 4 && Date.now() - cached.checked_at < (cached.count ? 3600000 : 60000)) return;
  const generation = defaultsGeneration;
  const work = (async () => {
    const result = unwrap(await call('pos_next.api.float_additions.get_default_offline_float_approvals', {
      pos_opening_shift: shift, terminal_id: terminal.terminal_id,
    }));
    const verified = [];
    for (const approval of result.approvals || []) {
      const c = await verifyGrant(approval.grant, shift, terminal.terminal_id, cashier);
      if (c.purpose !== 'posnext_cash_drawer_defaults_v4') throw new Error('Reconnect after the drawer update to refresh offline manager access.');
      verified.push({...approval, key: `float_approval:${cashier}:${shift}:${terminal.terminal_id}:${c.manager}`});
    }
    if (generation !== defaultsGeneration) return;
    // Signed cash records carry their own grant, so replacing cached keys does not erase queued cash.
    const prefix = `float_approval:${cashier}:${shift}:${terminal.terminal_id}:`;
    await db.transaction('rw', db.settings, async () => {
      await db.settings.where('key').startsWith(prefix).delete();
      for (const approval of verified) await db.settings.put(approval);
      await db.settings.put({key: marker, checked_at: Date.now(), revision: 4, count: verified.length, unavailable: result.unavailable || ''});
      if (result.history) await db.settings.put({key: `float_history:${cashier}:${shift}`, data: result.history});
    });
  })();
  preparingDefaults.set(marker, work);
  try { return await work; } finally { preparingDefaults.delete(marker); }
}
export async function clearFloatApprovals() {
  defaultsGeneration += 1;
  await db.settings.where('key').startsWith('float_approval:').delete();
  await db.settings.where('key').startsWith('float_defaults:').delete();
}
export async function cacheFloatHistory(shift, data) {
  const cashier = await user();
  await db.settings.put({key: `float_history:${cashier}:${shift}`, data});
}
export async function localFloatHistory(shift, profile) {
  const cashier = await user(), terminal = loadCashDrawerTerminalSettings(profile);
  const cached = await db.settings.get(`float_history:${cashier}:${shift}`);
  const approvals = await db.settings.where('key').startsWith(`float_approval:${cashier}:${shift}:${terminal.terminal_id}:`).toArray();
  let claims;
  for (const item of approvals) { try { claims = await verifyGrant(item.grant, shift, terminal.terminal_id, cashier); break; } catch (_) { /* Expired grants never authorize new money. */ } }
  const queued = await db.float_queue.where('shift').equals(shift).filter(row => row.user === cashier).toArray();
  const base = cached?.data || {rows: [], cash_modes: claims?.cash_modes || [], currency: claims?.currency || '', can_add: true};
  const knownNames = new Set((base.rows || []).map(row => row.name));
  const visibleQueue = queued.filter(row => row.status !== 'Synced' || !knownNames.has(row.server_name));
  return {...base, can_add: Boolean(base.can_add && claims), rows: [...(base.rows || []), ...visibleQueue.map(row => ({name: row.event_key, occurred_at: new Date(row.data.occurred_at * 1000).toLocaleString(), amount: row.data.amount, currency: payload(row.grant).currency, reason: row.data.reason, mode_of_payment: row.data.mode_of_payment, cashier: row.user, authorized_by: payload(row.grant).manager, offline: 1, sync_status: row.status, sync_error: row.error, drawer_status: row.drawer_status}))]};
}
let failures = 0, blockedUntil = 0;
async function unlockOfflineManager(shift, profile, pin) {
  if (Date.now() < blockedUntil) throw new Error('Too many incorrect PIN attempts. Wait five minutes.');
  const cashier = await user(), terminal = loadCashDrawerTerminalSettings(profile);
  const approvals = await db.settings.where('key').startsWith(`float_approval:${cashier}:${shift}:${terminal.terminal_id}:`).toArray();
  let key, grant, claims;
  for (const a of approvals) {
    try {
      const c = await verifyGrant(a.grant, shift, terminal.terminal_id, cashier);
      const aes = await pinKey(pin, bytes(a.salt));
      const raw = new Uint8Array(await crypto.subtle.decrypt({name: 'AES-GCM', iv: bytes(a.iv)}, aes, bytes(a.encrypted)));
      key = await crypto.subtle.importKey('pkcs8', raw, {name: 'Ed25519'}, false, ['sign']); raw.fill(0);
      grant = a.grant; claims = c; break;
    } catch (_) { /* Try another authorized manager. */ }
  }
  if (!key) { failures += 1; if (failures >= 5) { blockedUntil = Date.now() + 300000; failures = 0; } throw new Error('Manager PIN is incorrect or offline manager access is not ready. Reconnect once to refresh it automatically.'); }
  failures = 0;
  return {cashier, terminal, key, grant, claims};
}
export async function queueOfflineFloat(data, profile, pin) {
  const old = await db.float_queue.get(data.event_key);
  if (old) { if (old.user !== await user()) throw new Error('Cash addition belongs to another cashier.'); return old; }
  const {cashier, terminal, key, grant, claims} = await unlockOfflineManager(data.pos_opening_shift, profile, pin);
  const amount = Number(data.amount);
  if (!/^(?:[0-9]+(?:\.[0-9]{0,3})?|\.[0-9]{1,3})$/.test(String(data.amount)) || !Number.isFinite(amount) || amount < 0.001 || amount > 999999999.999 || Math.abs(amount * 1000 - Math.round(amount * 1000)) > 0.00001 || !String(data.reason).trim() || !claims.cash_modes.includes(data.mode_of_payment)) throw new Error('Enter valid cash details with at most three decimals.');
  const record = {pos_opening_shift: data.pos_opening_shift, terminal_id: terminal.terminal_id,
    event_key: data.event_key, amount: amount.toFixed(3), reason: data.reason.trim(), mode_of_payment: data.mode_of_payment, occurred_at: Math.floor(Date.now() / 1000)};
  const packet = JSON.stringify(record), signature = b64(await crypto.subtle.sign('Ed25519', key, encoder.encode(packet)));
  const row = {event_key: data.event_key, shift: data.pos_opening_shift, user: cashier, data: record, packet, signature, grant, status: 'Pending Sync', queued_at: Date.now(), drawer_status: 'Not requested', method: getCashDrawerMethodLabel(terminal.mode)};
  await db.float_queue.add(row);
  return row;
}
export async function updateOfflineDrawer(id, status, error = '') {
  await db.float_queue.update(id, {drawer_status: status, drawer_error: String(error).slice(0,500)});
}
let syncing;
export async function syncFloatQueue(shift) {
  if (isOffline()) return;
  if (syncing) { await syncing; return syncFloatQueue(shift); }
  syncing = (async () => {
    const cashier = await user();
    const rows = await db.float_queue.toArray();
    for (const row of rows.filter(r => r.user === cashier && r.status !== 'Synced' && (!shift || r.shift === shift) && (['Opened', 'Failed'].includes(r.drawer_status) || Date.now() - (r.queued_at || 0) > 300000))) {
      try {
        const result = unwrap(await call('pos_next.api.float_additions.sync_offline_float', {grant: JSON.stringify(row.grant), packet: row.packet, signature: row.signature, drawer_status: row.drawer_status, drawer_error: row.drawer_error || '', method: row.method}));
        await db.float_queue.update(row.event_key, {status: 'Synced', server_name: result.name, error: ''});
      } catch (exc) { await db.float_queue.update(row.event_key, {status: 'Needs Review', error: exc?.messages?.[0] || exc?.message || 'Sync failed'}); }
    }
  })();
  try { await syncing; } finally { syncing = null; }
}
export async function requireSyncedFloats(shift) {
  if (isOffline()) throw new Error('Reconnect and sync float additions before closing this shift.');
  await syncOfflineDrawers();
  await syncFloatQueue(shift);
  const cashier = await user();
  if (await getPendingFloatRequest(shift)) throw new Error('A cash addition response is unconfirmed. Open Add Float and retry the same addition before closing.');
  const pending = await db.float_queue.where('shift').equals(shift).filter(r => r.user === cashier && r.status !== 'Synced').count();
  if (pending) throw new Error('Float additions still need sync or manager review. Open Add Float history before closing.');
}


export async function getPendingFloatRequest(shift) {
  const cashier = await user();
  return (await db.settings.get(`float_request:${cashier}:${shift}`))?.data || null;
}
export async function savePendingFloatRequest(shift, data) {
  const cashier = await user();
  await db.settings.put({key: `float_request:${cashier}:${shift}`, data});
}
export async function clearPendingFloatRequest(shift) {
  const cashier = await user();
  await db.settings.delete(`float_request:${cashier}:${shift}`);
}


export async function queueOfflineDrawer(data, profile, pin) {
  const {cashier, terminal, key, grant, claims} = await unlockOfflineManager(data.pos_opening_shift, profile, pin);
  if (claims.purpose !== 'posnext_cash_drawer_defaults_v4' || claims.allow_manual_cash_drawer !== true) throw new Error('Offline manual drawer opening is unavailable. Reconnect once to refresh the drawer policy.');
  const old = await db.drawer_queue.get(data.event_key);
  if (old) {
    const prior = await verifyGrant(old.grant, data.pos_opening_shift, terminal.terminal_id, cashier);
    if (old.user !== cashier || old.shift !== data.pos_opening_shift || old.data.reason !== String(data.reason || '').trim() || prior.manager !== claims.manager) throw new Error('Drawer request conflicts with an existing event.');
    return old;
  }
  const reason = String(data.reason || '').trim();
  if (!reason || reason.length > 500 || terminal.mode === 'disabled') throw new Error('A configured drawer and reason of 1 to 500 characters are required.');
  const record = {pos_opening_shift: data.pos_opening_shift, terminal_id: terminal.terminal_id,
    event_key: data.event_key, reason, occurred_at: Math.floor(Date.now() / 1000), operation: 'manual_drawer_open_v1', method: getCashDrawerMethodLabel(terminal.mode)};
  const packet = JSON.stringify(record), signature = b64(await crypto.subtle.sign('Ed25519', key, encoder.encode(packet)));
  const row = {event_key: data.event_key, shift: data.pos_opening_shift, user: cashier, data: record,
    packet, signature, grant, status: 'Pending Sync', queued_at: Date.now(), drawer_status: 'Not requested'};
  await db.drawer_queue.add(row);
  return row;
}
export async function claimOfflineDrawer(id) {
  const cashier = await user();
  return db.transaction('rw', db.drawer_queue, async () => {
    const row = await db.drawer_queue.get(id);
    if (!row || row.user !== cashier || row.drawer_status !== 'Not requested' || Date.now() - row.queued_at > 300000) return false;
    await db.drawer_queue.update(id, {drawer_status: 'Requested'});
    return true;
  });
}
export async function finishOfflineDrawer(id, status, error = '', printer = '') {
  await db.drawer_queue.update(id, {drawer_status: status, drawer_error: String(error).slice(0,500), printer_name: printer, status: 'Pending Sync'});
}
let syncingDrawers;
export async function syncOfflineDrawers() {
  if (isOffline()) return;
  if (syncingDrawers) return syncingDrawers;
  syncingDrawers = (async () => {
    const cashier = await user();
    const rows = await db.drawer_queue.toArray();
    for (const row of rows.filter(r => r.user === cashier && r.status !== 'Synced' && (['Opened','Failed'].includes(r.drawer_status) || Date.now() - (r.queued_at || 0) > 300000))) {
      try {
        const result = unwrap(await call('pos_next.api.cash_drawer.sync_offline_open', {grant: JSON.stringify(row.grant), packet: row.packet, signature: row.signature,
          drawer_status: row.drawer_status, error_message: row.drawer_error || '', printer_name: row.printer_name || ''}));
        await db.drawer_queue.update(row.event_key, {status: 'Synced', server_name: result.name, error: ''});
      } catch (exc) { await db.drawer_queue.update(row.event_key, {status: 'Needs Review', error: exc?.messages?.[0] || exc?.message || 'Drawer audit sync failed'}); }
    }
  })();
  try { await syncingDrawers; } finally { syncingDrawers = null; }
}
