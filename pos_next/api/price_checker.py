"""Read-only price-list comparison. No cart, invoice or stock mutations."""
from decimal import Decimal, InvalidOperation
import frappe
from frappe import _
from frappe.utils import getdate, nowdate, cint


def _context(pos_profile):
    profile = frappe.get_doc('POS Profile', pos_profile)
    profile.check_permission('read')
    if profile.get('disabled'):
        frappe.throw(_('This POS Profile is disabled.'))
    users = [row.user for row in profile.get('applicable_for_users') or [] if row.get('user')]
    if users and frappe.session.user not in users and frappe.session.user != 'Administrator' and 'System Manager' not in frappe.get_roles():
        frappe.throw(_('You are not assigned to this POS Profile.'), frappe.PermissionError)
    selling = profile.get('selling_price_list')
    if not selling:
        frappe.throw(_('Set the selling Price List on the POS Profile first.'))
    comparison = frappe.db.get_value('POS Settings', {'pos_profile': pos_profile, 'enabled': 1}, 'comparison_price_list')
    from pos_next.api.items import _get_pos_profile_allowed_item_groups
    return profile, selling, comparison, _get_pos_profile_allowed_item_groups(profile)


def _check_item(item, groups):
    item.check_permission('read')
    if item.get('disabled') or not item.get('is_sales_item') or item.get('has_variants'):
        frappe.throw(_('Select an enabled sales item variant.'))
    if groups and item.get('item_group') not in groups:
        frappe.throw(_('This item is not available in the POS Profile.'))


def _price(item, price_list, uom):
    if not price_list:
        return None
    price_list_doc = frappe.get_doc('Price List', price_list)
    if not price_list_doc.get('enabled') or not price_list_doc.get('selling'):
        frappe.throw(_('Select an enabled selling Price List.'))
    fields = ['item_code', 'price_list_rate', 'currency', 'uom', 'valid_from', 'valid_upto', 'modified']
    optional = ['customer', 'supplier', 'batch_no', 'packing_unit', 'min_qty']
    meta = frappe.get_meta('Item Price')
    fields += [field for field in optional if meta.has_field(field)]
    codes = [item.name] + ([item.variant_of] if item.get('variant_of') else [])
    rows = frappe.get_all('Item Price', filters={'item_code': ['in', codes], 'price_list': price_list, 'selling': 1}, fields=fields, limit_page_length=0)
    today = getdate(nowdate())
    eligible = []
    for row in rows:
        if row.get('customer') or row.get('supplier') or row.get('batch_no'):
            continue
        if Decimal(str(row.get('packing_unit') or 1)) > 1 or Decimal(str(row.get('min_qty') or 0)) > 1:
            continue
        if row.get('valid_from') and getdate(row.valid_from) > today:
            continue
        if row.get('valid_upto') and getdate(row.valid_upto) < today:
            continue
        row_uom = row.get('uom') or item.stock_uom
        if row_uom != uom:
            continue
        eligible.append(row)
    eligible.sort(key=lambda row: (row.item_code == item.name, bool(row.get('uom')), str(row.get('valid_from') or ''), str(row.get('modified') or '')), reverse=True)
    result = {'price_list': price_list, 'currency': price_list_doc.get('currency'), 'uom': uom, 'rate': None}
    if eligible:
        row = eligible[0]
        try:
            rate = Decimal(str(row.price_list_rate))
        except (InvalidOperation, TypeError):
            return result
        if rate.is_finite() and rate >= 0:
            result.update(rate=float(rate), currency=row.get('currency') or result['currency'])
    return result


def _comparison(selling, comparison):
    if not selling or not comparison or selling.get('rate') is None or comparison.get('rate') is None:
        return None
    if not selling.get('currency') or selling['currency'] != comparison.get('currency') or selling['uom'] != comparison['uom']:
        return None
    current, original = Decimal(str(selling['rate'])), Decimal(str(comparison['rate']))
    if original <= 0 or current >= original:
        return None
    saving = original - current
    return {'savings': float(saving), 'discount_percentage': float(saving / original * 100), 'currency': selling['currency']}


