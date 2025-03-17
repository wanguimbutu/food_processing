# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Meals(Document):
	pass


@frappe.whitelist()
def update_total_meal_cost(doc, method):
    total_cost = sum(recipe.cost_per_recipe for recipe in doc.recipes)
    doc.total_meal_cost = total_cost
