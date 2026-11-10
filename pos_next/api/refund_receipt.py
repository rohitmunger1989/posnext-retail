"""Print the return document independently of provider refund settlement."""
from __future__ import annotations

import re

import frappe
from frappe.utils import cint


def refund_context(invoice):
    if (
        invoice.doctype != "Sales Invoice" or not cint(invoice.is_return)
        or "erpnext_payment_hub" not in frappe.get_installed_apps()
    ):
        return None
    from erpnext_payment_hub.pos.refund import get_return_refund_status
    from erpnext_payment_hub.pos.return_submission import invoice_receipt_html

    info = get_return_refund_status(invoice.name)
    if not info.get("managed"):
        return None
    return {"info": info, "notice": invoice_receipt_html(invoice)}


def _with_notice(html, notice):
    if not notice or 'class="payment-hub-refund-notice"' in html:
        return html
    # Preserve the chosen print format, its branding, width and item tables.
    pattern = r'(<[^>]+\bclass=[\"\'][^\"\']*\bprint-format\b[^\"\']*[\"\'][^>]*>)'
    if re.search(pattern, html, flags=re.I):
        html = re.sub(pattern, lambda match: match.group(0) + notice, html, count=1, flags=re.I)
    elif re.search(r'<body\b[^>]*>', html, flags=re.I):
        html = re.sub(r'(<body\b[^>]*>)', lambda match: match.group(0) + notice, html, count=1, flags=re.I)
    else:
        html = notice + html
    # The tender rows remain the accounting audit; these labels must not claim
    # that the recipient's bank has settled an asynchronous refund.
    html = html.replace("Total Paid:", "Refund instruction recorded:")
    html = html.replace("Net Settled:", "Recorded refund total:")
    return html


@frappe.whitelist()
def get_html_and_style(doc, name, print_format=None, no_letterhead=1, letterhead=None):
    from frappe.www.printview import get_html_and_style as render

    # Core renderer performs print/read permission and document checks first.
    result = render(doc=doc, name=name, print_format=print_format,
                    no_letterhead=cint(no_letterhead), letterhead=letterhead)
    if doc != "Sales Invoice" or not result.get("html"):
        return result
    invoice = frappe.get_doc(doc, name)
    context = refund_context(invoice)
    if context:
        result["html"] = _with_notice(result["html"], context["notice"])
    return result


@frappe.whitelist()
def download_pdf(doctype, name, print_format=None, no_letterhead=1):
    invoice = frappe.get_doc(doctype, name)
    invoice.check_permission("print")
    context = refund_context(invoice)
    if not context:
        from frappe.utils.print_format import download_pdf as core_download
        return core_download(doctype=doctype, name=name, format=print_format, no_letterhead=cint(no_letterhead))
    from frappe.utils.pdf import get_pdf

    rendered = get_html_and_style(doc=doctype, name=name, print_format=print_format, no_letterhead=no_letterhead)
    html = ('<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
            + (rendered.get("style") or "") + '</style></head><body>'
            + rendered["html"] + '</body></html>')
    frappe.local.response.filename = name + ".pdf"
    frappe.local.response.filecontent = get_pdf(html)
    frappe.local.response.type = "pdf"
