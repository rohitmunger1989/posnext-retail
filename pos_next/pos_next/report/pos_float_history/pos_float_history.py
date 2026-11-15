"""Float history by permitted POS profile and shift; no financial mutations."""
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate


MANAGER_ROLES = {"System Manager", "Sales Manager", "Nexus POS Manager"}


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if not frappe.has_permission("POS Opening Shift", "read"):
        frappe.throw(_("You do not have permission to view POS shifts."), frappe.PermissionError)
    manager = bool(MANAGER_ROLES.intersection(frappe.get_roles()))
    readable = frappe.get_list("POS Profile", pluck="name", limit_page_length=0)
    if manager:
        profiles = readable
    else:
        assigned = set(frappe.get_all("POS Profile User", filters={"user": frappe.session.user}, pluck="parent", limit_page_length=0))
        profiles = [name for name in readable if name in assigned]
    if filters.pos_profile:
        if filters.pos_profile not in profiles:
            frappe.throw(_("You cannot view this POS Profile."), frappe.PermissionError)
        profiles = [filters.pos_profile]
    if not manager and filters.cashier and filters.cashier != frappe.session.user:
        frappe.throw(_("Cashiers can view only their own float additions."), frappe.PermissionError)
    columns = get_columns()
    if not profiles:
        return columns, []
    start = getdate(filters.from_date or add_days(nowdate(), -30))
    end = getdate(filters.to_date or nowdate())
    if start > end:
        frappe.throw(_("From Date must be before To Date."))
    conditions = ["a.pos_profile IN %(profiles)s", "COALESCE(a.occurred_at, a.creation) >= %(from_date)s", "COALESCE(a.occurred_at, a.creation) < %(until)s"]
    values = {"profiles": tuple(profiles), "from_date": start, "until": add_days(end, 1)}
    if not manager:
        conditions.append("a.cashier = %(cashier)s")
        values["cashier"] = frappe.session.user
    elif filters.cashier:
        conditions.append("a.cashier = %(cashier)s")
        values["cashier"] = filters.cashier
    for key, field in (("pos_opening_shift", "a.pos_opening_shift"), ("authorized_by", "a.authorized_by")):
        if filters.get(key):
            conditions.append(field + " = %(" + key + ")s")
            values[key] = filters.get(key)
    data = frappe.db.sql("""
        SELECT a.name, COALESCE(a.occurred_at, a.creation) AS occurred_at,
            a.company, a.pos_profile, a.pos_opening_shift, s.pos_closing_shift,
            s.status AS shift_status, s.period_start_date AS shift_opened_at,
            a.mode_of_payment, a.currency, a.amount, a.reason, a.cashier, a.authorized_by,
            a.offline, COALESCE(NULLIF(a.terminal_id, ''), l.terminal_id) AS terminal_id,
            l.status AS drawer_status
        FROM `tabPOS Float Addition` a
        LEFT JOIN `tabPOS Opening Shift` s ON s.name = a.pos_opening_shift
        LEFT JOIN `tabPOS Cash Drawer Log` l ON l.event_key = CONCAT('FLOAT:', a.name)
        WHERE """ + " AND ".join(conditions) + " ORDER BY occurred_at DESC, a.name DESC", values, as_dict=True)
    totals = defaultdict(float)
    for row in data:
        totals[row.currency] += flt(row.amount)
    summary = [{"label": _("Total Float Added") + " (" + currency + ")", "value": flt(amount, 3),
        "datatype": "Currency", "currency": currency, "indicator": "Green"} for currency, amount in sorted(totals.items())]
    return columns, data, None, None, summary


def get_columns():
    return [
        {"fieldname": "occurred_at", "label": _("Added At"), "fieldtype": "Datetime", "width": 165},
        {"fieldname": "pos_profile", "label": _("POS Profile"), "fieldtype": "Link", "options": "POS Profile", "width": 130},
        {"fieldname": "pos_opening_shift", "label": _("Opening Shift"), "fieldtype": "Link", "options": "POS Opening Shift", "width": 180},
        {"fieldname": "shift_status", "label": _("Shift Status"), "fieldtype": "Data", "width": 110},
        {"fieldname": "shift_opened_at", "label": _("Shift Opened At"), "fieldtype": "Datetime", "width": 165},
        {"fieldname": "pos_closing_shift", "label": _("Closing Shift"), "fieldtype": "Link", "options": "POS Closing Shift", "width": 180},
        {"fieldname": "amount", "label": _("Float Added"), "fieldtype": "Currency", "options": "currency", "precision": 3, "width": 130},
        {"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "width": 85},
        {"fieldname": "mode_of_payment", "label": _("Cash Mode"), "fieldtype": "Link", "options": "Mode of Payment", "width": 120},
        {"fieldname": "reason", "label": _("Reason"), "fieldtype": "Data", "width": 230},
        {"fieldname": "cashier", "label": _("Cashier"), "fieldtype": "Link", "options": "User", "width": 170},
        {"fieldname": "authorized_by", "label": _("Approved By"), "fieldtype": "Link", "options": "User", "width": 170},
        {"fieldname": "terminal_id", "label": _("Terminal"), "fieldtype": "Data", "width": 140},
        {"fieldname": "drawer_status", "label": _("Drawer Status"), "fieldtype": "Data", "width": 110},
        {"fieldname": "offline", "label": _("Recorded Offline"), "fieldtype": "Check", "width": 120},
        {"fieldname": "company", "label": _("Company"), "fieldtype": "Link", "options": "Company", "width": 180},
    ]
