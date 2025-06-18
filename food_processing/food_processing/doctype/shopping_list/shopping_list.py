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

    meal_ids = frappe.get_all(
        "Meal Plan Entry",
        filters={"parent": meal_plan_name, "date": meal_date},
        pluck="meal_id" 
    )
    if not meal_ids:
        frappe.throw(f"No meal entries found for {meal_date} in Meal Plan {meal_plan_name}.")

    ingredient_totals = {}

    for meal_custom_id in meal_ids:
        meals = frappe.get_all("Meals", filters={"meal_id": meal_custom_id}, fields=["name"])
        if not meals:
            frappe.msgprint(f"No Meal found for meal_id: {meal_custom_id}")
            continue

        meal = frappe.get_doc("Meals", meals[0].name)

        for recipe_link in meal.recipes:
            if not recipe_link.recipe_name:
                continue
            try:
                recipe = frappe.get_doc("Recipe", recipe_link.recipe_name)
                for ing in recipe.ingredients:
                    if not ing.ingredient:
                        continue
                    ingredient_code = ing.ingredient
                    qty = float(ing.qty or 0)
                    ingredient_totals.setdefault(ingredient_code, 0)
                    ingredient_totals[ingredient_code] += qty
            except frappe.DoesNotExistError:
                frappe.msgprint(f"Recipe {recipe_link.recipe_name} not found.")
                continue

    if not ingredient_totals:
        frappe.throw("No ingredients found for the selected meals and recipes.")

    stock_entry = frappe.new_doc("Stock Entry")
    stock_entry.purpose = "Material Issue"
    stock_entry.stock_entry_type = "Material Issue"
    stock_entry.custom_meal_plan = meal_plan_name  
    stock_entry.custom_meal_date = meal_date     

    for item_code, total_qty in ingredient_totals.items():
        stock_entry.append("items", {
            "item_code": item_code,
            "qty": math.ceil(total_qty),
            "s_warehouse": warehouse
        })

    stock_entry.insert(ignore_permissions=True)
    stock_entry.submit()

    return stock_entry.name
