import frappe
from frappe import _

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "meal_type",
            "label": _("Meal Type"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "ingredient",
            "label": _("Ingredient"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "fieldname": "ingredient_name",
            "label": _("Ingredient Name"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "uom",
            "label": _("UOM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 80
        },
        {
            "fieldname": "total_qty_required",
            "label": _("Total Qty Required"),
            "fieldtype": "Float",
            "width": 120,
            "precision": 3
        }
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    
    query = f"""
        SELECT 
            mpe.date,
            mpe.meal_type,
            CASE 
                WHEN ri.is_substituted = 1 THEN ri.substituted_ingredient
                ELSE ri.ingredient 
            END AS ingredient,
            CASE 
                WHEN ri.is_substituted = 1 THEN 
                    (SELECT item_name FROM `tabItem` WHERE name = ri.substituted_ingredient)
                ELSE ri.ingredient_name 
            END AS ingredient_name,
            CASE 
                WHEN ri.is_substituted = 1 THEN ri.substituted_uom
                ELSE ri.unit_of_measure 
            END AS uom,
            SUM(
                CASE 
                    WHEN ri.is_substituted = 1 THEN (ri.substituted_qty * mp.total_individuals)
                    ELSE (ri.qty * mp.total_individuals)
                END
            ) AS total_qty_required
        FROM 
            `tabMeal Plan Entry` mpe
        INNER JOIN 
            `tabMeal Plan` mp ON mpe.parent = mp.name
        INNER JOIN 
            `tabMeals` m ON mpe.meal_id = m.name
        INNER JOIN 
            `tabRecipe Details` rd ON rd.parent = m.name
        INNER JOIN 
            `tabRecipe` r ON r.name = rd.recipe_name
        INNER JOIN 
            `tabIngredient Details` ri ON ri.parent = r.name
        WHERE 
            mp.docstatus = 1
            AND (
                (ri.is_substituted = 0 AND ri.ingredient IS NOT NULL AND ri.qty > 0) 
                OR 
                (ri.is_substituted = 1 AND ri.substituted_ingredient IS NOT NULL AND ri.substituted_qty > 0)
            )
            {conditions}
        GROUP BY 
            mpe.date, mpe.meal_type, ingredient, ingredient_name, uom
        ORDER BY 
            mpe.date ASC, 
            mpe.meal_type ASC, 
            ingredient ASC
    """
    
    return frappe.db.sql(query, filters, as_dict=1)


def get_conditions(filters):
    conditions = []

    if filters.get("from_date") and filters.get("to_date"):
        if filters.get("from_date") == filters.get("to_date"):
            conditions.append("mpe.date = %(from_date)s")
        else:
            conditions.append("mpe.date >= %(from_date)s")
            conditions.append("mpe.date <= %(to_date)s")
    elif filters.get("from_date"):
        conditions.append("mpe.date >= %(from_date)s")
    elif filters.get("to_date"):
        conditions.append("mpe.date <= %(to_date)s")

    elif filters.get("date"):
        conditions.append("mpe.date = %(date)s")
    
    return " AND " + " AND ".join(conditions) if conditions else ""
