import frappe
from frappe.utils import getdate
from datetime import timedelta

@frappe.whitelist()
def save_meal_assignment(assignments_json):
    import json
    from frappe.utils import getdate
    from datetime import timedelta

    data = json.loads(assignments_json)
    
    date = getdate(data['date'])
    meal_type = data['meal_type']
    meal_id = data['meal_id']
    meal_name = data['meal_name']

    # Appetite values from frontend
    small_appetite = data.get("small_appetite", 0)
    normal_appetite = data.get("normal_appetite", 0)
    large_appetite = data.get("large_appetite", 0)
    total_individuals = data.get("total_individuals", 0)

    # Get week range
    monday = date - timedelta(days=date.weekday())
    sunday = monday + timedelta(days=6)

    # Get or create the Meal Plan for this week
    meal_plan = frappe.get_all("Meal Plan", filters={
        "start_date": monday
    }, fields=["name"])

    if meal_plan:
        meal_plan_doc = frappe.get_doc("Meal Plan", meal_plan[0].name)
    else:
        meal_plan_doc = frappe.new_doc("Meal Plan")
        meal_plan_doc.start_date = monday
        meal_plan_doc.end_date = sunday
        meal_plan_doc.selected_projects = ""
   
    frappe.logger().info(f"Appetite values: Small={small_appetite}, Normal={normal_appetite}, Large={large_appetite}")


    # Store the latest appetite values in the parent Meal Plan
    meal_plan_doc.small_appetite = small_appetite
    meal_plan_doc.normal_appetite = normal_appetite
    meal_plan_doc.large_appetite = large_appetite
    meal_plan_doc.total_individuals = total_individuals

    # Check if entry already exists
    existing = [
        e for e in meal_plan_doc.meal_plan_entry
        if e.date == date and e.meal_type == meal_type
    ]
    if existing:
        existing[0].meal_id = meal_id
        existing[0].meal_name = meal_name
    else:
        meal_plan_doc.append("meal_plan_entry", {
            "date": date,
            "meal_type": meal_type,
            "meal_id": meal_id,
            "meal_name": meal_name
        })
    
    # Add projects from the week's tasks
    new_projects = set(get_projects_for_week(monday))

    existing_projects = set()
    if meal_plan_doc.selected_projects:
        existing_projects = set(
            [proj.strip() for proj in meal_plan_doc.selected_projects.split(",") if proj.strip()]
        )

    all_projects = existing_projects.union(new_projects)
    meal_plan_doc.selected_projects = ", ".join(sorted(all_projects))

    meal_plan_doc.save()
    frappe.db.commit()

    return {"status": "success"}



def get_projects_for_week(monday):
    sunday = monday + timedelta(days=6)
    tasks = frappe.get_all("Task", filters={
        "exp_start_date": ["<=", sunday],
        "exp_end_date": [">=", monday]
    }, fields=["project"])

    return list({task.project for task in tasks if task.project})

def get_monday(date_str):
    from datetime import datetime, timedelta
    date_obj = getdate(date_str)
    weekday = date_obj.weekday()
    monday = date_obj - timedelta(days=weekday)
    return monday.isoformat()

def get_projects_for_customer(customer):
    projects = frappe.get_all("Project", filters={"customer": customer}, pluck="name")
    return projects

@frappe.whitelist()
def submit_meal_plan(monday):
    from frappe.utils import getdate

    monday = getdate(monday)

    meal_plan = frappe.get_all("Meal Plan", filters={
        "start_date": monday
    }, fields=["name", "docstatus"])

    if not meal_plan:
        return "not_found"

    plan_doc = frappe.get_doc("Meal Plan", meal_plan[0].name)

    if plan_doc.docstatus == 0:
        plan_doc.submit()
        return "submitted"
    else:
        return "already_submitted"

@frappe.whitelist()
def get_meal_plan_data(start_date):
    from frappe.utils import getdate
    from datetime import timedelta

    monday = getdate(start_date)
    sunday = monday + timedelta(days=6)

    plan = frappe.get_all("Meal Plan", filters={"start_date": monday}, fields=["name"])
    if not plan:
        return {}

    doc = frappe.get_doc("Meal Plan", plan[0].name)

    return {
        "name": doc.name,
        "entries": [
            {
                "date": e.date,
                "meal_type": e.meal_type,
                "meal_id": e.meal_id,
                "meal_name": e.meal_name
            }
            for e in doc.meal_plan_entry
        ],
        "total_individuals": doc.total_individuals,
        "small_appetite": doc.small_appetite,
        "normal_appetite": doc.normal_appetite,
        "large_appetite": doc.large_appetite,
        "selected_projects": doc.selected_projects
    }
