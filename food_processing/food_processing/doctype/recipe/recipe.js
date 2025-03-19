// Copyright (c) 2025, wanguimbutu and contributors
// For license information, please see license.txt

frappe.ui.form.on('Recipe', {
    after_save: function(frm) {
        let tags = [];

        if (frm.doc.dairy) tags.push("Dairy");
        if (frm.doc.wheatgluten) tags.push("Wheat");
        if (frm.doc.nuts) tags.push("Nuts");
        if (frm.doc.eggs) tags.push("Eggs");
        if(frm.doc.fish) tags.push("Fish");
        if(frm.doc.beef) tags.push("Beef");
        if(frm.doc.poultry) tags.push("Poultry");
        if(frm.doc.shellfish) tags.push("Shellfish");
        if(frm.doc.soy) tags.push("Soy");

        if (tags.length > 0) {
            frappe.call({
                method: "food_processing.food_processing.doctype.recipe.recipe.add_recipe_tags",
                args: {
                    recipe_name: frm.doc.name, 
                    tags: tags.join(", ")       
                },
                callback: function(r) {
                    if (!r.exc) {
                        console.log("Tags successfully added:", tags);
                    } else {
                        console.error("Error adding tags:", r.exc);
                    }
                }
            });
        }
    }
});

frappe.ui.form.on('Ingredient Details', {
    substitute: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        let d = new frappe.ui.Dialog({
            title: "Substitute Ingredient",
            fields: [
                { label: "Current Ingredient", fieldname: "current_ingredient", fieldtype: "Data", read_only: 1, default: row.ingredient_name },
                { label: "New Substitute Ingredient", fieldname: "substituted_ingredient", fieldtype: "Link", options: "Item", reqd: 1 },
                { label: "New Qty", fieldname: "substituted_qty", fieldtype: "Float", reqd: 1 },
                { label: "New UOM", fieldname: "substituted_uom", fieldtype: "Data", reqd: 1 },
                { label: "Dietary Specification", fieldname: "dietary_specification", fieldtype: "MultiSelect",
                  options: ["Gluten-Free", "Vegan", "Nut-Free", "Dairy-Free", "Halal", "Kosher"]
                }
            ],
            primary_action_label: "Save Substitute",
            primary_action: function(data) {
                frappe.model.set_value(cdt, cdn, "substituted_ingredient", data.substituted_ingredient);
                frappe.model.set_value(cdt, cdn, "substituted_qty", data.substituted_qty);
                frappe.model.set_value(cdt, cdn, "substituted_uom", data.substituted_uom);
                
                // Ensure dietary_specification is stored as a list
                frappe.model.set_value(cdt, cdn, "dietary_specification", JSON.stringify(data.dietary_specification));

                frm.refresh_field("ingredients");
                d.hide();
            }
        });

        d.show();
    },
    ingredient: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        
        if (row.ingredient) {
            frappe.call({
                method: "frappe.client.get_value",
                args: {
                    doctype: "Item Price",
                    filters: {
                        item_code: row.ingredient,
                        price_list: "Standard Buying"
                    },
                    fieldname: "price_list_rate"
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, "cost", r.message.price_list_rate);
                    } else {
                        frappe.msgprint(__('No price found for this ingredient.'));
                    }
                }
            });
        }
    }
});