def _store_stock(item, profile):
    warehouse = profile.get('warehouse')
    store = {'profile': profile.name, 'warehouse': warehouse, 'label': warehouse or profile.name}
    stock = {'available_qty': None, 'uom': item.stock_uom, 'tracked': bool(item.get('is_stock_item'))}
    if not warehouse or not item.get('is_stock_item'):
        return store, stock
    doc = frappe.get_doc('Warehouse', warehouse)
    doc.check_permission('read')
    store['label'] = doc.get('warehouse_name') or warehouse
    if profile.get('company') and doc.get('company') != profile.company:
        frappe.throw(_('The POS warehouse belongs to another company.'))
    warehouses = [warehouse]
    if doc.get('is_group'):
        warehouses = [row.name for row in frappe.get_all('Warehouse', filters={
            'lft': ['between', [doc.lft, doc.rgt]], 'company': doc.company}, fields=['name'], limit_page_length=0)]
    rows = frappe.get_all('Bin', filters={'item_code': item.name, 'warehouse': ['in', warehouses]},
                         fields=['actual_qty', 'reserved_qty'], limit_page_length=0)
    available = sum(Decimal(str(row.get('actual_qty') or 0)) - Decimal(str(row.get('reserved_qty') or 0)) for row in rows)
    stock['available_qty'] = float(available)
    return store, stock


def _item_image(item):
    if item.get('image'):
        return item.image
    if item.get('variant_of'):
        template = frappe.get_doc('Item', item.variant_of)
        try:
            template.check_permission('read')
        except frappe.PermissionError:
            return None
        return template.get('image')
    return None


def _result(item_code, context, barcode=None, uom=None):
    profile, selling, comparison, groups = context
    item = frappe.get_doc('Item', item_code)
    _check_item(item, groups)
    uom = uom or item.stock_uom
    current = _price(item, selling, uom)
    before = _price(item, comparison, uom)
    store, stock = _store_stock(item, profile)
    return {'kind': 'price', 'checked_at': nowdate(),
        'item': {'item_code': item.name, 'item_name': item.item_name, 'image': _item_image(item),
                 'barcode': barcode or '', 'uom': uom, 'brand': item.get('brand') or '',
                 'attributes': [{'attribute': row.attribute, 'value': row.attribute_value} for row in item.get('attributes') or []]},
        'selling': current, 'comparison': before, 'offer': _comparison(current, before), 'store': store, 'stock': stock}


@frappe.whitelist()
def lookup(pos_profile, query):
    context = _context(pos_profile)
    query = str(query or '').strip()
    if not query or len(query) > 140:
        frappe.throw(_('Scan a barcode or enter an item code or name.'))
    from pos_next.services.barcode import resolve_barcode
    resolved = resolve_barcode(query, pos_profile) or {}
    effective = resolved.get('item_barcode') or query
    row = frappe.db.get_value('Item Barcode', {'barcode': effective}, ['parent', 'uom'], as_dict=True)
    if row:
        return _result(row.parent, context, barcode=query, uom=row.get('uom'))
    if frappe.db.exists('Item', query):
        item = frappe.get_doc('Item', query)
        if not item.get('has_variants'):
            return _result(query, context)
    filters = {'disabled': 0, 'is_sales_item': 1, 'has_variants': 0}
    groups = context[3]
    if groups:
        filters['item_group'] = ['in', groups]
    rows = frappe.get_list('Item', filters=filters,
        or_filters=[['name', 'like', '%' + query + '%'], ['item_name', 'like', '%' + query + '%'], ['variant_of', '=', query]],
        fields=['name', 'item_name', 'image', 'stock_uom'], order_by='item_name asc', limit_page_length=20)
    return {'kind': 'matches', 'items': rows}


@frappe.whitelist()
def get_price(pos_profile, item_code):
    return _result(item_code, _context(pos_profile))


def validate_settings(doc):
    value = doc.get('comparison_price_list')
    if not value:
        return
    row = frappe.db.get_value('Price List', value, ['enabled', 'selling'], as_dict=True)
    if not row or not cint(row.enabled) or not cint(row.selling):
        frappe.throw(_('Comparison Price List must be an enabled selling Price List.'))
