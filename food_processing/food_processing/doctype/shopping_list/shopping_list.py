# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import math
from frappe.utils import nowdate

class ShoppingList(Document):
     def on_submit(self):
        if not self.packing_list:
            return

        packing_list_doc = frappe.get_doc("Packing List", self.packing_list)

        packing_list_doc.shopping_list = []

        for item in self.shopping_details:
            rounded_qty = math.ceil(float(item.qty))
            frappe.msgprint(f"Copying {item.item_name} with qty: {rounded_qty}")
            packing_list_doc.append("shopping_list", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": rounded_qty,
                "cost": item.cost
            })


        packing_list_doc.save()
        frappe.msgprint("Items copied to Packing List.")

pass

@frappe.whitelist()
def create_material_request(shopping_list_name):
    shopping_list = frappe.get_doc("Shopping List", shopping_list_name)

    if not shopping_list.shopping_details:
        frappe.throw("No items found in Shopping Details.")

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.schedule_date = frappe.utils.nowdate()
    mr.custom_shopping_list = shopping_list.name

    default_warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")

    if not default_warehouse:
        frappe.throw("Please set a Default Warehouse in Stock Settings.")

    for item in shopping_list.shopping_details:
        mr.append("items", {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "qty": math.ceil(float(item.qty)),
            "schedule_date": frappe.utils.nowdate(),
            "warehouse": default_warehouse,
            "target_warehouse":default_warehouse,
            
        })

    mr.insert(ignore_permissions=True)
    return mr.name

@frappe.whitelist()
def create_daily_meal_issue(meal_plan_name, meal_date=None, warehouse=None):
    if not meal_date:
        meal_date = nowdate()

    if not warehouse:
        warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    if not warehouse:
        frappe.throw("Please set a Default Warehouse in Stock Settings or choose one manually.")

    # Get meal entries for the specified date
    meal_entries = frappe.get_all(
        "Meal Plan Entry",
        filters={"parent": meal_plan_name, "date": meal_date},
        fields=["meal_id", "name", "date"]
    )

    if not meal_entries:
        frappe.throw(f"No meal entries found for date {meal_date} in Meal Plan '{meal_plan_name}'.")

    frappe.msgprint(f"Found {len(meal_entries)} meal entries for {meal_date}")

    ingredient_totals = {}
    processed_meals = 0
    processed_recipes = 0
    matched_meals = 0
    matched_recipes = 0

    for entry in meal_entries:
        meal_custom_id = entry.meal_id
        frappe.msgprint(f"Processing Meal Plan Entry ID: {entry.name} with meal_id: {meal_custom_id}")

        # Try exact, stripped, and case-insensitive matching
        meals = frappe.get_all("Meals", filters={"meal_id": meal_custom_id}, fields=["name"])
        if not meals:
            meals = frappe.get_all("Meals", filters={"meal_id": meal_custom_id.strip()}, fields=["name"])
        if not meals:
            all_meals = frappe.get_all("Meals", fields=["name", "meal_id"])
            meals = [m for m in all_meals if m.meal_id and m.meal_id.lower().strip() == meal_custom_id.lower().strip()]

        if not meals:
            frappe.msgprint(f"❗ No Meal found for meal_id: '{meal_custom_id}'")
            continue

        matched_meals += len(meals)

        for meal_doc in meals:
            try:
                meal = frappe.get_doc("Meals", meal_doc.name)
                processed_meals += 1
                frappe.msgprint(f"✅ Found meal: {meal.name}")

                if not meal.recipes:
                    frappe.msgprint(f"⚠️ Meal '{meal.name}' has no recipes.")
                    continue

                for recipe_link in meal.recipes:
                    if not recipe_link.recipe_name:
                        frappe.msgprint(f"⚠️ Empty recipe link in meal: {meal.name}")
                        continue

                    try:
                        recipe = frappe.get_doc("Recipe", recipe_link.recipe_name)
                        processed_recipes += 1
                        frappe.msgprint(f"✅ Found recipe: {recipe.name}")

                        if not recipe.ingredients:
                            frappe.msgprint(f"⚠️ Recipe '{recipe.name}' has no ingredients.")
                            continue

                        matched_recipes += 1

                        for ing in recipe.ingredients:
                            if not ing.ingredient:
                                continue

                            qty = float(ing.qty or 0)
                            if qty > 0:
                                ingredient_totals.setdefault(ing.ingredient, 0)
                                ingredient_totals[ing.ingredient] += qty
                                frappe.msgprint(f"🔹 Ingredient: {ing.ingredient}, Qty: {qty}")
                            else:
                                frappe.msgprint(f"⚠️ Ingredient '{ing.ingredient}' has zero quantity.")

                    except frappe.DoesNotExistError:
                        frappe.msgprint(f"❗ Recipe '{recipe_link.recipe_name}' not found.")
                        continue

            except frappe.DoesNotExistError:
                frappe.msgprint(f"❗ Meal '{meal_doc.name}' not found.")
                continue

    # Summary diagnostics
    frappe.msgprint(f"📋 Summary for {meal_date}:\n- Processed {processed_meals} meals\n- Processed {processed_recipes} recipes\n- Matched {matched_meals} meals\n- Matched {matched_recipes} recipes")

    if not ingredient_totals:
        frappe.throw(f"No ingredients found for the selected meals and recipes on {meal_date}.\n"
                     f"Processed {processed_meals} meals and {processed_recipes} recipes.\n"
                     f"Check that meals link to recipes and recipes contain ingredients with positive quantities.")

    # Create stock entry
    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.purpose = "Material Issue"
    stock_entry.stock_entry_type = "Material Issue"
    stock_entry.custom_meal_plan = meal_plan_name
    stock_entry.custom_meal_date = meal_date

    for item_code, total_qty in ingredient_totals.items():
        if total_qty > 0:
            stock_entry.append("items", {
                "item_code": item_code,
                "qty": math.ceil(total_qty),
                "s_warehouse": warehouse
            })

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()

    frappe.msgprint(f"✅ Stock Entry {stock_entry.name} created with {len(ingredient_totals)} ingredients.")
    return stock_entry.name
