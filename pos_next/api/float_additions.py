"""Cash custody additions. These do not create sales or accounting entries."""
from decimal import Decimal, InvalidOperation
import uuid

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt


def parse_amount(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount > Decimal("999999999.999"):
            raise ValueError
        if amount != amount.quantize(Decimal("0.001")):
            raise ValueError
        return float(amount)
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw("Enter a positive amount with at most three decimal places.")


def lock_shift(name, *, require_open=False, check_owner=True):
    rows = frappe.db.sql("SELECT name FROM `tabPOS Opening Shift` WHERE name=%s FOR UPDATE", (name,))
    if not rows:
        frappe.throw("Shift not found.")
    shift = frappe.get_doc("POS Opening Shift", name)
    if check_owner and shift.user != frappe.session.user:
        frappe.throw("This shift belongs to another cashier.", frappe.PermissionError)
    if require_open and (shift.docstatus != 1 or shift.status != "Open" or shift.pos_closing_shift):
        frappe.throw("The shift is closed. No float can be added.")
    return shift


def float_rows(shift):
    return frappe.get_all("POS Float Addition", filters={"pos_opening_shift": shift},
        fields=["name", "creation", "amount", "currency", "mode_of_payment", "reason", "cashier", "authorized_by", "occurred_at", "offline"],
        order_by="creation asc", limit_page_length=0)


def float_totals(shift):
    totals = {}
    for row in float_rows(shift):
        totals[row.mode_of_payment] = flt(totals.get(row.mode_of_payment, 0) + row.amount, 3)
    return totals


@frappe.whitelist()
def get_float_history(pos_opening_shift):
    shift = lock_shift(pos_opening_shift)
    profile = frappe.get_cached_doc("POS Profile", shift.pos_profile)
    modes = []
    for row in profile.get("payments") or []:
        mode = row.mode_of_payment
        if mode and frappe.db.get_value("Mode of Payment", mode, "type") == "Cash" and mode not in modes:
            modes.append(mode)
    return {"rows": float_rows(shift.name), "cash_modes": modes,
        "currency": frappe.get_cached_value("Company", shift.company, "default_currency"),
        "can_add": shift.docstatus == 1 and shift.status == "Open" and not shift.pos_closing_shift}


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def add_float(pos_opening_shift, amount, mode_of_payment, reason, event_key, pin_approval=None):
    shift = lock_shift(pos_opening_shift, require_open=True)
    amount = parse_amount(amount)
    reason = str(reason or "").strip()
    if not reason or len(reason) > 500:
        frappe.throw("Enter a reason of 1 to 500 characters.")
    try:
        event_key = str(uuid.UUID(str(event_key)))
    except (ValueError, TypeError, AttributeError):
        frappe.throw("Invalid float request ID.")
    from pos_next.api.pin_approval import authorize_pin_approval
    approval = authorize_pin_approval("add_float", {"pos_opening_shift": pos_opening_shift,
        "amount": amount, "mode_of_payment": mode_of_payment, "reason": reason, "event_key": event_key}, pin_approval)
    existing = frappe.db.get_value("POS Float Addition", {"event_key": event_key}, "name")
    if existing:
        doc = frappe.get_doc("POS Float Addition", existing)
        if (doc.pos_opening_shift != shift.name or doc.cashier != frappe.session.user
            or doc.amount != amount or doc.reason != reason or doc.mode_of_payment != mode_of_payment):
            frappe.throw("Request ID was already used with different details.")
        return {"name": doc.name, "already_saved": True}
    profile = frappe.get_cached_doc("POS Profile", shift.pos_profile)
    allowed = [p.mode_of_payment for p in profile.get("payments") or []]
    if mode_of_payment not in allowed or frappe.db.get_value("Mode of Payment", mode_of_payment, "type") != "Cash":
        frappe.throw("Choose a cash payment mode configured for this POS Profile.")
    currency = frappe.get_cached_value("Company", shift.company, "default_currency")
    if profile.currency and profile.currency != currency:
        frappe.throw("Add Float currently requires POS Profile and company currencies to match.")
    doc = frappe.get_doc({"doctype": "POS Float Addition", "pos_opening_shift": shift.name,
        "pos_profile": shift.pos_profile, "company": shift.company, "currency": currency,
        "mode_of_payment": mode_of_payment, "amount": amount, "reason": reason,
        "cashier": frappe.session.user, "authorized_by": approval["approver"], "event_key": event_key,
        "occurred_at": frappe.utils.now_datetime()})
    doc.flags.authorized_float = True
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "already_saved": False}


