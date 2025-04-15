from frappe import _

def get_data(data=None):
    return {
        "fieldname": "name", 
        "non_standard_fieldnames": {
            "Shopping List": "meal_plan",  
        },
        "transactions": [
            {
                "label": _("Linked Documents"),
                "items": ["Shopping List"]
            }
        ]
    }
