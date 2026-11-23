"""Save POS customer details through the linked primary Contact."""
import frappe
from frappe import _


def _set_primary_row(contact, table, value_field, primary_field, value):
    rows = contact.get(table) or []
    primary = [row for row in rows if row.get(primary_field)]
    if len(primary) > 1:
        frappe.throw(_('The Contact has multiple primary entries. Correct it in Desk first.'))
    if not value:
        for row in primary:
            if table == 'phone_nos' and row.get('is_primary_phone'):
                row.is_primary_mobile_no = 0
            else:
                contact.remove(row)
        return
    matching = next((row for row in rows if row.get(value_field) == value), None)
    if matching is None and primary:
        old = primary[0]
        # Do not replace a separately designated primary telephone number.
        if table != 'phone_nos' or not old.get('is_primary_phone'):
            matching = old
            matching.set(value_field, value)
    if matching is None:
        matching = contact.append(table, {value_field: value})
    for row in contact.get(table) or []:
        row.set(primary_field, int(row is matching))


@frappe.whitelist()
def update_customer(customer, customer_name, mobile_no, email_id='', customer_group='',
                    territory='', custom_governorate='', custom_district='', pos_profile=None):
    """Use ordinary document permissions and one request transaction; no core changes."""
    name = str(customer_name or '').strip()
    mobile = str(mobile_no or '').strip()
    email = str(email_id or '').strip()
    if not name or not mobile:
        frappe.throw(_('Customer name and mobile number are required.'))
    doc = frappe.get_doc('Customer', customer)
    doc.check_permission('write')
    from pos_next.customer_mobile_policy import require_unique_mobile, normalize_mobile, duplicates_allowed
    contact_name = doc.get('customer_primary_contact')
    contact = frappe.get_doc('Contact', contact_name) if contact_name else None
    previous_mobile = contact.get('mobile_no') if contact else doc.get('mobile_no')
    if normalize_mobile(previous_mobile) == normalize_mobile(mobile):
        # Existing duplicates may still receive non-phone edits; do not backfill their keys.
        mobile_key = None if duplicates_allowed(pos_profile) else doc.get('custom_pos_mobile_key')
    else:
        mobile_key = require_unique_mobile(mobile, exclude_customer=doc.name, pos_profile=pos_profile)
    if contact:
        links = contact.get('links') or []
        if not any(row.link_doctype == 'Customer' and row.link_name == doc.name for row in links):
            frappe.throw(_('The primary Contact is not linked to this Customer. Correct it in Desk first.'))
        change_mobile = (contact.get('mobile_no') or '') != mobile
        change_email = (contact.get('email_id') or '') != email
        if change_mobile or change_email:
            contact.check_permission('write')
            if any(row.link_doctype != 'Customer' or row.link_name != doc.name for row in links):
                frappe.throw(_('This Contact is shared with other records. Update it in Desk after reviewing its links.'))
            if change_mobile:
                _set_primary_row(contact, 'phone_nos', 'phone', 'is_primary_mobile_no', mobile)
            if change_email:
                _set_primary_row(contact, 'email_ids', 'email_id', 'is_primary', email)
            contact.save()
            contact.reload()
    else:
        contact = frappe.get_doc({'doctype': 'Contact', 'first_name': name,
            'is_primary_contact': 1,
            'links': [{'link_doctype': 'Customer', 'link_name': doc.name}],
            'phone_nos': [{'phone': mobile, 'is_primary_mobile_no': 1}],
            'email_ids': [{'email_id': email, 'is_primary': 1}] if email else []})
        contact.insert()
        contact.reload()
    if (contact.get('mobile_no') or '') != mobile or (contact.get('email_id') or '') != email:
        frappe.throw(_('The Contact did not retain the requested details. No customer update was completed.'))
    # Contact hooks may have refreshed the Customer; avoid saving a stale document.
    doc.reload()
    doc.update({'custom_pos_mobile_key': mobile_key, 'customer_name': name, 'customer_primary_contact': contact.name,
        'mobile_no': mobile, 'email_id': email, 'customer_group': customer_group,
        'territory': territory, 'custom_governorate': custom_governorate or None,
        'custom_district': custom_district or None})
    doc.save()
    doc.reload()
    if (doc.get('mobile_no') or '') != mobile or (doc.get('email_id') or '') != email:
        frappe.throw(_('The Customer did not retain the requested contact details. No update was completed.'))
    return doc.as_dict()
