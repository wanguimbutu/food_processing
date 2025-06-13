# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json
import datetime
import math
from collections import defaultdict


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
        meal_name = frappe.get_value("Meals", {"meal_id": meal_id}, "name")

        if not meal_name:
            # If meal_name is still None, log a warning and continue to the next
            frappe.logger().warning(f"Meal with meal_id {meal_id} not found in Meals. Skipping.")
            continue

        try:
            meal = frappe.get_doc("Meals", meal_name)
        except frappe.DoesNotExistError:
            frappe.logger().warning(f"Meal with name {meal_name} not found. Skipping.")
            continue  # Skip this meal if it can't be found

        if not meal.recipes:
            frappe.logger().warning(f"No recipes linked to meal {meal_id}. Skipping.")
            continue  # Avoid crashing on missing recipes

        for recipe_link in meal.recipes:
            recipe = frappe.get_doc("Recipe", recipe_link.recipe_name)

            for ingredient in recipe.ingredients:
                item_code = ingredient.ingredient  
                unit = ingredient.unit_of_measure
                qty_per_serving = float(ingredient.qty)
                final_qty = qty_per_serving * total_servings

                item_rate = frappe.db.get_value(
                    "Item Price",
                    {"item_code": item_code, "price_list": "Standard Buying"},
                    "price_list_rate"
                )

                if item_rate is None:
                    frappe.logger().warning(f"No price found for {item_code} in Standard Buying.")
                    item_rate = 0.0  

                final_cost = item_rate * final_qty 

                if item_code in ingredient_list:
                    ingredient_list[item_code]["qty"] += final_qty
                    ingredient_list[item_code]["cost"] += final_cost
                else:
                    ingredient_list[item_code] = {
                        "ingredient": item_code, 
                        "qty": final_qty,
                        "unit_of_measure": unit,
                        "cost": final_cost
                    }

                frappe.logger().info(f"Updated {item_code}: Qty={final_qty}, Cost={final_cost}")

    frappe.logger().info(f"Final ingredient list: {ingredient_list}")
    return list(ingredient_list.values())


@frappe.whitelist()
def get_meals_by_category(category, start=0, page_length=5, sort_order="asc"):
    start = int(start)
    page_length = int(page_length)
    sort_order = "ASC" if sort_order.lower() == "asc" else "DESC"

    query = f"""
        SELECT DISTINCT m.name, m.meal_name, m.meal_id
        FROM `tabMeals` m
        INNER JOIN `tabMeal Plan Category` c ON c.parent = m.name
        WHERE c.category = %s
        ORDER BY m.meal_name {sort_order}
        LIMIT %s OFFSET %s
    """

    return frappe.db.sql(query, (category, page_length, start), as_dict=True)

@frappe.whitelist()
def is_lsg_meal(meal_id):
    result = frappe.db.exists(
        "Meal Plan Category",
        {"parent": meal_id, "category": "LSG"}
    )
    return bool(result)

@frappe.whitelist()
def get_meal_cost_data(meal_ids):
    import json
    if isinstance(meal_ids, str):
        meal_ids = json.loads(meal_ids)

    meal_data = []

    meals = frappe.get_all(
        'Meals',
        filters={'meal_id': ['in', meal_ids]},
        fields=['name', 'meal_id', 'total_meal_cost']
    )

    for meal in meals:
        meal_doc = frappe.get_doc('Meals', meal.name)
        categories = [row.category for row in meal_doc.meal_plan_category]  

        category = categories[0] if categories else "Uncategorized"

        meal_data.append({
            'meal_id': meal.meal_id,
            'total_meal_cost': meal.total_meal_cost,
            'category': category
        })

    return meal_data

@frappe.whitelist()
def check_meal_plan_overlap(meal_plan_name, start_date, end_date):
    current_plan = frappe.get_doc("Meal Plan", meal_plan_name)

    overlapping_names = frappe.get_all(
        "Meal Plan",
        filters={
            "name": ["!=", meal_plan_name],
            "start_date": ["<=", end_date],
            "end_date": [">=", start_date],
            "docstatus": 1
        },
        pluck="name"
    )

    if not overlapping_names:
        return {"message": "No overlapping meal plans."}

    for name in overlapping_names:
        overlapping_doc = frappe.get_doc("Meal Plan", name)

        # Copy HTML table
        if overlapping_doc.meal_plan_table:
            current_plan.meal_plan_table = overlapping_doc.meal_plan_table

        # Copy Meal Plan Entries
        existing_entries = {
            (entry.date, entry.meal_type): entry
            for entry in current_plan.meal_plan_entry
        }

        for entry in overlapping_doc.meal_plan_entry:
            if start_date <= str(entry.date) <= end_date:
                key = (entry.date, entry.meal_type)
                if key not in existing_entries:
                    current_plan.append("meal_plan_entry", {
                        "date": entry.date,
                        "meal_id": entry.meal_id,
                        "meal_name": entry.meal_name,
                        "meal_type": entry.meal_type
                })

        # You can break if you want only the first match
        break

    current_plan.save(ignore_permissions=True)
    populate_daily_meal_costs(current_plan)
    populate_shopping_list_from_meal_plan(current_plan)


    return {"message": "Meal plan data copied from overlapping plan."}

