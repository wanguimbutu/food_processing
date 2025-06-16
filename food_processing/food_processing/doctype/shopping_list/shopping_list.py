# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import math

class ShoppingList(Document):
     def on_submit(self):
        if not self.packing_list:
            # Packing List not linked, skip processing
            return

        packing_list_doc = frappe.get_doc("Packing List", self.packing_list)

        # Clear existing shopping_list items (optional)
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

# Add this method to your shopping_list.py file

@frappe.whitelist()
def create_daily_material_issue(shopping_list_name, issue_date, meal_plan,target_warehouse=None):
    """
    Creates a Material Issue (Stock Entry) for daily meal requirements
    based on the meal plan for a specific date
    """
    try:
        shopping_list = frappe.get_doc("Shopping List", shopping_list_name)
        meal_plan_doc = frappe.get_doc("Meal Plan", meal_plan)

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.posting_date = issue_date
        stock_entry.posting_time = frappe.utils.nowtime()
        stock_entry.set_stock_entry_type()

        if hasattr(stock_entry, 'custom_shopping_list'):
            stock_entry.custom_shopping_list = shopping_list_name
        if hasattr(stock_entry, 'custom_meal_plan'):
            stock_entry.custom_meal_plan = meal_plan
        if hasattr(stock_entry, 'custom_issue_date'):
            stock_entry.custom_issue_date = issue_date

        daily_items = get_daily_meal_items(meal_plan, None, issue_date)

        if not daily_items:
            total_entries = frappe.db.count("Meal Plan Entry", {"parent": meal_plan})
            frappe.msgprint(f"""
                No items found for the selected date and meal plan.<br><br>
                <b>Debugging Information:</b><br>
                - Meal Plan: {meal_plan}<br>
                - Date: {issue_date}<br>
                - Total entries in meal plan: {total_entries}<br><br>
                Please verify:<br>
                1. The meal plan has entries for the selected date<br>
                2. The meals have recipes assigned<br>
                3. The recipes have ingredients defined
            """, title="No Items Found", indicator="orange")
            return None

        item_append_count = 0
        for item in daily_items:
            if item.get("qty", 0) > 0:
                try:
                    stock_entry.append("items", {
                        "item_code": item.get("item_code"),
                        "qty": item.get("qty"),
                        "uom": item.get("unit_of_measure", "Nos"),
                        "s_warehouse": item.get("source_warehouse") or get_default_warehouse(),
                        "t_warehouse": target_warehouse,
                        "cost_center": get_default_cost_center(),
                        # "expense_account": get_default_expense_account(item.get("item_code"))  # Optional
                    })
                    item_append_count += 1
                except Exception as append_error:
                    frappe.log_error(
                        title="Stock Entry Append Error",
                        message=f"{str(append_error)}\n{frappe.as_json(item)}"
                    )

        if not stock_entry.items:
            frappe.msgprint("No valid items with quantities > 0 were found for this meal plan and date.",
                            title="No Valid Items", indicator="orange")
            return None

        try:
            stock_entry.insert()
            frappe.msgprint(f"✅ Material Issue <b>{stock_entry.name}</b> created successfully with <b>{item_append_count}</b> items.",
                            title="Success", indicator="green")
            return stock_entry.name
        except Exception as e:
            frappe.log_error("Material Issue Insert Error", frappe.get_traceback())
            frappe.throw("Failed to create the Material Issue. Please check the Error Log.")

    except Exception as e:
        frappe.log_error("Daily Material Issue Fatal Error", frappe.get_traceback())
        frappe.throw(f"Error creating daily material issue: {str(e)}")

