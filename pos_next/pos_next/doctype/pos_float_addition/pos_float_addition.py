import frappe
from frappe.model.document import Document


class POSFloatAddition(Document):
    def before_insert(self):
        if not self.flags.get("authorized_float"):
            frappe.throw("Use Add Float in POSNext.", frappe.PermissionError)

    def validate(self):
        if not self.is_new():
            frappe.throw("Float history cannot be edited. Contact your manager for a correction.")

    def on_trash(self):
        frappe.throw("Float history cannot be deleted.")
