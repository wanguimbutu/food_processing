// Copyright (c) 2025, wanguimbutu and contributors
// For license information, please see license.txt

frappe.ui.form.on('Meals', {
    refresh: function(frm) {
        calculate_total_meal_cost(frm);
    },
    recipes_add: function(frm) {
        calculate_total_meal_cost(frm);  // When a recipe is added
    },
    recipes_remove: function(frm) {
        calculate_total_meal_cost(frm);  // When a recipe is removed
    }
});

frappe.ui.form.on('Recipe Details', {
    cost_per_recipe: function(frm, cdt, cdn) {
        calculate_total_meal_cost(frm);  // When cost changes
    }
});

function calculate_total_meal_cost(frm) {
    let total_cost = 0;

    (frm.doc.recipes || []).forEach(recipe => {
        total_cost += recipe.cost_per_recipe || 0;
    });

    frm.set_value('total_meal_cost', total_cost);
    frm.refresh_field('total_meal_cost');
}
