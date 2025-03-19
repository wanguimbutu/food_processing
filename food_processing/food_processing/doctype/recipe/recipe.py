# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document


class Recipe(Document):
	pass

def before_save(doc, method):
    total_cost = 0

    for ingredient in doc.ingredients:
        ingredient_cost = (ingredient.cost or 0) * (ingredient.qty or 0)
        total_cost += ingredient_cost

    doc.total_cost = total_cost

    # Calculate cost per serving if servings_per_recipe is greater than zero
    if doc.servings_per_recipe and doc.servings_per_recipe > 0:
        doc.cost_per_serving = total_cost / doc.servings_per_recipe
    else:
        doc.cost_per_serving = 0  # Avoid division by zero

    frappe.logger().info(f"Recipe {doc.name}: Total Cost = {total_cost}, Cost per Serving = {doc.cost_per_serving}")


@frappe.whitelist()
def add_recipe_tags(recipe_name, tags):

    if not recipe_name or not tags:
        frappe.throw("Missing required parameters: 'recipe_name' or 'tags'")

    tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

    for tag in tags:
        if not frappe.db.exists("Tag", tag):
            tag_doc = frappe.get_doc({"doctype": "Tag", "name": tag})
            tag_doc.insert(ignore_permissions=True)

        
        if not frappe.db.exists("Tag Link", {"document_type": "Recipe", "document_name": recipe_name, "tag": tag}):
            tag_link = frappe.get_doc({
                "doctype": "Tag Link",
                "tag": tag,
                "document_type": "Recipe",
                "document_name": recipe_name
            })
            tag_link.insert(ignore_permissions=True)

    return {"status": "success", "tags_added": tags}

import json

@frappe.whitelist()
def get_recipe_with_dietary_substitutes(recipe_name, dietary_specification):
    """
    Fetches a recipe and applies ingredient substitutions based on dietary restrictions.
    """
    recipe = frappe.get_doc("Recipe", recipe_name)

    # Ensure dietary_specification is treated as a list
    if isinstance(dietary_specification, str):
        dietary_specification = json.loads(dietary_specification)  # Convert string to list

    for ingredient in recipe.ingredients:
        if ingredient.dietary_specification:
            ingredient_diet_specs = json.loads(ingredient.dietary_specification)

            if any(spec in dietary_specification for spec in ingredient_diet_specs):
                ingredient.ingredient = ingredient.substituted_ingredient
                ingredient.qty = ingredient.substituted_qty
                ingredient.unit_of_measure = ingredient.substituted_uom
                ingredient.is_substituted = True

    return recipe

import json

@frappe.whitelist()
def save_recipe(doc):
    if isinstance(doc, str):
        doc = json.loads(doc)  # Convert string to dictionary

    doc = frappe.get_doc(doc)  # Ensure it's a Frappe document
    doc.save()
    return doc

@frappe.whitelist()
def update_ingredient_prices(doc, method):
    """
    Updates ingredient cost and default unit of measure (UOM) in Recipe based on the latest Item details.
    Triggered before validation (before saving).
    """
    for ingredient in doc.ingredients:
        if ingredient.ingredient:
            # Fetch latest price from Item Price doctype
            item_price = frappe.db.get_value(
                "Item Price",
                {"item_code": ingredient.ingredient, "price_list": "Standard Selling"},
                "price_list_rate"
            )

            # Fetch default UOM from Item doctype
            default_uom = frappe.db.get_value("Item", ingredient.ingredient, "stock_uom")

            # Update cost field
            ingredient.cost = item_price if item_price else 0

            # Update UOM only if it's empty (allow manual override)
            if not ingredient.unit_of_measure:
                ingredient.unit_of_measure = default_uom
