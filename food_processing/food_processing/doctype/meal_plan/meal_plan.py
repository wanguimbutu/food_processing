# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json

class MealPlan(Document):
    pass

@frappe.whitelist()
def fetch_ingredients(meal_data, total_individuals, total_servings):
    """
    Fetches meal ingredients based on selected meals.
    - LSG meals use `selected_percentage * total_individuals`
    - Non-LSG meals use `total_servings` provided by the frontend
    """

    frappe.logger().info(f"Raw meal_data: {meal_data}, total_individuals: {total_individuals}, total_servings: {total_servings}")

    meal_list = json.loads(meal_data)  # Parse the incoming meal data
    total_individuals = float(total_individuals)
    total_servings = float(total_servings)  # Using this as provided by the frontend

    # Fetch all meal categories at once to avoid multiple DB calls
    meal_ids = [meal["meal_id"] for meal in meal_list]
    meal_categories = {
        meal.name: meal.meal_category
        for meal in frappe.get_all("Meals", filters={"name": ["in", meal_ids]}, fields=["name", "meal_category"])
    }

    total_meal_servings = 0

    for meal in meal_list:
        meal_id = meal["meal_id"]
        meal_category = meal_categories.get(meal_id, None)

        if meal_category == "LSG":
            selected_percentage = float(meal.get("selected_percentage", 0))  # Default to 0 if missing
            calculated_servings = selected_percentage * total_individuals  # LSG meals are based on % of individuals
        else:
            calculated_servings = total_servings  # Directly use `total_servings` from frontend for non-LSG meals

        frappe.logger().info(f"Meal {meal_id} ({meal_category}): Adding {calculated_servings} servings.")
        total_meal_servings += calculated_servings  # Accumulate total servings

    frappe.logger().info(f"Final total_servings for all meals: {total_meal_servings}")
    return actual_fetch_ingredients(meal_ids, total_meal_servings)

def actual_fetch_ingredients(meal_ids, total_servings):
    """
    Fetches ingredients for the given meal_ids and calculates quantities.
    """
    if isinstance(meal_ids, str):
        meal_ids = json.loads(meal_ids)

    total_servings = float(total_servings)
    ingredient_list = {}

    for meal_id in meal_ids:
        meal = frappe.get_doc("Meals", meal_id)
        if not meal.recipes:
            frappe.logger().warning(f"No recipes linked to meal {meal_id}. Skipping.")
            continue  # Avoid crashing on missing recipes

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

                frappe.logger().info(f"Updated {ingredient_name}: Qty={final_qty}, Cost={final_cost}")

    frappe.logger().info(f"Final ingredient list: {ingredient_list}")
    return list(ingredient_list.values())
