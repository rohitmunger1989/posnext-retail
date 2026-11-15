"""POSNext Retail cash drawer authorization and audit helpers.

Phase 1 does not talk to printer hardware. It authorizes a drawer operation
server-side, creates a mandatory audit record, and returns a request the POS
frontend can later execute through QZ Tray or the POSNext Local Agent.
"""

from __future__ import annotations

import secrets
import uuid

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, flt, now_datetime


DRAWER_SETTINGS_FIELDS = [
    "enable_cash_drawer",
    "auto_open_cash_sale",
    "auto_open_cash_refund",
    "allow_manual_cash_drawer",
    "require_manager_pin_cash_drawer",
]


def _enabled(value, default=0) -> int:
    if value is None or value == "":
        return cint(default)
    return cint(value)


def _get_settings(pos_profile: str) -> dict:
    settings = frappe.db.get_value(
        "POS Settings",
        {"pos_profile": pos_profile, "enabled": 1},
        DRAWER_SETTINGS_FIELDS,
        as_dict=True,
    ) or {}

    return {
        "enable_cash_drawer": _enabled(settings.get("enable_cash_drawer"), 0),
        "auto_open_cash_sale": _enabled(settings.get("auto_open_cash_sale"), 1),
        "auto_open_cash_refund": _enabled(settings.get("auto_open_cash_refund"), 1),
        "allow_manual_cash_drawer": _enabled(settings.get("allow_manual_cash_drawer"), 1),
        "require_manager_pin_cash_drawer": _enabled(
            settings.get("require_manager_pin_cash_drawer"), 1
        ),
    }


def _validate_shift(pos_opening_shift: str | None, pos_profile: str) -> dict:
    if not pos_opening_shift:
        frappe.throw(_("An open POS shift is required."))

    shift = frappe.db.get_value(
        "POS Opening Shift",
        pos_opening_shift,
        ["name", "pos_profile", "docstatus", "status", "user", "pos_closing_shift"],
        as_dict=True,
    )
    if not shift:
        frappe.throw(_("POS Opening Shift {0} was not found.").format(pos_opening_shift))
    if shift.pos_profile != pos_profile:
        frappe.throw(_("The POS shift does not belong to the selected POS Profile."))
    if shift.user != frappe.session.user:
        frappe.throw(_("This POS shift belongs to another cashier."), frappe.PermissionError)
    if (
        int(shift.docstatus or 0) != 1
        or (shift.status or "").lower() != "open"
        or bool(shift.pos_closing_shift)
    ):
        frappe.throw(_("The POS shift is not open."))
    return shift


def _verify_drawer_manager_pin(pin: str | None, *, permission="can_open_cash_drawer") -> dict:
    pin = (pin or "").strip()
    if not pin:
        frappe.throw(_("Manager POS PIN is required."))
    if not pin.isdigit() or not 4 <= len(pin) <= 6:
        frappe.throw(_("Manager POS PIN must contain 4 to 6 digits."))

    rows = frappe.get_all(
        "POS User PIN",
        filters={"enabled": 1, permission: 1},
        fields=["name", "user"],
        order_by="modified desc",
    )

    matches = []
    for row in rows:
        if not row.user or not frappe.db.get_value("User", row.user, "enabled"):
            continue
        try:
            doc = frappe.get_doc("POS User PIN", row.name)
            stored = doc.get_password("pos_pin", raise_exception=False)
        except TypeError:
            try:
                stored = doc.get_password("pos_pin")
            except Exception:
                stored = None
        except Exception:
            stored = None

        if stored and secrets.compare_digest(str(stored), pin):
            matches.append(row.user)

    if not matches:
        frappe.throw(_("Manager authorization failed. Check the POS PIN."))
    if len(matches) > 1:
        frappe.throw(
            _(
                "This POS PIN is assigned to more than one drawer approver. "
                "Ask an administrator to assign unique PINs."
            )
        )
    return {"approver": matches[0]}


def _normalize_method(method: str | None) -> str:
    method = (method or "").strip()
    if method not in ("QZ Tray", "POSNext Local Agent", "POSNext Mobile Agent"):
        return ""
    return method


