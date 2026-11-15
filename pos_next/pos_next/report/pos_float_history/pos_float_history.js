frappe.query_reports["POS Float History"] = {
    filters: [
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.add_days(frappe.datetime.get_today(), -30), reqd: 1},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
        {fieldname: "pos_profile", label: __("POS Profile"), fieldtype: "Link", options: "POS Profile"},
        {fieldname: "pos_opening_shift", label: __("Opening Shift"), fieldtype: "Link", options: "POS Opening Shift", get_query() {
            const profile = frappe.query_report.get_filter_value("pos_profile");
            return profile ? {filters: {pos_profile: profile}} : {};
        }},
        {fieldname: "cashier", label: __("Cashier"), fieldtype: "Link", options: "User"},
        {fieldname: "authorized_by", label: __("Approved By"), fieldtype: "Link", options: "User"},
    ],
};
