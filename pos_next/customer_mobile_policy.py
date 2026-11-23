"""POS-only mobile uniqueness, including legacy Customer and primary Contact values."""
import re
import frappe
from frappe import _

FIELD = 'custom_pos_mobile_key'


def normalize_mobile(value):
    digits = re.sub(r'[^0-9]', '', str(value or ''))
    if digits.startswith('00'):
        digits = digits[2:]
    # Existing Kuwait customer imports often omit +965.
    if len(digits) == 8:
        digits = '965' + digits
    return digits


def setup():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields({'Customer': [{
        'fieldname': FIELD, 'label': 'POS Mobile Uniqueness Key',
        'fieldtype': 'Data', 'insert_after': 'mobile_no',
        'hidden': 1, 'read_only': 1, 'no_copy': 1, 'unique': 1,
        'description': 'Normalized mobile key maintained by POSNext create/edit APIs.',
    }]}, update=True)


def duplicates_allowed(pos_profile):
    if not pos_profile:
        return False
    frappe.get_doc('POS Profile', pos_profile).check_permission('read')
    from frappe.utils import cint
    return bool(cint(frappe.db.get_value('POS Settings',
        {'pos_profile': pos_profile, 'enabled': 1}, 'allow_duplicate_customer_mobile')))


def require_unique_mobile(value, exclude_customer=None, pos_profile=None):
    key = normalize_mobile(value)
    if not key or duplicates_allowed(pos_profile):
        return None
    if not frappe.get_meta('Customer').has_field(FIELD):
        frappe.throw(_('Run site migration before creating or editing customers in POSNext.'))
    # SQL normalization deliberately mirrors normalize_mobile and includes legacy rows
    # whose unique key has not been populated. Do not backfill or alter old duplicates.
    maria = "REGEXP_REPLACE(COALESCE({field}, ''), '[^0-9]', '')"
    postgres = "REGEXP_REPLACE(COALESCE({field}, ''), '[^0-9]', '', 'g')"
    template = postgres if frappe.db.db_type == 'postgres' else maria
    def normalized(field):
        digits = template.format(field=field)
        stripped = "(CASE WHEN LEFT({d}, 2) = '00' THEN SUBSTRING({d}, 3) ELSE {d} END)".format(d=digits)
        return "(CASE WHEN LENGTH({d}) = 8 THEN CONCAT('965', {d}) ELSE {d} END)".format(d=stripped)
    if frappe.db.db_type == 'postgres':
        customer_table, contact_table = '"tabCustomer"', '"tabContact"'
    else:
        customer_table, contact_table = '`tabCustomer`', '`tabContact`'
    query = f'''SELECT c.name FROM {customer_table} c
        LEFT JOIN {contact_table} p ON p.name = c.customer_primary_contact
        WHERE (%(exclude)s IS NULL OR c.name != %(exclude)s)
        AND (c.{FIELD} = %(key)s OR {normalized('c.mobile_no')} = %(key)s
             OR {normalized('p.mobile_no')} = %(key)s)
        LIMIT 1'''
    if frappe.db.sql(query, {'exclude': exclude_customer, 'key': key}):
        frappe.throw(_('A customer with this mobile number already exists. Select the existing customer instead.'))
    return key