@frappe.whitelist()
def authorize_float_drawer(float_name, terminal_id=None, method=None):
    from pos_next.api.cash_drawer import _create_log, _get_settings
    addition = frappe.get_doc("POS Float Addition", float_name)
    shift = lock_shift(addition.pos_opening_shift, require_open=True)
    if addition.cashier != frappe.session.user:
        frappe.throw("This addition belongs to another cashier.", frappe.PermissionError)
    if not _get_settings(shift.pos_profile)["enable_cash_drawer"]:
        frappe.throw("Cash drawer is disabled in POS Settings.")
    if not str(terminal_id or "").strip() or method not in ("QZ Tray", "POSNext Local Agent", "POSNext Mobile Agent"):
        frappe.throw("Configure the terminal cash drawer first.")
    event_key = "FLOAT:" + addition.name
    existing = frappe.db.get_value("POS Cash Drawer Log", {"event_key": event_key}, ["name", "status"], as_dict=True)
    if existing:
        return {"authorized": False, "log_name": existing.name, "status": existing.status}
    log = _create_log(event_key=event_key, action="Float Addition", company=shift.company,
        pos_profile=shift.pos_profile, pos_opening_shift=shift.name, cash_amount=addition.amount,
        authorized_by=addition.authorized_by, reason="Float " + addition.name + ": " + addition.reason,
        terminal_id=terminal_id, method=method)
    return {"authorized": True, "log_name": log.name}


# Offline grants use the same installed signing key as cashier offline access.
# A browser signing key is encrypted under the manager PIN. No PIN is queued.
def _b64decode(value):
    import base64
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _verify_offline_packet(grant, packet, signature, *, action="float"):
    import json
    import time
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from pos_next.api.offline_authorization import KEY_DIRECTORY, EXPECTED_SITE
    if frappe.local.site != EXPECTED_SITE:
        frappe.throw("Offline float approval is not enabled for this site.")
    try:
        public = serialization.load_pem_public_key((KEY_DIRECTORY / "ed25519_public.pem").read_bytes())
        raw = _b64decode(grant["payload"])
        public.verify(_b64decode(grant["signature"]), raw)
        claims = json.loads(raw)
        encoded = packet.encode("utf-8")
        Ed25519PublicKey.from_public_bytes(_b64decode(claims["device_public_key"])).verify(_b64decode(signature), encoded)
        data = json.loads(packet)
        now = int(time.time())
        checks = [
            claims["purpose"] in ("posnext_float_approval_v1", "posnext_float_drawer_approval_v2", "posnext_float_drawer_defaults_v3", "posnext_cash_drawer_defaults_v4"),
            claims["site"] == frappe.local.site,
            claims["user"] == frappe.session.user,
            claims["shift"] == data["pos_opening_shift"],
            claims["terminal_id"] == data["terminal_id"],
            claims["issued_at"] <= data["occurred_at"] <= now + 30,
            data["occurred_at"] < claims["expires_at"],
            0 < claims["expires_at"] - claims["issued_at"] <= 72 * 3600,
            (action == "float" and set(data) == {"pos_opening_shift", "terminal_id", "event_key", "amount", "reason", "mode_of_payment", "occurred_at"})
            or (action == "drawer" and set(data) == {"pos_opening_shift", "terminal_id", "event_key", "reason", "occurred_at", "operation", "method"}
                and data.get("operation") == "manual_drawer_open_v1"
                and claims.get("purpose") == "posnext_cash_drawer_defaults_v4"
                and claims.get("allow_manual_cash_drawer") is True),
        ]
        if not all(checks):
            raise ValueError("Offline binding mismatch")
    except Exception:
        frappe.throw("Offline cash approval is invalid. Keep this entry and ask a manager to review it.")
    manager = frappe.get_doc("POS User PIN", claims["manager_pin_record"])
    if not manager.enabled or not manager.can_open_cash_drawer or manager.user != claims["manager"] or not frappe.db.get_value("User", manager.user, "enabled"):
        frappe.throw("Offline float approver is no longer authorized. Manager review is required.")
    return claims, data