def get_daily_meal_items(meal_plan, day_of_week, issue_date):
    """
    Get items required for meals on a specific day based on meal plan
    """
    items = []

    #frappe.log_error(f"Debug - Meal Plan: {meal_plan}, Date: {issue_date}", "Daily Material Issue Debug")

    # Get meal entries for this date
    meal_entries = frappe.get_all(
        "Meal Plan Entry",
        filters={"parent": meal_plan, "date": issue_date},
        fields=["meal_type", "meal_id", "date"]
    )

   # frappe.log_error(f"Debug - Found {len(meal_entries)} meal entries: {meal_entries}", "Daily Material Issue Debug")

    if not meal_entries:
        all_dates = frappe.get_all(
            "Meal Plan Entry",
            filters={"parent": meal_plan},
            distinct=True,
            fields=["date"],
            order_by="date"
        )
        #frappe.log_error(f"Debug - Available dates in meal plan: {all_dates}", "Daily Material Issue Debug")
        return items

    for entry in meal_entries:
        meal_id_value = entry.get("meal_id")
        if not meal_id_value:
            continue

        # Look up the actual document name of the Meal using its custom meal_id field
        meal_name = frappe.db.get_value("Meals", {"meal_id": meal_id_value}, "name")
        if not meal_name:
            frappe.log_error(f"Meal with meal_id '{meal_id_value}' not found", "Daily Material Issue Debug")
            continue

       # frappe.log_error(f"Debug - Processing meal_id: {meal_id_value} -> {meal_name}", "Daily Material Issue Debug")

        # Load the actual Meal document
        try:
            meal_doc = frappe.get_doc("Meals", meal_name)
        except frappe.DoesNotExistError:
            frappe.log_error(f"Meal document not found: {meal_name}", "Daily Material Issue Debug")
            continue

        for recipe_row in meal_doc.recipes:
            recipe_name = recipe_row.recipe_name
            if not recipe_name or not frappe.db.exists("Recipe", recipe_name):
                frappe.log_error(f"Invalid or missing recipe: {recipe_name}", "Daily Material Issue Debug")
                continue

            #frappe.log_error(f"Debug - Processing recipe: {recipe_name}", "Daily Material Issue Debug")

            try:
                recipe_doc = frappe.get_doc("Recipe", recipe_name)
            except frappe.DoesNotExistError:
                frappe.log_error(f"Recipe not found: {recipe_name}", "Daily Material Issue Debug")
                continue

            for ing in recipe_doc.ingredients:
                if not ing.ingredient:
                    continue

                existing_item = next((item for item in items if item["item_code"] == ing.ingredient), None)

                if existing_item:
                    existing_item["qty"] += ing.qty or 0
                else:
                    items.append({
                        "item_code": ing.ingredient,
                        "qty": ing.qty or 0,
                        "uom": ing.unit_of_measure or "Nos",
                        "meal_type": entry.meal_type,
                        "meal_name": meal_doc.get("meal_name", meal_name),
                        "recipe": recipe_name
                    })

   # frappe.log_error(f"Debug - Final items list: {items}", "Daily Material Issue Debug")
    return items


def get_default_warehouse():
    """Get default warehouse for material issues"""
    # You can customize this based on your setup
    return frappe.db.get_single_value("Stock Settings", "default_warehouse") or "Stores - Company"

def get_default_cost_center():
    """Get default cost center"""
    # You can customize this based on your setup
    return frappe.db.get_value("Company", frappe.defaults.get_user_default("Company"), "cost_center")

def get_default_expense_account(item_code):
    """Get default expense account for an item"""
    # Try to get from item master first
    expense_account = frappe.db.get_value("Item", item_code, "expense_account")
    if expense_account:
        return expense_account
    
    # Fallback to default
    return frappe.db.get_single_value("Accounts Settings", "default_expense_account") or "Cost of Goods Sold - Company"

@frappe.whitelist()
def debug_meal_plan_structure(meal_plan, issue_date):
    """
    Debug function to check meal plan structure
    """
    result = {
        "meal_plan": meal_plan,
        "issue_date": issue_date,
        "meal_entries": [],
        "meals": [],
        "recipes": [],
        "ingredients": []
    }

    # Fetch all meal plan entries
    meal_entries = frappe.db.get_all(
        "Meal Plan Entry",
        filters={"parent": meal_plan},
        fields=["name", "meal_id", "date"],
        order_by="date"
    )
    result["meal_entries"] = meal_entries

    # Filter by issue date
    date_entries = [entry for entry in meal_entries if str(entry.date) == issue_date]

    for entry in date_entries:
        meal_id_value = entry.meal_id
        meal_name = frappe.db.get_value("Meals", {"meal_id": meal_id_value}, "name")
        result["meals"].append({
            "meal_id": meal_id_value,
            "meal_docname": meal_name,
            "exists": bool(meal_name)
        })

        if not meal_name:
            continue

        try:
            meal_doc = frappe.get_doc("Meals", meal_name)
        except frappe.DoesNotExistError:
            continue

        for recipe in meal_doc.recipes:
            recipe_name = recipe.recipe_name
            recipe_exists = frappe.db.exists("Recipe", recipe_name)
            result["recipes"].append({
                "recipe_name": recipe_name,
                "exists": bool(recipe_exists)
            })

            if not recipe_exists:
                continue

            ingredients = frappe.db.get_all(
                "Ingredient Details",
                filters={"parent": recipe_name},
                fields=["ingredient", "qty", "unit_of_measure"],
            )
            result["ingredients"].extend(ingredients)

    return result
