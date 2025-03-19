# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MealPlan(Document):
	pass

@frappe.whitelist()
def fetch_ingredients(meal_ids, total_servings):
    import json


    if isinstance(meal_ids, str):
        meal_ids = json.loads(meal_ids)  

    total_servings = float(total_servings)
    ingredient_list = {}

    for meal_id in meal_ids:
        meal = frappe.get_doc("Meals", meal_id)
        if not meal.recipes:
            frappe.throw(f"No recipes linked to meal {meal_id}.")

        for recipe_link in meal.recipes:
            recipe = frappe.get_doc("Recipe", recipe_link.recipe_name)

            for ingredient in recipe.ingredients:
                ingredient_name = ingredient.ingredient_name
                unit = ingredient.unit_of_measure
                qty_per_serving = float(ingredient.qty)
                cost_per_serving = float(ingredient.cost)

                final_qty = qty_per_serving * total_servings
                final_cost = cost_per_serving * total_servings

                if ingredient_name in ingredient_list:
                    ingredient_list[ingredient_name]["qty"] += final_qty
                    ingredient_list[ingredient_name]["cost"] += final_cost
                else:
                    ingredient_list[ingredient_name] = {
                        "ingredient_name": ingredient_name,
                        "qty": final_qty,
                        "unit_of_measure": unit,
                        "cost": final_cost
                    }

    return list(ingredient_list.values())