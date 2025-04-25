# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ShoppingList(Document):
     def on_submit(self):
        if not self.packing_list:
            frappe.throw("Packing List not linked!")

        packing_list_doc = frappe.get_doc("Packing List", self.packing_list)

        # Clear existing items (optional)
        packing_list_doc.items = []

        for item in self.shopping_details:
                packing_list_doc.append("shopping_list", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "qty": item.qty,
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
            "qty": item.qty,
            "schedule_date": frappe.utils.nowdate(),
            "warehouse": default_warehouse,
            "target_warehouse":default_warehouse,
            
        })

    mr.insert(ignore_permissions=True)
    return mr.name


