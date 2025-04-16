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
                            frappe.msgprint({
                                title: __("Material Request Created"),
                                message: `Created Material Request <b>${r.message}</b>.`,
                                indicator: "green"
                            });
                            frappe.set_route("Form", "Material Request", r.message);
                        }
                    }
                });
            }, __('Actions'));
        }
    }
});
