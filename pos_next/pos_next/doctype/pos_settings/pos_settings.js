// Copyright (c) 2024, BrainWise and contributors
// For license information, please see license.txt

frappe.ui.form.on("POS Settings", {
	refresh(frm) {
        if (!frm.is_new() && frm.doc.customer_display_enabled && frm.perm?.[0]?.write) {
            frm.add_custom_button(__("Add Advertising Videos"), () => {
                new frappe.ui.FileUploader({
                    doctype: "POS Settings", docname: frm.doc.name, allow_multiple: true, is_private: 0,
                    restrictions: {allowed_file_types: ["video/*"], max_file_size: 500 * 1024 * 1024},
                    on_success(file) {
                        if (!file.file_url || (frm.doc.customer_display_videos || []).some(row => row.video === file.file_url)) return;
                        frm.add_child("customer_display_videos", {video:file.file_url,title:file.file_name,enabled:1});
                        frm.refresh_field("customer_display_videos");frm.dirty();
                    },
                });
            }, __("Customer Display"));
        }

		// Return receipts must use a Sales Invoice print format.
		frm.set_query("return_invoice_print_format", function () {
			return {
				filters: {
					doc_type: "Sales Invoice",
					disabled: 0,
				},
			};
		});

		// Set query for loyalty program filtered by POS Profile company
		frm.set_query("default_loyalty_program", function () {
			if (!frm.doc.__company) {
				return { filters: {} };
			}
			return {
				filters: {
					company: frm.doc.__company,
				},
			};
		});

		// Fetch company when form loads
		if (frm.doc.pos_profile) {
			fetch_pos_profile_company(frm);
		}
	},

	pos_profile(frm) {
		// Clear loyalty program when POS Profile changes
		frm.set_value("default_loyalty_program", "");
		frm.doc.__company = null;

		if (frm.doc.pos_profile) {
			fetch_pos_profile_company(frm);
		}
	},

	enable_loyalty_program(frm) {
		if (!frm.doc.enable_loyalty_program) {
			frm.set_value("default_loyalty_program", "");
		}
	},
});

function fetch_pos_profile_company(frm) {
	frappe.db.get_value("POS Profile", frm.doc.pos_profile, "company", (r) => {
		if (r && r.company) {
			frm.doc.__company = r.company;
		}
	});
}
