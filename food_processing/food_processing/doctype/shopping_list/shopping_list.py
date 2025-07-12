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
    from frappe.utils import nowdate

    if not meal_date:
        meal_date = nowdate()

    if not warehouse:
        warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
    if not warehouse:
        frappe.throw("Please set a Default Warehouse in Stock Settings or choose one manually.")

    # Get the meal plan document to access total individuals
    meal_plan = frappe.get_doc("Meal Plan", meal_plan_name)
    total_individuals = float(meal_plan.total_individuals or 1)  # Default to 1 if not set
    
    frappe.msgprint(f"Meal Plan: {meal_plan_name}, Total Individuals: {total_individuals}")

    meal_entries = frappe.get_all(
        "Meal Plan Entry",
        filters={"parent": meal_plan_name, "date": meal_date},
        fields=["meal_id", "name", "date"]
    )

    if not meal_entries:
        frappe.throw(f"No meal entries found for date {meal_date} in Meal Plan '{meal_plan_name}'.")

    frappe.msgprint(f"Found {len(meal_entries)} meal entries for {meal_date}")

    # Build normalized meal lookup
    all_meals = frappe.get_all("Meals", fields=["name", "meal_id"])
    meal_lookup = {
        m.meal_id.lower().strip(): m.name for m in all_meals if m.meal_id
    }

    ingredient_totals = {}
    processed_meals = 0
    processed_recipes = 0
    matched_meals = 0
    matched_recipes = 0

    for entry in meal_entries:
        raw_meal_id = entry.meal_id or ""
        normalized_meal_id = raw_meal_id.lower().strip()

        frappe.msgprint(f"Looking up meal_id: '{raw_meal_id}' -> normalized: '{normalized_meal_id}'")

        if normalized_meal_id not in meal_lookup:
            frappe.msgprint(f"❌ No Meal found for normalized meal_id: '{normalized_meal_id}'")
            continue

        meal_name = meal_lookup[normalized_meal_id]
        frappe.msgprint(f"✅ Found meal: {meal_name}")
        matched_meals += 1

        try:
            meal = frappe.get_doc("Meals", meal_name)
            processed_meals += 1

            if not meal.recipes:
                frappe.msgprint(f"⚠️ Meal '{meal.name}' has no recipes.")
                continue

            for recipe_link in meal.recipes:
                if not recipe_link.recipe_name:
                    frappe.msgprint(f"⚠️ Empty recipe link in meal: {meal.name}")
                    continue

                # 🔍 Find recipe by recipe_name field with fuzzy matching
                recipe = None
                recipe_found = False
                
                if hasattr(recipe_link, 'recipe_name') and recipe_link.recipe_name:
                    search_name = recipe_link.recipe_name.strip()
                    
                    # Method 1: Exact match
                    recipe_docs = frappe.get_all("Recipe", 
                                                filters={"recipe_name": search_name}, 
                                                fields=["name", "recipe_name"])
                    if recipe_docs:
                        recipe = frappe.get_doc("Recipe", recipe_docs[0].name)
                        recipe_found = True
                        frappe.msgprint(f"✅ Found recipe (exact): '{recipe.recipe_name}' (Document: {recipe.name})")
                    else:
                        # Method 2: Case-insensitive match
                        all_recipes = frappe.get_all("Recipe", fields=["name", "recipe_name"])
                        for r in all_recipes:
                            if r.recipe_name and r.recipe_name.lower().strip() == search_name.lower():
                                recipe = frappe.get_doc("Recipe", r.name)
                                recipe_found = True
                                frappe.msgprint(f"✅ Found recipe (case-insensitive): '{recipe.recipe_name}' (Document: {recipe.name})")
                                break
                        
                        if not recipe_found:
                            # Method 3: Partial match
                            for r in all_recipes:
                                if r.recipe_name and (search_name.lower() in r.recipe_name.lower() or 
                                                    r.recipe_name.lower() in search_name.lower()):
                                    recipe = frappe.get_doc("Recipe", r.name)
                                    recipe_found = True
                                    frappe.msgprint(f"✅ Found recipe (partial match): '{recipe.recipe_name}' (Document: {recipe.name}) - searched for '{search_name}'")
                                    break
                        
                        if not recipe_found:
                            # Show available recipes for debugging
                            available_recipes = [r.recipe_name for r in all_recipes if r.recipe_name]
                            frappe.msgprint(f"❌ Recipe '{search_name}' not found. Available recipes: {available_recipes[:10]}...")
                
                # Method 4: Direct lookup by document name (fallback)
                if not recipe_found and hasattr(recipe_link, 'recipe') and recipe_link.recipe:
                    try:
                        recipe = frappe.get_doc("Recipe", recipe_link.recipe)
                        recipe_found = True
                        frappe.msgprint(f"✅ Found recipe by document name: {recipe.name} ({getattr(recipe, 'recipe_name', 'No recipe_name field')})")
                    except frappe.DoesNotExistError:
                        frappe.msgprint(f"❌ Recipe document not found: {recipe_link.recipe}")
                
                if not recipe_found:
                    continue
                processed_recipes += 1
                matched_recipes += 1
                frappe.msgprint(f"✅ Processing recipe: {getattr(recipe, 'recipe_name', recipe.name)}")

                if not recipe.ingredients:
                    frappe.msgprint(f"⚠️ Recipe '{getattr(recipe, 'recipe_name', recipe.name)}' has no ingredients.")
                    continue

                # Get recipe serving size (check if servings field exists, default to 1)
                recipe_servings = float(getattr(recipe, 'servings', None) or 1)
                frappe.msgprint(f"🍽️ Recipe servings: {recipe_servings}")

                for ing in recipe.ingredients:
                    if not ing.ingredient:
                        continue

                    base_qty = float(ing.qty or 0)
                    if base_qty > 0:
                        # Check if the ingredient is a valid stock item
                        item_doc = frappe.get_doc("Item", ing.ingredient)
                        if not item_doc.is_stock_item:
                            frappe.msgprint(f"⚠️ Skipping '{ing.ingredient}' - not a stock item")
                            continue
                        
                        # Calculate quantity per serving, then multiply by total individuals
                        qty_per_serving = base_qty / recipe_servings
                        total_qty = qty_per_serving * total_individuals
                        
                        ingredient_totals.setdefault(ing.ingredient, 0)
                        ingredient_totals[ing.ingredient] += total_qty
                        
                        frappe.msgprint(f"🔹 Ingredient: {ing.ingredient}")
                        frappe.msgprint(f"   Base qty: {base_qty}, Per serving: {qty_per_serving:.3f}, Total for {total_individuals} individuals: {total_qty:.3f}")
                    else:
                        frappe.msgprint(f"⚠️ Ingredient '{ing.ingredient}' has zero quantity.")

        except frappe.DoesNotExistError:
            frappe.msgprint(f"❗ Meal '{meal_name}' not found.")
            continue

    # Summary
    frappe.msgprint(
        f"📋 Summary for {meal_date}:\n"
        f"- Total Individuals: {total_individuals}\n"
        f"- Entries: {len(meal_entries)}\n"
        f"- Matched Meals: {matched_meals}\n"
        f"- Processed Meals: {processed_meals}\n"
        f"- Matched Recipes: {matched_recipes}\n"
        f"- Processed Recipes: {processed_recipes}"
    )

    if not ingredient_totals:
        frappe.throw(f"No ingredients found for the selected meals and recipes on {meal_date}.\n"
                     f"Processed {processed_meals} meals and {processed_recipes} recipes.\n"
                     f"Check that meals link to recipes (via recipe_name field), and that recipes contain ingredients with positive quantities.")

    # Create Stock Entry
    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.purpose = "Material Issue"
    stock_entry.stock_entry_type = "Material Issue"
    stock_entry.custom_meal_plan = meal_plan_name
    stock_entry.custom_meal_date = meal_date

    for item_code, total_qty in ingredient_totals.items():
        safe_qty = round(float(total_qty), 3)
        if safe_qty > 0:
            stock_entry.append("items", {
                "item_code": item_code,
                "qty": safe_qty,
                "s_warehouse": warehouse
            })

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()

    frappe.msgprint(f"✅ Stock Entry {stock_entry.name} created with {len(ingredient_totals)} ingredients for {total_individuals} individuals.")
    return stock_entry.name