@frappe.whitelist()
@rate_limit(limit=4, seconds=60)
def get_default_offline_float_approvals(pos_opening_shift, terminal_id):
    """Prepare existing drawer PINs automatically for this cashier's active terminal.

    Only encrypted device keys and signed grants leave the server, never PINs.
    """
    import base64
    import json
    import secrets
    import time
    from collections import Counter
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from pos_next.api.offline_authorization import KEY_DIRECTORY, EXPECTED_SITE, encode_base64url
    from pos_next.api.cash_drawer import _get_settings

    shift = lock_shift(pos_opening_shift, require_open=True)
    history = get_float_history(shift.name)
    if frappe.local.site != EXPECTED_SITE:
        return {"approvals": [], "history": history, "unavailable": "Offline authorization is not enabled for this site."}
    terminal_id = str(terminal_id or "").strip()
    if not terminal_id or len(terminal_id) > 140:
        frappe.throw("A configured terminal ID is required.")
    settings = _get_settings(shift.pos_profile)
    if not settings["enable_cash_drawer"]:
        return {"approvals": [], "history": history, "unavailable": "Cash drawer is disabled in POS Settings."}
    profile = frappe.get_cached_doc("POS Profile", shift.pos_profile)
    if profile.currency and profile.currency != history["currency"]:
        return {"approvals": [], "history": history, "unavailable": "Offline float requires company and POS currencies to match."}
    managers = frappe.get_all("POS User PIN", filters={"enabled": 1, "can_open_cash_drawer": 1}, fields=["name", "user"], limit_page_length=0)
    if len(managers) > 50:
        frappe.throw("More than 50 drawer approvers are configured. Contact your administrator to review offline access.")
    eligible = []
    for row in managers:
        if not row.user or not frappe.db.get_value("User", row.user, "enabled"):
            continue
        pin_doc = frappe.get_doc("POS User PIN", row.name)
        pin = pin_doc.get_password("pos_pin", raise_exception=False)
        if pin and str(pin).isdigit() and 4 <= len(str(pin)) <= 6:
            eligible.append((row, str(pin)))
    # Match online behavior: a PIN shared by two approvers must not authorize cash.
    counts = Counter(pin for _, pin in eligible)
    issuer = serialization.load_pem_private_key((KEY_DIRECTORY / "ed25519_private.pem").read_bytes(), password=None)
    now = int(time.time())
    approvals = []
    for row, pin in eligible:
        if counts[pin] != 1:
            continue
        device = Ed25519PrivateKey.generate()
        public = device.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        claims = {"purpose": "posnext_cash_drawer_defaults_v4", "site": frappe.local.site,
            "user": frappe.session.user, "shift": shift.name, "pos_profile": shift.pos_profile,
            "manager": row.user, "manager_pin_record": row.name, "terminal_id": terminal_id,
            "device_public_key": encode_base64url(public), "issued_at": now, "expires_at": now + 72 * 3600,
            "currency": history["currency"], "cash_modes": history["cash_modes"],
            "allow_manual_cash_drawer": bool(settings.get("allow_manual_cash_drawer", 1))}
        raw = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
        salt, iv = secrets.token_bytes(32), secrets.token_bytes(12)
        aes_key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=310000).derive(pin.encode())
        private = device.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        encrypted = AESGCM(aes_key).encrypt(iv, private, None)
        approvals.append({"grant": {"payload": encode_base64url(raw), "signature": encode_base64url(issuer.sign(raw))},
            "encrypted": encode_base64url(encrypted), "salt": encode_base64url(salt), "iv": encode_base64url(iv)})
    return {"approvals": approvals, "history": history, "expires_at": now + 72 * 3600,
        "unavailable": "No unique, enabled cash-drawer manager PIN is configured." if not approvals else ""}


