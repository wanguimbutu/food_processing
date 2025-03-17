# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MealPlan(Document):
	pass

@frappe.whitelist()
def fetch_ingredients(meal_id, total_servings):
    total_servings = float(total_servings)

    # Fetch the Meal document
    meal = frappe.get_doc("Meals", meal_id)
    if not meal.recipes:
        frappe.throw("No recipes linked to this meal.")

    ingredient_list = {}

    print(f"\n🔍 Fetching Ingredients for Meal: {meal.name}")
    print(f"🍽 Total Servings Needed: {total_servings}")

    # Loop through all linked recipes
    for recipe_link in meal.recipes:  # Assuming meal.recipes is a child table
        recipe = frappe.get_doc("Recipe", recipe_link.recipe_name)  # Fetch each recipe

        print(f"\n📌 Processing Recipe: {recipe.name} (Servings: {recipe.servings_per_recipe})")

        if not recipe.ingredients:
            print("⚠️ No ingredients found for this recipe.")
            continue  # Skip to the next recipe

        for ingredient in recipe.ingredients:
            ingredient_name = ingredient.ingredient_name
            unit = ingredient.unit_of_measure
            qty_per_serving = float(ingredient.qty)  # Since servings per recipe is always 1
            cost_per_serving = float(ingredient.cost)  # Cost is already per serving

            # Multiply by total servings
            final_qty = qty_per_serving * total_servings
            final_cost = cost_per_serving * total_servings

            print(f"\n📝 Ingredient: {ingredient_name}")
            print(f"   - Qty Per Serving: {qty_per_serving} {unit}")
            print(f"   - Cost Per Serving: {cost_per_serving}")
            print(f"   - Final Qty Needed: {final_qty} {unit}")
            print(f"   - Final Cost: {final_cost}")

            # Merge duplicate ingredients
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
