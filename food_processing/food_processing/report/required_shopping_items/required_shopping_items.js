// Copyright (c) 2025, wanguimbutu and contributors
// For license information, please see license.txt

frappe.query_reports["Required Shopping Items"] = {
    filters: [
        {
            fieldname: "shopping_list",
            label: "Shopping List",
            fieldtype: "Link",
            options: "Shopping List",
            reqd: 1
        }
    ],
    onload: function(report) {
        report.page.add_inner_button('Create Material Request', function() {
            frappe.call({
                method: "food_processing.food_processing.report.required_shopping_items.required_shopping_items.create_material_request",
                args: {
                    shopping_list: frappe.query_report.get_filter_value('shopping_list')
                },
                callback: function(response) {
                    if (response.message) {
                        frappe.set_route("Form", "Material Request", response.message);
                    }
                }
            });
        }, 'Actions');
    }
};

