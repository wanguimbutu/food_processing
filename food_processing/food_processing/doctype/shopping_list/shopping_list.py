# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import math
from frappe.utils import nowdate
import math

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
            "target_warehouse": default_warehouse,
        })

    doc = mr.as_dict()
    doc["__islocal"] = 1   
    return doc

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

    # Get meal entries for the specific date
    meal_entries = frappe.get_all(
        "Meal Plan Entry",
        filters={"parent": meal_plan_name, "date": meal_date},
        fields=["meal_id", "name", "date"]
    )

    if not meal_entries:
        frappe.throw(f"No meal entries found for date {meal_date} in Meal Plan '{meal_plan_name}'.")

    frappe.msgprint(f"Found {len(meal_entries)} meal entries for {meal_date}")

    # Build normalized meal lookup for better matching
    all_meals = frappe.get_all("Meals", fields=["name", "meal_id"])
    meal_lookup = {
        m.meal_id.lower().strip(): m.name for m in all_meals if m.meal_id
    }

    ingredient_totals = {}
    processed_meals = 0
    processed_recipes = 0
    matched_meals = 0

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

            # Debug: Check what's in the meal document
            frappe.msgprint(f"🔍 Meal document loaded: {meal.name}")
            frappe.msgprint(f"🔍 Available fields: {list(meal.as_dict().keys())}")
            
            # Access Recipe Details child table - get the actual link field value
            recipe_details = frappe.get_all(
                "Recipe Details",
                filters={"parent": meal.name},
                fields=["name", "recipe_name"]  # recipe_name contains the actual document name like REC-0012
            )
            
            if not recipe_details:
                frappe.msgprint(f"⚠️ Meal '{meal.name}' has no Recipe Details")
                continue

            frappe.msgprint(f"📋 Processing {len(recipe_details)} recipes for meal: {meal.name}")

            # Debug: Show what's in each recipe record
            for i, recipe_link in enumerate(recipe_details):
                frappe.msgprint(f"🔍 Recipe {i+1}: {recipe_link}")

            for recipe_link in recipe_details:
                # Debug: Check all available fields in recipe_link
                frappe.msgprint(f"🔍 Recipe link fields: {list(recipe_link.keys())}")
                frappe.msgprint(f"🔍 Recipe link data: {recipe_link}")
                
                # Get the actual document name from the link field
                recipe_reference = recipe_link.get('recipe_name')
                if not recipe_reference:
                    frappe.msgprint(f"❌ No recipe_name found in recipe link")
                    continue
                
                frappe.msgprint(f"✅ Found recipe document name: {recipe_reference}")

                try:
                    # Direct lookup using the document name (like REC-0012)
                    recipe = frappe.get_doc("Recipe", recipe_reference)
                    processed_recipes += 1
                    frappe.msgprint(f"✅ Processing recipe: {recipe.name} (Title: {getattr(recipe, 'title', 'No title')})")

                    # Debug: Check recipe fields
                    frappe.msgprint(f"🔍 Recipe fields: {list(recipe.as_dict().keys())}")

                    if not hasattr(recipe, 'ingredients'):
                        frappe.msgprint(f"❌ Recipe '{recipe.name}' has no 'ingredients' field")
                        continue
                        
                    if not recipe.ingredients:
                        frappe.msgprint(f"⚠️ Recipe '{recipe.name}' has empty ingredients field")
                        continue

                    # Get recipe serving size (check if servings field exists, default to 1)
                    recipe_servings = float(getattr(recipe, 'servings', None) or 1)
                    frappe.msgprint(f"🍽️ Recipe '{recipe.name}' servings: {recipe_servings}")

                    frappe.msgprint(f"📋 Processing {len(recipe.ingredients)} ingredients for recipe: {recipe.name}")

                    for ing in recipe.ingredients:
                        # Debug: Check ingredient fields
                        ing_dict = ing.as_dict()
                        frappe.msgprint(f"🔍 Ingredient fields: {list(ing_dict.keys())}")
                        frappe.msgprint(f"🔍 Ingredient data: {ing_dict}")

                        # Try different field names for ingredient reference
                        ingredient_code = None
                        if hasattr(ing, 'ingredient') and ing.ingredient:
                            ingredient_code = ing.ingredient
                        elif hasattr(ing, 'item_code') and ing.item_code:
                            ingredient_code = ing.item_code
                        elif hasattr(ing, 'item') and ing.item:
                            ingredient_code = ing.item
                        
                        if not ingredient_code:
                            frappe.msgprint(f"⚠️ Empty ingredient reference in recipe: {recipe.name}")
                            continue

                        # Try different field names for quantity
                        base_qty = 0
                        if hasattr(ing, 'qty') and ing.qty:
                            base_qty = float(ing.qty)
                        elif hasattr(ing, 'quantity') and ing.quantity:
                            base_qty = float(ing.quantity)
                        elif hasattr(ing, 'amount') and ing.amount:
                            base_qty = float(ing.amount)
                        
                        if base_qty <= 0:
                            frappe.msgprint(f"⚠️ Ingredient '{ingredient_code}' has zero or negative quantity: {base_qty}")
                            continue

                        try:
                            # Check if the ingredient is a valid stock item
                            item_doc = frappe.get_doc("Item", ingredient_code)
                            if not item_doc.is_stock_item:
                                frappe.msgprint(f"⚠️ Skipping '{ingredient_code}' - not a stock item")
                                continue
                            
                            # Calculate quantity per serving, then multiply by total individuals
                            qty_per_serving = base_qty / recipe_servings
                            total_qty = qty_per_serving * total_individuals
                            
                            ingredient_totals.setdefault(ingredient_code, 0)
                            ingredient_totals[ingredient_code] += total_qty
                            
                            frappe.msgprint(f"🔹 Ingredient: {ingredient_code}")
                            frappe.msgprint(f"   Base qty: {base_qty}, Per serving: {qty_per_serving:.3f}, Total for {total_individuals} individuals: {total_qty:.3f}")
                        
                        except frappe.DoesNotExistError:
                            frappe.msgprint(f"❌ Item '{ingredient_code}' not found in system")
                            continue

                except frappe.DoesNotExistError:
                    frappe.msgprint(f"❌ Recipe '{recipe_reference}' not found")
                    continue
                except Exception as e:
                    frappe.msgprint(f"❌ Error processing recipe '{recipe_reference}': {str(e)}")
                    continue

        except frappe.DoesNotExistError:
            frappe.msgprint(f"❗ Meal '{meal_name}' not found.")
            continue
        except Exception as e:
            frappe.msgprint(f"❗ Error processing meal '{meal_name}': {str(e)}")
            continue

    # Summary
    frappe.msgprint(
        f"📋 Summary for {meal_date}:\n"
        f"- Total Individuals: {total_individuals}\n"
        f"- Meal Entries: {len(meal_entries)}\n"
        f"- Matched Meals: {matched_meals}\n"
        f"- Processed Meals: {processed_meals}\n"
        f"- Processed Recipes: {processed_recipes}\n"
        f"- Unique Ingredients: {len(ingredient_totals)}"
    )

    if not ingredient_totals:
        frappe.throw(f"No ingredients found for the selected meals and recipes on {meal_date}.\n"
                     f"Processed {processed_meals} meals and {processed_recipes} recipes.\n"
                     f"Please check:\n"
                     f"1. Meals have recipes linked properly\n"
                     f"2. Recipes contain ingredients with positive quantities\n"
                     f"3. Ingredients are valid stock items\n"
                     f"4. Field names match your doctype structure")

 
    # Create Stock Entry
    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.purpose = "Material Issue"
    stock_entry.stock_entry_type = "Material Issue"
    stock_entry.custom_meal_plan = meal_plan_name
    stock_entry.custom_meal_date = meal_date

    for item_code, total_qty in ingredient_totals.items():
        # Use math.ceil to round up to nearest integer
        # 2.2 becomes 3, 1.5 becomes 2, 1.1 becomes 2
        rounded_qty = math.ceil(float(total_qty))
        
        if rounded_qty > 0:
            stock_entry.append("items", {
                "item_code": item_code,
                "qty": rounded_qty,
                "s_warehouse": warehouse
            })

    stock_entry.insert(ignore_permissions=True)
    # stock_entry.submit()

    frappe.msgprint(f"✅ Stock Entry {stock_entry.name} created with {len(ingredient_totals)} ingredients for {total_individuals} individuals.")
    return stock_entry.name