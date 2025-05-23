import frappe

@frappe.whitelist()
def save_meal_assignment(assignments_json):
    try:
        import json
        from frappe.utils import getdate
        from datetime import timedelta

        data = json.loads(assignments_json)
        
        date = getdate(data['date'])
        meal_type = data['meal_type']
        meal_id = data['meal_id']
        meal_name = data['meal_name']
        customer = data.get('customer', '')  # Make sure customer is included

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

        # Check if entry already exists (include customer in the check)
        existing = [
            e for e in meal_plan_doc.meal_plan_entry
            if e.date == date and e.meal_type == meal_type and e.get('customer') == customer
        ]
        
        if existing:
            existing[0].meal_id = meal_id
            existing[0].meal_name = meal_name
            existing[0].customer = customer
        else:
            meal_plan_doc.append("meal_plan_entry", {
                "date": date,
                "meal_type": meal_type,
                "meal_id": meal_id,
                "meal_name": meal_name,
                "customer": customer
            })
        
        # Add projects from the week's tasks
        try:
            new_projects = set(get_projects_for_week(monday))
            existing_projects = set()
            if meal_plan_doc.selected_projects:
                existing_projects = set(
                    [proj.strip() for proj in meal_plan_doc.selected_projects.split(",") if proj.strip()]
                )
            all_projects = existing_projects.union(new_projects)
            meal_plan_doc.selected_projects = ", ".join(sorted(all_projects))
        except Exception as e:
            frappe.logger().error(f"Error getting projects for week: {str(e)}")
            # Continue without projects if there's an error

        meal_plan_doc.save()
        frappe.db.commit()

        # Return "OK" to match what the frontend expects
        return "OK"
        
    except Exception as e:
        frappe.logger().error(f"Error in save_meal_assignment: {str(e)}")
        frappe.log_error(f"Save meal assignment error: {str(e)}")
        return {"error": str(e)}


# Also add the get_projects_for_week function if it doesn't exist
def get_projects_for_week(monday):
    """Get projects that have tasks in the given week"""
    try:
        from datetime import timedelta
        
        sunday = monday + timedelta(days=6)
        
        # Get tasks for the week
        tasks = frappe.get_all("Task", filters={
            "subject": "Meal Plan Allocation",
            "exp_start_date": ["<=", sunday],
            "exp_end_date": [">=", monday]
        }, fields=["project"])
        
        projects = [task.project for task in tasks if task.project]
        return list(set(projects))  # Remove duplicates
        
    except Exception as e:
        frappe.logger().error(f"Error getting projects for week: {str(e)}")
        return []


@frappe.whitelist()
def get_meal_entries_for_dates(dates_json):
    """Get meal entries for the specified dates"""
    try:
        import json
        from frappe.utils import getdate
        
        dates = json.loads(dates_json)
        
        if not dates:
            return []
            
        # Get all meal plans that might contain these dates
        meal_plans = frappe.get_all("Meal Plan", filters={
            "start_date": ["<=", max(dates)],
            "end_date": [">=", min(dates)]
        }, fields=["name"])
        
        entries = []
        for plan in meal_plans:
            meal_plan_doc = frappe.get_doc("Meal Plan", plan.name)
            for entry in meal_plan_doc.meal_plan_entry:
                if str(entry.date) in dates:
                    entries.append({
                        "date": str(entry.date),
                        "meal_type": entry.meal_type,
                        "meal_name": entry.meal_name,
                        "customer": entry.get("customer", "")
                    })
        
        return entries
        
    except Exception as e:
        frappe.logger().error(f"Error in get_meal_entries_for_dates: {str(e)}")
        return []


@frappe.whitelist()
def remove_meal_assignment(date, meal_type, customer):
    """Remove a meal assignment"""
    try:
        from frappe.utils import getdate
        from datetime import timedelta
        
        date = getdate(date)
        monday = date - timedelta(days=date.weekday())
        
        # Find the meal plan for this week
        meal_plan = frappe.get_all("Meal Plan", filters={
            "start_date": monday
        }, fields=["name"])
        
        if not meal_plan:
            return "not_found"
            
        meal_plan_doc = frappe.get_doc("Meal Plan", meal_plan[0].name)
        
        # Find and remove the entry
        for i, entry in enumerate(meal_plan_doc.meal_plan_entry):
            if (entry.date == date and 
                entry.meal_type == meal_type and 
                entry.get('customer') == customer):
                del meal_plan_doc.meal_plan_entry[i]
                break
        
        meal_plan_doc.save()
        frappe.db.commit()
        
        return "OK"
        
    except Exception as e:
        frappe.logger().error(f"Error in remove_meal_assignment: {str(e)}")
        return "error"
    

@frappe.whitelist()
def submit_meal_plan(monday):
    from frappe.utils import getdate
    import traceback

    frappe.logger().info(f"[submit_meal_plan] Called with monday = {monday}")
    try:
        monday = getdate(monday)
        frappe.logger().info(f"[submit_meal_plan] Parsed date: {monday}")

        meal_plan = frappe.get_all("Meal Plan", filters={
            "start_date": monday
        }, fields=["name", "docstatus"])

        frappe.logger().info(f"[submit_meal_plan] Found meal_plan records: {meal_plan}")

        if not meal_plan:
            return "not_found"

        plan_doc = frappe.get_doc("Meal Plan", meal_plan[0].name)
        frappe.logger().info(f"[submit_meal_plan] Loaded doc: {plan_doc.name}, docstatus: {plan_doc.docstatus}")

        if plan_doc.docstatus == 0:
            plan_doc.submit()
            frappe.logger().info(f"[submit_meal_plan] Successfully submitted: {plan_doc.name}")
            return "submitted"
        else:
            return "already_submitted"

    except Exception as e:
        frappe.logger().error(f"[submit_meal_plan] Error: {str(e)}\n{traceback.format_exc()}")
        return "error"


