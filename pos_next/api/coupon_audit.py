from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt

SOURCE_POS = "POS Coupon"
SOURCE_ERP = "ERPNext Coupon Code"

AUDIT_FIELDS = (
    "posnext_coupon_code",
    "posnext_coupon_type",
    "posnext_coupon_source",
    "posnext_coupon_reference",
    "posnext_pricing_rule",
    "posnext_coupon_discount_type",
    "posnext_coupon_discount_value",
    "posnext_coupon_discount_amount",
    "posnext_coupon_usage_counted",
)


def _has_audit_fields(doc):
    meta = frappe.get_meta(doc.doctype)
    return all(meta.has_field(f) for f in AUDIT_FIELDS)


def clear_coupon_audit(doc):
    if not _has_audit_fields(doc):
        return
    doc.posnext_coupon_code = None
    doc.posnext_coupon_type = None
    doc.posnext_coupon_source = None
    doc.posnext_coupon_reference = None
    doc.posnext_pricing_rule = None
    doc.posnext_coupon_discount_type = None
    doc.posnext_coupon_discount_value = 0
    doc.posnext_coupon_discount_amount = 0
    doc.posnext_coupon_usage_counted = 0


def set_coupon_audit_from_code(doc, coupon_code, discount_amount=0):
    if not _has_audit_fields(doc):
        return

    code = (coupon_code or "").strip()
    if not code:
        clear_coupon_audit(doc)
        return

    pos_coupon = None
    if frappe.db.table_exists("POS Coupon"):
        pos_coupon = frappe.db.get_value(
            "POS Coupon",
            {"coupon_code": code, "company": doc.company},
            ["name", "coupon_code", "coupon_type", "discount_type", "discount_percentage", "discount_amount"],
            as_dict=True,
        ) or frappe.db.get_value(
            "POS Coupon",
            {"coupon_code": code},
            ["name", "coupon_code", "coupon_type", "discount_type", "discount_percentage", "discount_amount"],
            as_dict=True,
        )

    if pos_coupon:
        dtype = pos_coupon.discount_type
        dvalue = flt(pos_coupon.discount_percentage) if dtype == "Percentage" else flt(pos_coupon.discount_amount)
        doc.posnext_coupon_code = pos_coupon.coupon_code or code
        doc.posnext_coupon_type = pos_coupon.coupon_type
        doc.posnext_coupon_source = SOURCE_POS
        doc.posnext_coupon_reference = pos_coupon.name
        doc.posnext_pricing_rule = None
        doc.posnext_coupon_discount_type = dtype
        doc.posnext_coupon_discount_value = dvalue
        doc.posnext_coupon_discount_amount = flt(discount_amount)
        doc.posnext_coupon_usage_counted = 0
        return

    erp_coupon = None
    if frappe.db.table_exists("Coupon Code"):
        erp_coupon = frappe.db.get_value(
            "Coupon Code",
            {"coupon_code": code},
            ["name", "coupon_code", "coupon_type", "pricing_rule"],
            as_dict=True,
        ) or frappe.db.get_value(
            "Coupon Code",
            code,
            ["name", "coupon_code", "coupon_type", "pricing_rule"],
            as_dict=True,
        )

    if erp_coupon:
        dtype = None
        dvalue = 0
        if erp_coupon.pricing_rule:
            rule = frappe.db.get_value(
                "Pricing Rule",
                erp_coupon.pricing_rule,
                ["rate_or_discount", "discount_percentage", "discount_amount"],
                as_dict=True,
            )
            if rule:
                if rule.rate_or_discount == "Discount Percentage":
                    dtype = "Percentage"
                    dvalue = flt(rule.discount_percentage)
                elif rule.rate_or_discount == "Discount Amount":
                    dtype = "Amount"
                    dvalue = flt(rule.discount_amount)

        doc.posnext_coupon_code = erp_coupon.coupon_code or code
        doc.posnext_coupon_type = erp_coupon.coupon_type
        doc.posnext_coupon_source = SOURCE_ERP
        doc.posnext_coupon_reference = erp_coupon.name
        doc.posnext_pricing_rule = erp_coupon.pricing_rule
        doc.posnext_coupon_discount_type = dtype
        doc.posnext_coupon_discount_value = dvalue
        doc.posnext_coupon_discount_amount = flt(discount_amount)
        doc.posnext_coupon_usage_counted = 0
        return

    frappe.throw(_("Invalid coupon code"))


def _lock_coupon(doctype, name):
    rows = frappe.db.sql(
        f"SELECT name, used, maximum_use FROM `tab{doctype}` WHERE name = %s FOR UPDATE",
        (name,),
        as_dict=True,
    )
    return rows[0] if rows else None


def record_coupon_usage(doc, method=None):
    if doc.doctype != "Sales Invoice" or cint(doc.get("is_return")) or not _has_audit_fields(doc):
        return

    code = doc.get("posnext_coupon_code")
    source = doc.get("posnext_coupon_source")
    reference = doc.get("posnext_coupon_reference")
    if not code or not source or not reference or cint(doc.get("posnext_coupon_usage_counted")):
        return

    if source == SOURCE_POS:
        row = _lock_coupon("POS Coupon", reference)
        if not row:
            frappe.throw(_("POS Coupon {0} no longer exists").format(reference))
        used = cint(row.used)
        maximum_use = cint(row.maximum_use)
        if maximum_use and used >= maximum_use:
            frappe.throw(_("Coupon {0} has already reached its usage limit").format(code))
        frappe.db.set_value("POS Coupon", reference, "used", used + 1, update_modified=False)

    elif source == SOURCE_ERP:
        row = _lock_coupon("Coupon Code", reference)
        if not row:
            frappe.throw(_("Coupon Code {0} no longer exists").format(reference))
        used = cint(row.used)
        maximum_use = cint(row.maximum_use)
        if maximum_use and used >= maximum_use:
            frappe.throw(_("Coupon {0} has already reached its usage limit").format(code))
        frappe.db.set_value("Coupon Code", reference, "used", used + 1, update_modified=False)
    else:
        frappe.throw(_("Unsupported coupon source: {0}").format(source))

    doc.db_set("posnext_coupon_usage_counted", 1, update_modified=False)
    doc.posnext_coupon_usage_counted = 1


def release_coupon_usage(doc, method=None):
    if doc.doctype != "Sales Invoice" or not _has_audit_fields(doc):
        return
    if not cint(doc.get("posnext_coupon_usage_counted")):
        return

    source = doc.get("posnext_coupon_source")
    reference = doc.get("posnext_coupon_reference")

    if source == SOURCE_POS and reference:
        row = _lock_coupon("POS Coupon", reference)
        if row:
            frappe.db.set_value("POS Coupon", reference, "used", max(cint(row.used) - 1, 0), update_modified=False)
    elif source == SOURCE_ERP and reference:
        row = _lock_coupon("Coupon Code", reference)
        if row:
            frappe.db.set_value("Coupon Code", reference, "used", max(cint(row.used) - 1, 0), update_modified=False)

    doc.db_set("posnext_coupon_usage_counted", 0, update_modified=False)
    doc.posnext_coupon_usage_counted = 0
