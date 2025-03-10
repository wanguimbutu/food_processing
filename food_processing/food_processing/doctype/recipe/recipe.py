# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document


class Recipe(Document):
	pass

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
