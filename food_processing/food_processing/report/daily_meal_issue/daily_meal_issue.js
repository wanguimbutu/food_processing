frappe.query_reports["Daily Meal Issue"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "reqd": 1
        }
    ],

    onload: function(report) {
        report.page.add_inner_button(__('Create Material Request'), function() {
            let d = new frappe.ui.Dialog({
                title: 'Select Warehouse',
                fields: [
                    {
                        label: 'Required By Warehouse',
                        fieldname: 'warehouse',
                        fieldtype: 'Link',
                        options: 'Warehouse',
                        reqd: 1
                    }
                ],
                primary_action_label: 'Create',
                primary_action(values) {
                    let filters = report.get_values();
                    filters.warehouse = values.warehouse;

                    frappe.call({
                        method: "food_processing.food_processing.report.daily_meal_issue.daily_meal_issue.make_material_request",
                        args: { filters },
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint(__('Material Request {0} created', [r.message]));
                                frappe.set_route("Form", "Material Request", r.message);
                            }
                        }
                    });
                    d.hide();
                }
            });

            d.show();
        });
    }
};
