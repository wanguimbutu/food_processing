# Copyright (c) 2025, wanguimbutu and contributors
# For license information, please see license.txt


import frappe
def execute(filters=None):
    

    shopping_list_id = filters.get("shopping_list")
    if not shopping_list_id:
        frappe.throw("Please select a Shopping List.")


    columns = [
        {"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item"},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data"},
        {"label": "Requested Qty", "fieldname": "requested_qty", "fieldtype": "Float"},
        {"label": "Available Qty", "fieldname": "available_qty", "fieldtype": "Float"},
        {"label": "Shortage", "fieldname": "shortage", "fieldtype": "Float"},
        {"label": "Surplus", "fieldname": "surplus", "fieldtype": "Float"}
    ]

    data = []

    # Fetch items from Shopping Details based on the selected shopping list
    shopping_items = frappe.get_all(
        "Shopping Details",
        filters={"parent": shopping_list_id},
        fields=["item_code", "item_name", "qty"]
    )

    for item in shopping_items:
        item_code = item.item_code
        item_name = item.item_name
        requested_qty = item.qty

        # Get stock quantity from Stock Ledger Entry
        stock_qty = frappe.db.sql("""
            SELECT SUM(actual_qty) AS actual_qty
            FROM `tabBin`
            WHERE item_code = %s
        """, (item_code,), as_dict=True)[0].actual_qty or 0

        # Calculate shortage
        if stock_qty < requested_qty:
            shortage = requested_qty - stock_qty
            surplus = 0
        else:
            shortage = 0
            surplus =stock_qty - requested_qty

        # Append data for each item
        data.append({
            "item_code": item_code,
            "item_name": item_name,
            "requested_qty": requested_qty,
            "available_qty": stock_qty,
            "shortage": shortage,
            "surplus": surplus
        })

    return columns, data

@frappe.whitelist()
def create_material_request(shopping_list):
    if not shopping_list:
        frappe.throw("No shopping list provided")

    # Get items with shortage
    shopping_items = frappe.get_all(
        "Shopping Details",
        filters={"parent": shopping_list},
        fields=["item_code", "qty"]
    )

    items_to_request = []

    for item in shopping_items:
        stock_qty = frappe.db.sql("""
            SELECT SUM(actual_qty) AS actual_qty
            FROM `tabBin`
            WHERE item_code = %s
        """, (item.item_code,), as_dict=True)[0].actual_qty or 0

        shortage = item.qty - stock_qty
        if shortage > 0:
            items_to_request.append({
                "item_code": item.item_code,
                "qty": shortage,
                "schedule_date": frappe.utils.nowdate()
            })

    if not items_to_request:
        frappe.throw("No shortage items to request.")

    mr = frappe.new_doc("Material Request")
    mr.material_request_type = "Purchase"
    mr.company = frappe.defaults.get_user_default("Company")

    for item in items_to_request:
        mr.append("items", item)

    mr.save()
    frappe.msgprint("Material Request created")
    return mr.name
