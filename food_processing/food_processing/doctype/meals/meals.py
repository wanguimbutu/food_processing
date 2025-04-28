# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname

class Meals(Document):
	pass


@frappe.whitelist()
def update_total_meal_cost(doc, method):
    total_cost = sum(recipe.cost_per_recipe for recipe in doc.recipes)
    doc.total_meal_cost = total_cost

@frappe.whitelist()
def generate_meal_id():
    return make_autoname('MEAL-.####')