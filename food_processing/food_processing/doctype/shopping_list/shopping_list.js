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

            // New button for creating daily material issue
            frm.add_custom_button(__('Create Daily Material Issue'), function() {
                // First, show a date picker dialog
                frappe.prompt([
                    {
                        label: 'Date',
                        fieldname: 'issue_date',
                        fieldtype: 'Date',
                        default: frappe.datetime.get_today(),
                        reqd: 1
                    },
                    {
                        label: 'Meal Plan',
                        fieldname: 'meal_plan',
                        fieldtype: 'Link',
                        options: 'Meal Plan',
                        reqd: 1
                    }
                ], function(values) {
                    frappe.call({
                        method: 'food_processing.food_processing.doctype.shopping_list.shopping_list.create_daily_material_issue',
                        args: {
                            shopping_list_name: frm.doc.name,
                            issue_date: values.issue_date,
                            meal_plan: values.meal_plan
                        },
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint({
                                    title: __("Material Issue Created"),
                                    message: `Created Material Issue <b>${r.message}</b> for ${values.issue_date}.`,
                                    indicator: "green"
                                });
                                frappe.set_route("Form", "Stock Entry", r.message);
                            }
                        }
                    });
                }, __('Create Daily Material Issue'), __('Create'));
            }, __('Actions'));

            // Debug button to check meal plan structure
            frm.add_custom_button(__('Debug Meal Plan'), function() {
                frappe.prompt([
                    {
                        label: 'Date',
                        fieldname: 'issue_date',
                        fieldtype: 'Date',
                        default: frappe.datetime.get_today(),
                        reqd: 1
                    },
                    {
                        label: 'Meal Plan',
                        fieldname: 'meal_plan',
                        fieldtype: 'Link',
                        options: 'Meal Plan',
                        reqd: 1
                    }
                ], function(values) {
                    frappe.call({
                        method: 'food_processing.food_processing.doctype.shopping_list.shopping_list.debug_meal_plan_structure',
                        args: {
                            meal_plan: values.meal_plan,
                            issue_date: values.issue_date
                        },
                        callback: function(r) {
                            if (r.message) {
                                console.log('Debug Result:', r.message);
                                let debug_info = r.message;
                                let message = `
                                    <b>Debug Information:</b><br>
                                    Meal Plan: ${debug_info.meal_plan}<br>
                                    Date: ${debug_info.issue_date}<br>
                                    Total Meal Entries: ${debug_info.meal_entries.length}<br>
                                    Meals Found: ${debug_info.meals.length}<br>
                                    Recipes Found: ${debug_info.recipes.length}<br>
                                    Ingredients Found: ${debug_info.ingredients.length}<br><br>
                                    <small>Check browser console for detailed information</small>
                                `;
                                frappe.msgprint({
                                    title: "Debug Information",
                                    message: message,
                                    indicator: "blue"
                                });
                            }
                        }
                    });
                }, __('Debug Meal Plan Structure'), __('Debug'));
            }, __('Debug'));
        }

        if (frm.doc.docstatus === 1) {
            frm.add_custom_button('View Required Shopping Items', () => {
                frappe.set_route('query-report', 'Required Shopping Items', {
                    shopping_list: frm.doc.name
                });
            });

            // New button for viewing daily meal requirements
            frm.add_custom_button('View Daily Meal Requirements', () => {
                frappe.prompt([
                    {
                        label: 'Date',
                        fieldname: 'date',
                        fieldtype: 'Date',
                        default: frappe.datetime.get_today(),
                        reqd: 1
                    },
                    {
                        label: 'Meal Plan',
                        fieldname: 'meal_plan',
                        fieldtype: 'Link',
                        options: 'Meal Plan',
                        reqd: 1
                    },
                    {
                        label: 'Warehouse (Optional)',
                        fieldname: 'warehouse',
                        fieldtype: 'Link',
                        options: 'Warehouse'
                    }
                ], function(values) {
                    frappe.set_route('query-report', 'Daily Meal Requirements', {
                        date: values.date,
                        meal_plan: values.meal_plan,
                        warehouse: values.warehouse,
                        shopping_list: frm.doc.name
                    });
                }, __('View Daily Requirements'), __('View'));
            });
        }
    }
});