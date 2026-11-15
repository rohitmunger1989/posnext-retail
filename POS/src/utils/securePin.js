import { call } from 'frappe-ui';

/** Encrypt a PIN under an ephemeral server challenge; never send/store the raw PIN. */
export async function encryptManagerPin(action, context, pin) {
  if (!globalThis.crypto?.subtle) throw new Error('Secure browser cryptography is required for manager approval.');
  if (!/^\d{4,6}$/.test(String(pin || '').trim())) throw new Error('Enter the manager 4 to 6 digit POS PIN.');
  const response = await call('pos_next.api.pin_approval.issue_pin_challenge', {action, context: JSON.stringify(context)});
  const challenge = response?.message || response;
  if (challenge?.algorithm !== 'RSA-OAEP-SHA256' || !challenge.challenge_id || !challenge.public_key) throw new Error('Invalid manager approval challenge.');
  const pem = challenge.public_key.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\s/g, '');
  const der = Uint8Array.from(atob(pem), c => c.charCodeAt(0));
  const key = await crypto.subtle.importKey('spki', der, {name: 'RSA-OAEP', hash: 'SHA-256'}, false, ['encrypt']);
  const plaintext = new TextEncoder().encode(JSON.stringify({p: String(pin).trim(), n: challenge.challenge_id}));
  let cipher;
  try { cipher = await crypto.subtle.encrypt({name: 'RSA-OAEP'}, key, plaintext); }
  finally { plaintext.fill(0); }
  const ciphertext = btoa(String.fromCharCode(...new Uint8Array(cipher))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  return JSON.stringify({challenge_id: challenge.challenge_id, ciphertext});
}
