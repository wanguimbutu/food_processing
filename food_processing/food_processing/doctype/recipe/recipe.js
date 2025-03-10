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