@frappe.whitelist()
def update_daily_meal_costs(meal_plan_doc):
    """Update Daily Meal Costs table based on meal plan entries"""
    try:
        # Get all unique dates from meal plan entries
        dates_in_plan = {}
        for entry in meal_plan_doc.meal_plan_entry:
            date_key = entry.date
            if date_key not in dates_in_plan:
                dates_in_plan[date_key] = []
            dates_in_plan[date_key].append(entry)
        
        # Clear existing daily meal costs entries
        meal_plan_doc.daily_meal_costs = []
        
        # Calculate costs for each date
        for date, meal_entries in dates_in_plan.items():
            total_meal_cost = 0
            
            for meal_entry in meal_entries:
                try:
                    # Get the total meal cost from Meals doctype
                    meal_doc = frappe.get_doc("Meals", meal_entry.meal_id)
                    meal_cost = meal_doc.get("total_meal_cost", 0)
                    
                    if meal_cost:
                        total_meal_cost += meal_cost
                        
                except Exception as meal_error:
                    frappe.logger().error(f"Error getting cost for meal {meal_entry.meal_name}: {str(meal_error)}")
            
            # Add entry to daily meal costs table
            meal_plan_doc.append("daily_meal_costs", {
                "date": date,
                "meal_cost": total_meal_cost
            })
            
    except Exception as e:
        frappe.logger().error(f"Error updating daily meal costs: {str(e)}")
        frappe.log_error(f"Daily meal costs error: {str(e)}")



import frappe
from frappe.utils import getdate

@frappe.whitelist()
def create_shopping_list(monday):
    """Create shopping list from meal plan start date (monday in yyyy-mm-dd)"""
    try:
        frappe.logger().info(f"[create_shopping_list] Starting shopping list creation for: {monday}")
        monday_date = getdate(monday)

        # Fetch Meal Plan for given start date
        meal_plan_list = frappe.get_all("Meal Plan", filters={"start_date": monday_date}, fields=["name"])
        if not meal_plan_list:
            msg = f"No Meal Plan found starting on {monday}"
            frappe.logger().warning(msg)
            return msg

        meal_plan_doc = frappe.get_doc("Meal Plan", meal_plan_list[0].name)

        # Check if shopping list already exists
        existing_list = frappe.get_all("Shopping List", filters={"meal_plan": meal_plan_doc.name}, fields=["name"])
        if existing_list:
            shopping_list_doc = frappe.get_doc("Shopping List", existing_list[0].name)
            shopping_list_doc.shopping_details = []
            frappe.logger().info(f"Regenerating existing shopping list: {shopping_list_doc.name}")
        else:
            shopping_list_doc = frappe.new_doc("Shopping List")
            shopping_list_doc.meal_plan = meal_plan_doc.name
            shopping_list_doc.selected_projects = meal_plan_doc.selected_projects or ""
            frappe.logger().info(f"Creating new shopping list for Meal Plan: {meal_plan_doc.name}")

        ingredient_totals = {}
        meal_frequency = {}

        for entry in meal_plan_doc.get("meal_plan_entry", []):
            meal_id = entry.get("meal_id")
            if not meal_id:
                continue
            meal_frequency[meal_id] = meal_frequency.get(meal_id, 0) + 1

        for meal_id, freq in meal_frequency.items():
            meal_doc = frappe.get_doc("Meals", meal_id)
            for recipe in meal_doc.get("recipes", []):
                recipe_name = recipe.get("recipe_name")
                if not recipe_name:
                    continue
                recipe_doc = frappe.get_doc("Recipe", recipe_name)
                for ing in recipe_doc.get("ingredients", []):
                    item_code = ing.get("item_code")
                    qty = ing.get("qty", 0)
                    cost = ing.get("cost", 0)
                    if not item_code:
                        continue
                    if item_code not in ingredient_totals:
                        ingredient_totals[item_code] = {"qty": 0, "cost": 0}
                    ingredient_totals[item_code]["qty"] += qty * freq
                    ingredient_totals[item_code]["cost"] += cost * freq

        for item_code, totals in ingredient_totals.items():
            shopping_list_doc.append("shopping_details", {
                "item_code": item_code,
                "qty": totals["qty"],
                "cost": totals["cost"]
            })

        shopping_list_doc.save()
        frappe.logger().info(f"[create_shopping_list] Shopping List created: {shopping_list_doc.name} with {len(shopping_list_doc.shopping_details)} items")
        return shopping_list_doc.name

    except Exception as e:
        error_message = f"Error creating shopping list: {str(e)}"
        frappe.logger().error(error_message)
        frappe.log_error(error_message)
        return error_message


@frappe.whitelist()
def get_meal_plan_status(monday):
    """Get the status of meal plan for a given week"""
    try:
        from frappe.utils import getdate
        
        monday_date = getdate(monday)
        
        meal_plan = frappe.get_all("Meal Plan", filters={
            "start_date": monday_date
        }, fields=["name", "status"])
        
        if meal_plan:
            return {
                "exists": True,
                "status": meal_plan[0].status,
                "name": meal_plan[0].name
            }
        else:
            return {
                "exists": False,
                "status": None,
                "name": None
            }
            
    except Exception as e:
        frappe.logger().error(f"Error getting meal plan status: {str(e)}")
        return {"exists": False, "status": None, "name": None}