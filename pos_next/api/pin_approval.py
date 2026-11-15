"""Single-use encrypted manager PIN envelopes. Raw PINs never enter form_dict."""
import base64
import hashlib
import json
import uuid

import frappe
from frappe.rate_limiter import rate_limit

TTL_SECONDS = 90
ACTIONS = {"add_float", "manual_drawer", "drawer_setup"}


def _session_key():
    user = frappe.session.user
    sid = getattr(frappe.session, "sid", None)
    if not user or user == "Guest" or not sid:
        frappe.throw("An authenticated POS session is required.", frappe.PermissionError)
    return hashlib.sha256(str(sid).encode()).hexdigest()


def _cache_key(challenge_id):
    return f"{frappe.local.site}:posnext:encrypted-pin:v1:{_session_key()}:{challenge_id}"


def _canonical_context(action, context):
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except (ValueError, TypeError):
            frappe.throw("Invalid approval context.")
    fields = {
        "add_float": {"pos_opening_shift", "amount", "mode_of_payment", "reason", "event_key"},
        "manual_drawer": {"pos_profile", "pos_opening_shift", "reason", "terminal_id", "method", "request_id"},
        "drawer_setup": {"pos_profile", "pos_opening_shift"},
    }
    if action not in ACTIONS or not isinstance(context, dict) or set(context) != fields[action]:
        frappe.throw("Invalid approval action or context.")
    result = {key: str(value or "").strip() for key, value in context.items()}
    if action != "drawer_setup" and not result["pos_opening_shift"]:
        frappe.throw("An open POS shift is required.")
    if action == "add_float":
        from pos_next.api.float_additions import parse_amount
        result["amount"] = f"{parse_amount(context['amount']):.3f}"
        try:
            result["event_key"] = str(uuid.UUID(result["event_key"]))
        except (ValueError, TypeError, AttributeError):
            frappe.throw("Invalid cash addition request ID.")
        if not result["mode_of_payment"]:
            frappe.throw("Cash mode is required.")
    else:
        if not result["pos_profile"]:
            frappe.throw("POS Profile is required.")
    if action != "drawer_setup" and (not result["reason"] or len(result["reason"]) > 500):
        frappe.throw("Enter a reason of 1 to 500 characters.")
    if action == "manual_drawer":
        try:
            result["request_id"] = str(uuid.UUID(result["request_id"]))
        except (ValueError, TypeError, AttributeError):
            frappe.throw("Invalid drawer request ID.")
        if not result["terminal_id"] or len(result["terminal_id"]) > 140 or result["method"] not in ("QZ Tray", "POSNext Local Agent", "POSNext Mobile Agent"):
            frappe.throw("Configure the terminal cash drawer first.")
    return result


def _context_hash(context):
    raw = json.dumps(context, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _validate_context_shift(action, context):
    if action == "add_float":
        from pos_next.api.float_additions import lock_shift
        lock_shift(context["pos_opening_shift"], require_open=True)
    elif action == "drawer_setup" and not context["pos_opening_shift"]:
        if not frappe.db.exists("POS Profile", context["pos_profile"]):
            frappe.throw("POS Profile was not found.")
    else:
        from pos_next.api.cash_drawer import _validate_shift
        _validate_shift(context["pos_opening_shift"], context["pos_profile"])


@frappe.whitelist()
@rate_limit(limit=12, seconds=60)
def issue_pin_challenge(action, context):
    """Return a public key only; ephemeral private key stays in server Redis."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    _session_key()
    context = _canonical_context(action, context)
    _validate_context_shift(action, context)
    challenge_id = str(uuid.uuid4())
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    record = {"user": frappe.session.user, "session": _session_key(), "site": frappe.local.site,
        "action": action, "context": _context_hash(context), "private": private}
    frappe.cache.setex(_cache_key(challenge_id), TTL_SECONDS, json.dumps(record))
    return {"challenge_id": challenge_id, "public_key": public, "algorithm": "RSA-OAEP-SHA256", "expires_in": TTL_SECONDS}


def _consume_approval(action, context, challenge_id, ciphertext):
    """Confine secret handling and catch exceptions before they reach error snapshots."""
    record = None
    decrypted = None
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from pos_next.api.cash_drawer import _verify_drawer_manager_pin

        # Redis GETDEL is atomic: parallel/replayed submissions cannot reuse a key.
        raw = frappe.cache.getdel(_cache_key(challenge_id))
        if not raw:
            return None
        record = json.loads(raw)
        if (record["user"] != frappe.session.user or record["session"] != _session_key()
            or record["site"] != frappe.local.site or record["action"] != action
            or record["context"] != _context_hash(context)):
            return None
        private = serialization.load_pem_private_key(record.pop("private").encode(), password=None)
        encoded = ciphertext + "=" * (-len(ciphertext) % 4)
        cipher = base64.b64decode(encoded, altchars=b"-_", validate=True)
        decrypted = json.loads(private.decrypt(cipher, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)))
        if set(decrypted) != {"p", "n"} or decrypted["n"] != challenge_id:
            return None
        return _verify_drawer_manager_pin(decrypted["p"], permission="can_open_cash_drawer")
    except Exception:
        # No exception object, PIN, private key or decrypted payload is logged/returned.
        return None
    finally:
        if isinstance(decrypted, dict):
            decrypted.clear()
        if isinstance(record, dict):
            record.clear()


def authorize_pin_approval(action, context, pin_approval):
    """Validate one encrypted proof for exactly this session/action/context."""
    _session_key()
    context = _canonical_context(action, context)
    try:
        envelope = json.loads(pin_approval) if isinstance(pin_approval, str) else pin_approval
        if not isinstance(envelope, dict) or set(envelope) != {"challenge_id", "ciphertext"}:
            raise ValueError
        challenge_id = str(uuid.UUID(envelope["challenge_id"]))
        ciphertext = envelope["ciphertext"]
        if not isinstance(ciphertext, str) or len(ciphertext) > 800:
            raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError):
        frappe.throw("Encrypted manager approval is required. Refresh POSNext and try again.")
    approval = _consume_approval(action, context, challenge_id, ciphertext)
    if not approval:
        frappe.throw("Manager approval failed or expired. Enter the manager PIN again.", frappe.PermissionError)
    return approval
