// Copyright (c) 2026, BrainWise and contributors
// For license information, please see license.txt

frappe.ui.form.on("Customer", {
	refresh(frm) {
		frm.toggle_enable("loyalty_program", !frm.doc.custom_pos_disable_loyalty);
		frm.set_query("custom_district", () => {
			return {
				filters: {
					governorate: frm.doc.custom_governorate || "",
				},
			};
		});
	},

	custom_pos_disable_loyalty(frm) {
		frm.toggle_enable("loyalty_program", !frm.doc.custom_pos_disable_loyalty);
		if (frm.doc.custom_pos_disable_loyalty) frm.set_value("loyalty_program", null);
	},

	custom_governorate(frm) {
		if (frm.doc.custom_district) {
			frm.set_value("custom_district", null);
		}
	},
});