@frappe.whitelist()
def sync_offline_float(grant, packet, signature, drawer_status=None, drawer_error=None, method=None):
    import json
    from datetime import datetime, timezone
    from frappe.utils import convert_utc_to_system_timezone
    grant = json.loads(grant) if isinstance(grant, str) else grant
    claims, data = _verify_offline_packet(grant, packet, signature)
    shift = lock_shift(data["pos_opening_shift"])
    amount = parse_amount(data["amount"])
    reason = str(data["reason"] or "").strip()
    event_key = str(uuid.UUID(str(data["event_key"])))
    old = frappe.db.get_value("POS Float Addition", {"event_key": event_key}, "name")
    if old:
        row = frappe.get_doc("POS Float Addition", old)
        if (row.pos_opening_shift != shift.name or row.cashier != frappe.session.user or row.amount != amount
            or row.reason != reason or row.mode_of_payment != data["mode_of_payment"] or row.authorized_by != claims["manager"]):
            frappe.throw("Offline request conflicts with an existing float entry.")
        return {"name": row.name, "already_saved": True}
    import time
    if time.time() >= claims["expires_at"]:
        frappe.throw("Offline approval expired before sync. Retain this addition for manager review.")
    if shift.docstatus != 1 or shift.status != "Open" or shift.pos_closing_shift:
        frappe.throw("Shift is closed. Retain the offline float entry for manager review.")
    if not reason or len(reason) > 500 or data["mode_of_payment"] not in claims["cash_modes"]:
        frappe.throw("Offline cash details are invalid.")
    # Current profile must still allow this cash mode.
    profile = frappe.get_cached_doc("POS Profile", shift.pos_profile)
    allowed = [p.mode_of_payment for p in profile.get("payments") or []]
    if data["mode_of_payment"] not in allowed or frappe.db.get_value("Mode of Payment", data["mode_of_payment"], "type") != "Cash":
        frappe.throw("The offline cash mode is no longer configured. Manager review is required.")
    if shift.pos_profile != claims["pos_profile"] or frappe.get_cached_value("Company", shift.company, "default_currency") != claims["currency"]:
        frappe.throw("Offline shift currency or profile changed.")
    occurred = datetime.fromtimestamp(data["occurred_at"], timezone.utc).replace(tzinfo=None)
    doc = frappe.get_doc({"doctype": "POS Float Addition", "pos_opening_shift": shift.name,
        "pos_profile": shift.pos_profile, "company": shift.company, "currency": claims["currency"],
        "mode_of_payment": data["mode_of_payment"], "amount": amount, "reason": reason,
        "cashier": frappe.session.user, "authorized_by": claims["manager"], "event_key": event_key,
        "offline": 1, "occurred_at": convert_utc_to_system_timezone(occurred).replace(tzinfo=None), "terminal_id": data["terminal_id"]})
    doc.flags.authorized_float = True
    doc.insert(ignore_permissions=True)
    from pos_next.api.cash_drawer import _create_log
    audit = _create_log(event_key="FLOAT:" + doc.name, action="Float Addition", company=shift.company,
        pos_profile=shift.pos_profile, pos_opening_shift=shift.name, cash_amount=amount,
        authorized_by=claims["manager"], reason="Offline float " + doc.name,
        terminal_id=data["terminal_id"], method=method)
    audit.status = "Opened" if drawer_status == "Opened" else "Failed" if drawer_status == "Failed" else "Pending"
    audit.error_message = str(drawer_error or "Recorded offline; hardware result reported by terminal.")[:500]
    audit.save(ignore_permissions=True)
    return {"name": doc.name, "already_saved": False}