def populate_daily_meal_costs(plan_doc):
    # Clear existing costs
    plan_doc.set("daily_meal_costs", [])

    # Map to hold total cost per date
    cost_per_date = {}

    # Get total servings
    total_servings = plan_doc.total_servings or 1

    # Cache meal costs
    meal_cost_map = {}
    meal_ids = list({e.meal_id for e in plan_doc.meal_plan_entry})
    if meal_ids:
        meal_docs = frappe.get_all("Meals", filters={"meal_id": ["in", meal_ids]}, fields=["meal_id", "total_meal_cost"])
        meal_cost_map = {m.meal_id: m.total_meal_cost for m in meal_docs}

    # Accumulate daily costs
    for entry in plan_doc.meal_plan_entry:
        meal_cost = meal_cost_map.get(entry.meal_id, 0)
        cost = meal_cost * total_servings
        cost_per_date[entry.date] = cost_per_date.get(entry.date, 0) + cost
        # Debug: Log cost calculation for each entry
        frappe.logger().info(f"Processing {entry.meal_id} on {entry.date}: Cost per meal = {meal_cost}, Servings = {total_servings}, Total Cost = {cost}")

    # Fill daily_meal_costs child table
    total_plan_cost = 0  # Initialize the total meal plan cost variable
    for date, total_cost in sorted(cost_per_date.items()):
        plan_doc.append("daily_meal_costs", {
            "date": date,
            "meal_cost": total_cost
        })
        total_plan_cost += total_cost  # Accumulate the total meal plan cost
        # Debug: Log what is being appended to the daily_meal_costs
        frappe.logger().info(f"Appending total cost for {date}: {total_cost}")

    # Update the total meal plan cost field
    plan_doc.total_meal_plan_cost = total_plan_cost
    frappe.logger().info(f"Total meal plan cost updated: {total_plan_cost}")

    # Save the updated document to ensure the changes are persisted
    plan_doc.save(ignore_permissions=True)
    # Debug: Log successful save
    frappe.logger().info(f"Meal Plan {plan_doc.name} updated with daily costs and total meal plan cost.")


def populate_shopping_list_from_meal_plan(plan_doc):
    """
    Populates the Shopping List from the meals in the given Meal Plan document.
    Quantities are rounded up to the next whole integer for easier purchasing.
    """
    total_individuals = plan_doc.total_individuals or 1
    total_servings = plan_doc.total_servings or 1

    # Step 1: Prepare meal data for reusing fetch logic
    meal_data = []
    for entry in plan_doc.meal_plan_entry:
        meal_data.append({
            "meal_id": entry.meal_id,
            "selected_percentage": entry.selected_percentage or 0  # Only used for LSG
        })

    # Step 2: Reuse logic from fetch_ingredients
    ingredient_list = fetch_ingredients(
        meal_data=json.dumps(meal_data),
        total_individuals=total_individuals,
        total_servings=total_servings
    )

    # Step 3: Write to Shopping List table
    for ingredient in ingredient_list:
        # Round quantity up to next whole integer for easier purchasing
        rounded_qty = math.ceil(ingredient["qty"])
        
        existing = frappe.get_all(
            "Shopping List",
            filters={
                "meal_plan_link": plan_doc.name,
                "item_code": ingredient["ingredient"]
            },
            fields=["name"]
        )

        if existing:
            # Update quantity and cost
            shopping_doc = frappe.get_doc("Shopping List", existing[0].name)
            shopping_doc.qty = rounded_qty
            shopping_doc.cost = ingredient["cost"]
            shopping_doc.unit_of_measure = ingredient["unit_of_measure"]
            shopping_doc.save(ignore_permissions=True)
            frappe.logger().info(f"Updated Shopping List item {ingredient['ingredient']} with rounded up qty {rounded_qty}")
        else:
            # Insert new entry
            frappe.get_doc({
                "doctype": "Shopping List",
                "item_code": ingredient["ingredient"],
                "qty": rounded_qty,
                "unit_of_measure": ingredient["unit_of_measure"],
                "cost": ingredient["cost"],
                "meal_plan_link": plan_doc.name
            }).insert(ignore_permissions=True)
            frappe.logger().info(f"Created Shopping List item {ingredient['ingredient']} with rounded up qty {rounded_qty}")

    frappe.logger().info(f"Shopping list populated for meal plan {plan_doc.name}.")