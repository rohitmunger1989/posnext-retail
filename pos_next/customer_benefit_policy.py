"""Independent per-customer loyalty, wallet and credit preferences."""
import frappe
from frappe import _
from frappe.utils import cint, flt

FIELDS = {
    "loyalty": "custom_pos_disable_loyalty",
    "wallet": "custom_pos_disable_wallet",
    "credit": "custom_pos_disable_credit",
}


def disabled(customer, feature):
    if not customer:
        return False
    field = FIELDS[feature]
    if hasattr(customer, "get"):
        return bool(cint(customer.get(field)))
    if not frappe.get_meta("Customer").has_field(field):
        return False
    return bool(cint(frappe.db.get_value("Customer", customer, field)))


def loyalty_disabled(customer):
    return disabled(customer, "loyalty")


def wallet_disabled(customer):
    return disabled(customer, "wallet")


def credit_disabled(customer):
    return disabled(customer, "credit")


def reject_feature(customer, feature):
    if disabled(customer, feature):
        labels = {"loyalty": _("Loyalty points"), "wallet": _("Customer wallet"), "credit": _("Customer credit")}
        frappe.throw(_("{0} is disabled for this customer.").format(labels[feature]))


def validate_customer(doc, method=None):
    if loyalty_disabled(doc):
        doc.loyalty_program = None
        if doc.meta.has_field("loyalty_program_tier"):
            doc.loyalty_program_tier = None


def clear_invoice_loyalty(doc, method=None):
    if not loyalty_disabled(doc.get("customer")):
        return
    if cint(doc.get("redeem_loyalty_points")) or flt(doc.get("loyalty_amount")):
        reject_feature(doc.customer, "loyalty")
    for field, value in {"loyalty_program": None, "redeem_loyalty_points": 0,
                         "loyalty_points": 0, "loyalty_amount": 0,
                         "loyalty_redemption_account": None,
                         "loyalty_redemption_cost_center": None}.items():
        if doc.meta.has_field(field):
            doc.set(field, value)


def validate_return_settlement(invoice, data=None):
    """Validate explicitly selected credit/exchange options before draft/submit."""
    if not cint(invoice.get("is_return")) or not cint(invoice.get("is_pos")):
        return
    data = data if isinstance(data, dict) else {}
    customer = invoice.get("customer")
    if cint(data.get("pos_next_exchange_return") or invoice.get("pos_next_exchange_return")):
        reject_feature(customer, "credit")
    if cint(invoice.get("add_to_customer_balance")):
        # This existing UI option is labelled Customer Credit but is implemented
        # as a wallet credit; respect both independently configured restrictions.
        reject_feature(customer, "credit")
        reject_feature(customer, "wallet")


def validate_invoice(doc, method=None):
    customer = doc.get("customer")
    if not customer:
        return
    clear_invoice_loyalty(doc)
    if flt(doc.get("redeemed_customer_credit")) or flt(getattr(doc.flags, "pos_next_redeemed_customer_credit", 0)):
        reject_feature(customer, "credit")
    for row in doc.get("payments") or []:
        if not flt(row.get("amount")):
            continue
        mode = row.get("mode_of_payment")
        if mode == "POSNext Customer Credit" or cint(row.get("is_customer_credit")):
            reject_feature(customer, "credit")
        if mode and cint(frappe.db.get_value("Mode of Payment", mode, "is_wallet_payment")):
            reject_feature(customer, "wallet")


def before_submit_invoice(doc, method=None):
    validate_invoice(doc)
    # A standalone/no-invoice refund without a refund payment intentionally
    # creates customer credit. Block it before stock/GL submission; retain normal
    # invoice-linked returns and asynchronous original-provider refund handling.
    if (credit_disabled(doc.get("customer")) and cint(doc.get("is_return"))
            and cint(doc.get("is_pos")) and not doc.get("return_against")):
        unpaid = flt(doc.get("outstanding_amount"), doc.precision("outstanding_amount")) < 0
        has_refund = any(flt(row.get("amount")) < 0 for row in doc.get("payments") or [])
        if unpaid or (flt(doc.get("grand_total")) < 0 and not has_refund):
            reject_feature(doc.customer, "credit")
    # For linked returns, reversing an existing unpaid receivable is permitted.
    # Any value beyond that must be represented by refund payment rows, rather
    # than left as a newly reusable credit balance for a restricted customer.
    if (credit_disabled(doc.get("customer")) and cint(doc.get("is_return"))
            and cint(doc.get("is_pos")) and doc.get("return_against")):
        open_debt = max(0, flt(frappe.db.get_value("Sales Invoice", doc.return_against, "outstanding_amount")))
        refund = sum(max(0, -flt(row.get("amount"))) for row in doc.get("payments") or [])
        remainder = abs(flt(doc.get("grand_total"))) - refund - open_debt - abs(flt(doc.get("write_off_amount")))
        if flt(remainder, doc.precision("outstanding_amount")) > 0:
            reject_feature(doc.customer, "credit")
    # Returns retain normal accounting/provider refund behavior.
    if credit_disabled(doc.get("customer")) and not cint(doc.get("is_return")) and cint(doc.get("is_pos")):
        if flt(doc.get("outstanding_amount"), doc.precision("outstanding_amount")) > 0:
            frappe.throw(_("Customer credit is disabled. This POS sale must be fully paid."))


def validate_wallet(doc, method=None):
    if doc.is_new():
        reject_feature(doc.get("customer"), "wallet")


def validate_wallet_transaction(doc, method=None):
    owner = frappe.db.get_value("Wallet", doc.get("wallet"), "customer") if doc.get("wallet") else None
    reject_feature(owner, "wallet")
    reject_feature(doc.get("customer"), "wallet")


def validate_loyalty_entry(doc, method=None):
    reject_feature(doc.get("customer"), "loyalty")


def setup():
    """Ship default-off Customer options on installs and upgrades."""
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    fields = []
    after = "loyalty_program"
    definitions = [
        ("loyalty", "Disable Loyalty Points", "Stop loyalty earning and redemption. Wallet and credit have independent settings."),
        ("wallet", "Disable Customer Wallet", "Stop wallet creation, top-ups and payments. Loyalty points can still be earned if enabled."),
        ("credit", "Disable Customer Credit", "Stop customer credit redemption, credit sales and partial payment. POS sales must be fully paid."),
    ]
    for feature, label, description in definitions:
        fields.append({"fieldname": FIELDS[feature], "label": label, "fieldtype": "Check",
                       "insert_after": after, "default": "0",
                       "description": description + " Sync POS terminals online after changing this option."})
        after = FIELDS[feature]
    create_custom_fields({"Customer": fields}, update=True)