def _cash_amount(invoice_doc) -> float:
    total = 0.0
    for payment in invoice_doc.get("payments") or []:
        mode = (payment.get("mode_of_payment") or "").strip()
        amount = flt(payment.get("amount") or 0)
        if not mode or abs(amount) < 0.0000001:
            continue
        mode_type = frappe.db.get_value("Mode of Payment", mode, "type")
        if (mode_type or "").strip().lower() == "cash":
            total += abs(amount)
    return flt(total, 3)


def _create_log(
    *,
    event_key: str,
    action: str,
    pos_profile: str,
    pos_opening_shift: str,
    invoice=None,
    cash_amount=0,
    authorized_by=None,
    reason=None,
    terminal_id=None,
    method=None,
    company=None,
    warehouse=None,
):
    doc = frappe.get_doc(
        {
            "doctype": "POS Cash Drawer Log",
            "event_key": event_key,
            "action": action,
            "status": "Pending",
            "invoice": invoice,
            "cash_amount": flt(cash_amount or 0, 3),
            "company": company,
            "warehouse": warehouse,
            "pos_profile": pos_profile,
            "pos_opening_shift": pos_opening_shift,
            "cashier": frappe.session.user,
            "authorized_by": authorized_by,
            "reason": (reason or "").strip(),
            "terminal_id": (terminal_id or "").strip()[:140],
            "method": _normalize_method(method),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


@frappe.whitelist()
def get_cash_drawer_settings(pos_profile: str):
    if not pos_profile:
        frappe.throw(_("POS Profile is required."))
    if not frappe.db.exists("POS Profile", pos_profile):
        frappe.throw(_("POS Profile {0} was not found.").format(pos_profile))
    return _get_settings(pos_profile)


@frappe.whitelist()
@rate_limit(limit=10, seconds=60)
def verify_cash_drawer_manager_pin(pos_profile=None, pos_opening_shift=None, pin_approval=None):
    """Authorize setup using an encrypted, session-bound manager approval."""
    from pos_next.api.pin_approval import authorize_pin_approval
    if pos_opening_shift:
        _validate_shift(pos_opening_shift, pos_profile)
    elif not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
        frappe.throw(_("POS Profile was not found."))
    approval = authorize_pin_approval("drawer_setup", {"pos_profile": pos_profile,
        "pos_opening_shift": pos_opening_shift}, pin_approval)
    return {"authorized": True, "authorized_by": approval["approver"]}


@frappe.whitelist()
@rate_limit(limit=20, seconds=60)
def authorize_automatic_open(
    invoice_name: str,
    pos_opening_shift: str,
    terminal_id: str | None = None,
    method: str | None = None,
):
    """Authorize one automatic drawer pulse for a submitted cash invoice."""
    if not invoice_name:
        frappe.throw(_("Sales Invoice is required."))

    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    if int(invoice.docstatus or 0) != 1:
        frappe.throw(_("Cash drawer can only be authorized for a submitted invoice."))

    pos_profile = (invoice.pos_profile or "").strip()
    if not pos_profile:
        frappe.throw(_("The invoice is not linked to a POS Profile."))

    _validate_shift(pos_opening_shift, pos_profile)

    invoice_shift = (invoice.get("posa_pos_opening_shift") or "").strip()
    if invoice_shift and invoice_shift != pos_opening_shift:
        frappe.throw(
            _("This invoice belongs to another POS opening shift."),
            frappe.PermissionError,
        )

    settings = _get_settings(pos_profile)
    if not settings["enable_cash_drawer"]:
        return {"authorized": False, "reason": "disabled"}

    is_return = bool(cint(invoice.is_return))
    if is_return and not settings["auto_open_cash_refund"]:
        return {"authorized": False, "reason": "cash_refund_auto_open_disabled"}
    if not is_return and not settings["auto_open_cash_sale"]:
        return {"authorized": False, "reason": "cash_sale_auto_open_disabled"}

    cash_amount = _cash_amount(invoice)
    if cash_amount <= 0:
        return {"authorized": False, "reason": "no_cash_movement", "cash_amount": 0}

    event_key = f"AUTO:{invoice.name}"
    existing = frappe.db.get_value(
        "POS Cash Drawer Log",
        {"event_key": event_key},
        ["name", "status"],
        as_dict=True,
    )
    if existing:
        return {
            "authorized": False,
            "reason": "already_authorized",
            "log_name": existing.name,
            "status": existing.status,
            "cash_amount": cash_amount,
        }

    try:
        log = _create_log(
            event_key=event_key,
            action="Automatic",
            invoice=invoice.name,
            cash_amount=cash_amount,
            company=invoice.company,
            warehouse=invoice.set_warehouse or None,
            pos_profile=pos_profile,
            pos_opening_shift=pos_opening_shift,
            terminal_id=terminal_id,
            method=method,
        )
    except frappe.DuplicateEntryError:
        existing_name = frappe.db.get_value(
            "POS Cash Drawer Log", {"event_key": event_key}, "name"
        )
        return {
            "authorized": False,
            "reason": "already_authorized",
            "log_name": existing_name,
            "cash_amount": cash_amount,
        }

    return {
        "authorized": True,
        "action": "Automatic",
        "log_name": log.name,
        "invoice": invoice.name,
        "is_return": is_return,
        "cash_amount": cash_amount,
    }


@frappe.whitelist()
@rate_limit(limit=12, seconds=60)
def authorize_manual_open(
    pos_profile: str,
    pos_opening_shift: str,
    pin_approval: str | None = None,
    request_id: str | None = None,
    reason: str | None = None,
    terminal_id: str | None = None,
    method: str | None = None,
):
    """Authorize a manager-approved manual drawer opening."""
    if not pos_profile:
        frappe.throw(_("POS Profile is required."))

    _validate_shift(pos_opening_shift, pos_profile)
    settings = _get_settings(pos_profile)

    if not settings["enable_cash_drawer"]:
        frappe.throw(_("Cash Drawer is disabled in POS Settings."))
    if not settings["allow_manual_cash_drawer"]:
        frappe.throw(_("Manual cash drawer opening is disabled in POS Settings."))

    reason = (reason or "").strip()
    if not reason:
        frappe.throw(_("A reason is required for manual cash drawer opening."))

    authorized_by = frappe.session.user
    if settings["require_manager_pin_cash_drawer"]:
        from pos_next.api.pin_approval import authorize_pin_approval
        authorized_by = authorize_pin_approval("manual_drawer", {"pos_profile": pos_profile,
            "pos_opening_shift": pos_opening_shift, "reason": reason, "terminal_id": terminal_id,
            "method": method, "request_id": request_id}, pin_approval)["approver"]

    try:
        event_key = "MANUAL:" + (uuid.UUID(str(request_id)).hex if request_id else uuid.uuid4().hex)
    except (ValueError, TypeError, AttributeError):
        frappe.throw(_("Invalid drawer request ID."))
    existing = frappe.db.get_value("POS Cash Drawer Log", {"event_key": event_key},
        ["name", "status", "cashier", "pos_opening_shift", "pos_profile", "reason", "terminal_id", "method"], as_dict=True)
    if existing:
        if (existing.cashier != frappe.session.user or existing.pos_opening_shift != pos_opening_shift
            or existing.pos_profile != pos_profile or existing.reason != reason
            or existing.terminal_id != str(terminal_id or "").strip() or existing.method != _normalize_method(method)):
            frappe.throw(_("Drawer request ID was already used for different details."))
        return {"authorized": False, "reason": "already_authorized", "log_name": existing.name, "status": existing.status}
    profile = frappe.get_cached_doc("POS Profile", pos_profile)
    log = _create_log(
        event_key=event_key,
        action="Manual",
        company=profile.company,
        warehouse=profile.warehouse,
        pos_profile=pos_profile,
        pos_opening_shift=pos_opening_shift,
        authorized_by=authorized_by,
        reason=reason,
        terminal_id=terminal_id,
        method=method,
    )

    return {
        "authorized": True,
        "action": "Manual",
        "log_name": log.name,
        "authorized_by": authorized_by,
        "reason": reason,
    }


@frappe.whitelist()
def report_open_result(
    log_name: str,
    success=0,
    printer_name: str | None = None,
    error_message: str | None = None,
):
    """Record QZ/Local Agent hardware success or failure."""
    if not log_name:
        frappe.throw(_("Cash drawer log is required."))

    doc = frappe.get_doc("POS Cash Drawer Log", log_name)
    if doc.cashier != frappe.session.user and "System Manager" not in frappe.get_roles():
        frappe.throw(
            _("You cannot update another cashier's drawer request."),
            frappe.PermissionError,
        )

    if doc.status != "Pending":
        return {
            "success": doc.status == "Opened",
            "log_name": doc.name,
            "status": doc.status,
        }

    ok = bool(cint(success))
    doc.status = "Opened" if ok else "Failed"
    doc.printer_name = (printer_name or "").strip()[:140]
    doc.error_message = (
        "" if ok else (error_message or _("Cash drawer hardware did not confirm opening."))[:500]
    )
    if ok:
        doc.opened_at = now_datetime()
    doc.save(ignore_permissions=True)

    return {
        "success": ok,
        "log_name": doc.name,
        "status": doc.status,
    }


@frappe.whitelist()
def sync_offline_open(grant, packet, signature, drawer_status=None, error_message=None, printer_name=None):
    """Import a signed offline manual drawer audit. Never opens hardware or adds cash."""
    import json
    import time
    from datetime import datetime, timezone
    from frappe.utils import convert_utc_to_system_timezone, get_datetime
    from pos_next.api.float_additions import _verify_offline_packet, lock_shift

    grant = json.loads(grant) if isinstance(grant, str) else grant
    claims, data = _verify_offline_packet(grant, packet, signature, action="drawer")
    shift = lock_shift(data["pos_opening_shift"])
    if shift.docstatus != 1 or shift.pos_profile != claims["pos_profile"]:
        frappe.throw("The offline drawer event does not match its POS shift.")
    reason = str(data["reason"] or "").strip()
    try:
        event_id = str(uuid.UUID(str(data["event_key"])))
    except (ValueError, TypeError, AttributeError):
        frappe.throw("Invalid offline drawer event ID.")
    if not reason or len(reason) > 500 or data["method"] not in ("QZ Tray", "POSNext Local Agent", "POSNext Mobile Agent"):
        frappe.throw("Invalid offline drawer reason or method.")
    occurred = datetime.fromtimestamp(data["occurred_at"], timezone.utc)
    occurred = convert_utc_to_system_timezone(occurred).replace(tzinfo=None)
    if occurred < get_datetime(shift.period_start_date):
        frappe.throw("The drawer event predates this shift.")
    if shift.pos_closing_shift:
        end = frappe.db.get_value("POS Closing Shift", shift.pos_closing_shift, "period_end_date")
        if not end or occurred > get_datetime(end):
            frappe.throw("The drawer event was recorded after the shift closed.")
    event_key = "OFFLINE-MANUAL:" + event_id
    name = frappe.db.get_value("POS Cash Drawer Log", {"event_key": event_key}, "name")
    if not name:
        # An online authorization response may have been lost before local fallback.
        # Both paths carry the same client request UUID; complete that audit once.
        name = frappe.db.get_value("POS Cash Drawer Log", {"event_key": "MANUAL:" + uuid.UUID(event_id).hex}, "name")
    if name:
        log = frappe.get_doc("POS Cash Drawer Log", name)
        if (log.cashier != frappe.session.user or log.pos_opening_shift != shift.name
            or log.authorized_by != claims["manager"] or log.reason != reason or log.terminal_id != data["terminal_id"]
            or log.method != data["method"] or log.action != "Manual"):
            frappe.throw("Offline drawer event conflicts with an existing audit entry.")
    else:
        if time.time() >= claims["expires_at"]:
            frappe.throw("Offline drawer approval expired before sync. Retain this audit for manager review.")
        log = _create_log(event_key=event_key, action="Manual", company=shift.company,
            warehouse=frappe.get_cached_value("POS Profile", shift.pos_profile, "warehouse"),
            pos_profile=shift.pos_profile, pos_opening_shift=shift.name, authorized_by=claims["manager"],
            reason=reason, terminal_id=data["terminal_id"], method=data["method"])
    # Late hardware confirmations may complete Pending, but never downgrade Opened.
    if log.status == "Pending":
        log.status = "Opened" if drawer_status == "Opened" else "Failed" if drawer_status == "Failed" else "Pending"
        log.error_message = str(error_message or "Offline manual drawer event; terminal reported the hardware result.")[:500]
        log.printer_name = str(printer_name or "")[:140]
        if log.status == "Opened":
            log.opened_at = occurred
        log.save(ignore_permissions=True)
    return {"name": log.name, "already_saved": bool(name), "status": log.status}
