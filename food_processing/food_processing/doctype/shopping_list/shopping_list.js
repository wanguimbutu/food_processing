// Copyright (c) 2025, wanguimbutu and contributors
// For license information, please see license.txt

frappe.ui.form.on('Shopping List', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Create Material Request'), function() {
                frappe.call({
                    method: 'food_processing.food_processing.doctype.shopping_list.shopping_list.create_material_request',
                    args: {
                        shopping_list_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            let doc = r.message;
                            frappe.model.sync(doc);
                            frappe.set_route("Form", doc.doctype, doc.name);
                        }
                    }
                });
            }, __('Actions'));
        }
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button('View Required Shopping Items', () => {
              frappe.set_route('query-report', 'Required Shopping Items', {
                shopping_list: frm.doc.name
              });
            });
          }
    
        if (frm.doc.docstatus === 1 && frm.doc.meal_plan) {
            frm.add_custom_button(__('Create Meal Issue'), function() {
                open_meal_issue_dialog(frm);
            }, __('Actions'));
        }
    }
});
function open_meal_issue_dialog(frm) {
    frappe.db.get_single_value('Stock Settings', 'default_warehouse')
        .then(default_warehouse => {
            const d = new frappe.ui.Dialog({
                title: 'Create Meal Issue',
                fields: [
                    {
                        label: 'Meal Date',
                        fieldname: 'meal_date',
                        fieldtype: 'Date',
                        reqd: 1,
                        default: frappe.datetime.get_today()
                    },
                    {
                        label: 'Warehouse (source)',
                        fieldname: 'warehouse',
                        fieldtype: 'Link',
                        options: 'Warehouse',
                        reqd: 1,
                        default: default_warehouse
                    }
                ],
                primary_action_label: 'Create Issue',
                primary_action(values) {
                    d.hide();
                    frappe.call({
                        method: 'food_processing.food_processing.doctype.shopping_list.shopping_list.create_daily_meal_issue',
                        args: {
                            meal_plan_name: frm.doc.meal_plan,
                            meal_date: values.meal_date,
                            warehouse: values.warehouse
                        },
                        callback: res => {
                            if (!res.exc) {
                                frappe.show_alert({
                                    message: `Stock Entry ${res.message} created`,
                                    indicator: 'green'
                                });
                                frappe.set_route('Form', 'Stock Entry', res.message);
                            }
                        }
                    });
                }
            });

            d.show();
        });
}
