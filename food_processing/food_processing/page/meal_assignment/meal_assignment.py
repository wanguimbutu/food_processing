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
        customer = data.get('customer', '')
        project_key = data.get('project_key', '') or ''

        # Parse project_key: expected format: customer_YYYY-MM-DD_YYYY-MM-DD
        task_start_date = None
        task_end_date = None
        project_name = ""
        no_of_people = 0

        if project_key:
            parts = project_key.split("_")
            if len(parts) >= 3:
                customer_code = parts[0]
                task_start_date = getdate(parts[1])
                task_end_date = getdate(parts[2])

                # Fetch allocation tasks for that week
                tasks = get_projects_for_week(task_start_date)

                # Match the specific task for this customer and date range
                matching_task = next(
                    (t for t in tasks if t["custom_customer"] == customer and
                     getdate(t["exp_start_date"]) == task_start_date and
                     getdate(t["exp_end_date"]) == task_end_date),
                    None
                )

                if matching_task:
                    project_name = matching_task.get("project", "")
                    no_of_people = int(matching_task.get("custom_no_of_people") or 0)

        # Use the actual task's start/end dates for the meal plan range
        monday = task_start_date or (date - timedelta(days=date.weekday()))
        sunday = task_end_date or (monday + timedelta(days=6))

        # Get or create meal plan for the customer for that week
        meal_plan = frappe.get_all("Meal Plan", filters={
            "start_date": monday,
            "customer": customer
        }, fields=["name", "docstatus"], order_by="`tabMeal Plan`.creation desc")

        if meal_plan:
            meal_plan_doc = frappe.get_doc("Meal Plan", meal_plan[0].name)
            if meal_plan_doc.docstatus == 2:
                # Create amendment if cancelled
                amendment_doc = frappe.copy_doc(meal_plan_doc)
                amendment_doc.docstatus = 0 
                amendment_doc.amended_from = meal_plan_doc.name
                amendment_doc.name = None
                amendment_doc.insert()
                meal_plan_doc = amendment_doc
        else:
            # Create new meal plan
            meal_plan_doc = frappe.new_doc("Meal Plan")
            meal_plan_doc.start_date = monday
            meal_plan_doc.end_date = sunday
            meal_plan_doc.customer = customer
            meal_plan_doc.group_name = customer
            meal_plan_doc.selected_projects = ""
            meal_plan_doc.title = f"Meal Plan - {customer} - Week of {monday.strftime('%d %b %Y')}"

        # Log for debugging
        frappe.logger().info(f"[save_meal_assignment] Customer: {customer}, Meal: {meal_name}, Project: {project_name}, Individuals: {no_of_people}")

        # Set total individuals only if meals are being assigned
        if no_of_people > 0:
            meal_plan_doc.total_individuals = no_of_people

        # Set selected_projects only if project is found
        if project_name:
            existing_projects = set(meal_plan_doc.selected_projects.split(", ")) if meal_plan_doc.selected_projects else set()
            existing_projects.add(project_name)
            meal_plan_doc.selected_projects = ", ".join(sorted(existing_projects))

        # Set exact start and end dates if available
        if task_start_date and task_end_date:
            meal_plan_doc.start_date = task_start_date
            meal_plan_doc.end_date = task_end_date

        # Check if this entry already exists
        existing = [
            e for e in meal_plan_doc.meal_plan_entry
            if getdate(e.date) == date and e.meal_type == meal_type and e.get('project_key', '') == project_key
        ]

        if existing:
            # Update existing entry
            e = existing[0]
            e.meal_id = meal_id
            e.meal_name = meal_name
            e.customer = customer
            e.project_key = project_key
        else:
            # Add new entry
            meal_plan_doc.append("meal_plan_entry", {
                "date": date,
                "meal_type": meal_type,
                "meal_id": meal_id,
                "meal_name": meal_name,
                "customer": customer,
                "project_key": project_key
            })

        # Save the meal plan
        meal_plan_doc.save()
        frappe.db.commit()

        return "OK"

    except Exception as e:
        error_msg = f"Error in save_meal_assignment: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error(error_msg)
        return str(e)


#get all customers with assigned meals for a week
@frappe.whitelist()
def get_customers_for_week(monday):
    """Get all customers who have meal assignments for the given week"""
    try:
        from frappe.utils import getdate
        from datetime import timedelta
        
        monday_date = getdate(monday)
        sunday = monday_date + timedelta(days=6)
        
        # Get all meal plans for the week
        meal_plans = frappe.get_all("Meal Plan", filters={
            "start_date": monday_date
        }, fields=["name", "customer", "docstatus", "total_individuals", "group_name"])
        
        customers_info = []
        for plan in meal_plans:
            customers_info.append({
                "customer": plan.customer,
                "group_name": plan.group_name,
                "meal_plan_name": plan.name,
                "status": "Submitted" if plan.docstatus == 1 else "Draft",
                "docstatus": plan.docstatus,
                "total_individuals": plan.total_individuals or 0
            })
        
        return customers_info
        
    except Exception as e:
        frappe.logger().error(f"Error getting customers for week: {str(e)}")
        return []


def submit_meal_plans_for_week(monday, customers=None):
    """Submit meal plans for specific customers or all customers in a week"""
    from frappe.utils import getdate
    import traceback
    import json

    frappe.logger().info(f"[submit_meal_plans_for_week] Called with monday = {monday}, customers = {customers}")
    
    try:
        monday = getdate(monday)
        
        if customers and isinstance(customers, str):
            try:
                customers = json.loads(customers)
            except:
                customers = [customers]
        
        # Get meal plans to submit
        from datetime import timedelta
        sunday = monday + timedelta(days=6)

        filters = {
            "start_date": ["<=", sunday],
            "end_date": [">=", monday],
            "docstatus": 0
        }

        if customers:
            filters["customer"] = ["in", customers]

        
        meal_plans = frappe.get_all("Meal Plan", filters=filters, fields=["name", "group_name", "docstatus"])

        frappe.logger().info(f"[submit_meal_plans_for_week] Found {len(meal_plans)} meal plans to process")

        if not meal_plans:
            return {"status": "no_plans_found", "message": "No draft meal plans found for the specified criteria"}

        submitted_count = 0
        already_submitted_count = 0
        error_count = 0
        results = []

        for plan_info in meal_plans:
            try:
                plan_doc = frappe.get_doc("Meal Plan", plan_info.name)
                frappe.logger().info(f"[submit_meal_plans_for_week] Processing: {plan_doc.name} for customer: {plan_info.customer}")

                if plan_doc.docstatus == 0:
                
                    if not plan_doc.group_name and plan_doc.customer:
                        plan_doc.group_name = plan_doc.customer
                        plan_doc.save()
                    
                    plan_doc.submit()
                    submitted_count += 1
                    results.append({
                        "customer": plan_info.customer,
                        "meal_plan": plan_doc.name,
                        "status": "submitted"
                    })
                    frappe.logger().info(f"[submit_meal_plans_for_week] Successfully submitted: {plan_doc.name}")
                else:
                    already_submitted_count += 1
                    results.append({
                        "customer": plan_info.customer,
                        "meal_plan": plan_doc.name,
                        "status": "already_submitted"
                    })

            except Exception as plan_error:
                error_count += 1
                error_msg = str(plan_error)
                results.append({
                    "customer": plan_info.customer,
                    "meal_plan": plan_info.name,
                    "status": "error",
                    "error": error_msg
                })
                frappe.logger().error(f"[submit_meal_plans_for_week] Error submitting {plan_info.name}: {error_msg}")

        return {
            "status": "completed",
            "submitted": submitted_count,
            "already_submitted": already_submitted_count,
            "errors": error_count,
            "total_processed": len(meal_plans),
            "details": results
        }

    except Exception as e:
        error_msg = f"[submit_meal_plans_for_week] Error: {str(e)}\n{traceback.format_exc()}"
        frappe.logger().error(error_msg)
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def submit_meal_plan_and_create_shopping_list(monday, customer=None):
    """Combined function to submit meal plan and create shopping list"""
    try:
        frappe.logger().info(f"[submit_meal_plan_and_create_shopping_list] START - Monday: {monday}, Customer: {customer}")
        
        # Step 1: Submit meal plan
        submit_result = submit_meal_plans_for_week(monday)  
        frappe.logger().info(f"[submit_meal_plan_and_create_shopping_list] Submit result: {submit_result}")
        
        if submit_result and (submit_result.get("status") == "completed" or submit_result == "no_plans_to_submit"):
            # Step 2: Create shopping list
            shopping_result = create_shopping_list(monday)
            frappe.logger().info(f"[submit_meal_plan_and_create_shopping_list] Shopping list result: {shopping_result}")
            
            return {
                "status": "success",
                "meal_plan_result": submit_result,
                "shopping_list_result": shopping_result,
                "message": "Meal plan submitted and shopping list created successfully"
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to submit meal plan: {submit_result}",
                "meal_plan_result": submit_result
            }
            
    except Exception as e:
        error_msg = f"Error in submit_meal_plan_and_create_shopping_list: {str(e)}"
        frappe.logger().error(f"[submit_meal_plan_and_create_shopping_list] {error_msg}")
        return {"status": "error", "message": error_msg}
    
def get_projects_for_week(monday):
    """Return Meal Plan Allocation tasks for the given week"""
    try:
        from datetime import timedelta

        sunday = monday + timedelta(days=6)

        tasks = frappe.get_all("Task", filters={
            "subject": "Meal Plan Allocation",
            "exp_start_date": ["<=", sunday],
            "exp_end_date": [">=", monday],
            "custom_is_meals_at_camp": 1
        }, fields=[
            "project",
            "custom_no_of_people",
            "custom_customer",
            "exp_start_date",
            "exp_end_date"
        ])

        return tasks

    except Exception as e:
        frappe.logger().error(f"Error getting meal allocation tasks: {str(e)}")
        return []


@frappe.whitelist()
def get_meal_entries_for_dates(dates_json):
    """Get meal entries for specific dates, excluding cancelled meal plans"""
    try:
        import json
        from frappe.utils import getdate
        from datetime import timedelta
        
        dates = json.loads(dates_json)
        entries = []
        
        for date_str in dates:
            date = getdate(date_str)
            week_start = date - timedelta(days=date.weekday())
            week_end = week_start + timedelta(days=6)

            # Find meal plans overlapping the week
            meal_plans = frappe.get_all("Meal Plan", 
                filters={
                    "start_date": ["<=", week_end],
                    "end_date": [">=", week_start],
                    "docstatus": ["!=", 2]
                }, 
                fields=["name", "docstatus"]
            )
            
            for meal_plan in meal_plans:
                meal_plan_doc = frappe.get_doc("Meal Plan", meal_plan.name)
                
                for entry in meal_plan_doc.meal_plan_entry:
                    if entry.date == date:
                        entries.append({
                            "date": str(entry.date),
                            "meal_type": entry.meal_type,
                            "meal_name": entry.meal_name,
                            "customer": entry.get('custom_customer') or entry.get('customer'),
                            "project_key": entry.get('project_key', '')  
                        })
        
        return entries
        
    except Exception as e:
        frappe.logger().error(f"Error in get_meal_entries_for_dates: {str(e)}")
        return []

@frappe.whitelist()
def remove_meal_assignment(date, meal_type, customer, project_key=None):
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
        
        customer = customer or None
        project_key = project_key or None
        
        initial_count = len(meal_plan_doc.meal_plan_entry)
        meal_plan_doc.meal_plan_entry = [
            entry for entry in meal_plan_doc.meal_plan_entry 
            if not (entry.date == date and 
                    entry.meal_type == meal_type and 
                    entry.customer == customer and
                    entry.get('project_key') == project_key)  
        ]
        
        final_count = len(meal_plan_doc.meal_plan_entry)
        
        if initial_count == final_count:
            return "not_found"
        
        meal_plan_doc.save()
        frappe.db.commit()
        
        return "OK"
        
    except Exception as e:
        frappe.logger().error(f"Error in remove_meal_assignment: {str(e)}")
        return "error"
    

@frappe.whitelist()
def save_meal_plan_summary(monday, total_individuals):
    from frappe.utils import getdate
    monday = getdate(monday)
    plans = frappe.get_all("Meal Plan", filters={"start_date": monday}, fields=["name"])
    if not plans:
        return "not_found"
    plan_doc = frappe.get_doc("Meal Plan", plans[0].name)
    plan_doc.total_individuals = int(total_individuals or 0)
    plan_doc.save()
    frappe.db.commit()
    return "OK"
   

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




@frappe.whitelist()
def create_shopping_list(monday=None):
    """Create a shopping list for the most recently submitted meal plan (optionally within a week)"""
    from frappe.utils import getdate
    from datetime import timedelta

    try:
        filters = {"docstatus": 1}

        if monday:
            monday = getdate(monday)
            sunday = monday + timedelta(days=6)

            filters["start_date"] = ["<=", sunday]
            filters["end_date"] = [">=", monday]

        latest_plan = frappe.get_all("Meal Plan", filters=filters, fields=["name"], order_by="modified desc", limit=1)

        if not latest_plan:
            return {"status": "error", "message": "No submitted Meal Plan found"}

        latest_doc = frappe.get_doc("Meal Plan", latest_plan[0].name)

        # Call your existing shopping list generation logic
        result = _generate_shopping_list(latest_doc)

        return {
            "status": "success",
            "message": f"Shopping list created for {latest_doc.name}",
            "details": result
        }

    except Exception as e:
        frappe.logger().error(f"Error in create_shopping_list: {str(e)}")
        return {"status": "error", "message": str(e)}

import math

def _generate_shopping_list(meal_plan_doc):
    try:
        frappe.msgprint(f"Generating shopping list for: {meal_plan_doc.name}")
        frappe.logger().info(f"[START] Shopping list creation for {meal_plan_doc.name}")

        total_individuals = meal_plan_doc.total_individuals or 1  
        frappe.logger().info(f"Total individuals for shopping calculations: {total_individuals}")

        existing_list = frappe.get_all("Shopping List", filters={
            "meal_plan": meal_plan_doc.name
        }, fields=["name"])

        if existing_list:
            shopping_list_doc = frappe.get_doc("Shopping List", existing_list[0].name)
            shopping_list_doc.shopping_details = []
            frappe.logger().info(f"Found existing Shopping List: {shopping_list_doc.name}, clearing items")
        else:
            shopping_list_doc = frappe.new_doc("Shopping List")
            shopping_list_doc.meal_plan = meal_plan_doc.name
            shopping_list_doc.selected_projects = meal_plan_doc.selected_projects or ""
            frappe.logger().info("Creating new Shopping List")

        ingredient_totals = {}
        unique_meals = set()
        meal_frequency = {}

        # ✅ Add validation for meal plan entries
        if not meal_plan_doc.meal_plan_entry:
            frappe.msgprint(f"No meal entries found in meal plan {meal_plan_doc.name}")
            frappe.logger().warning(f"No meal entries in meal plan {meal_plan_doc.name}")
            return None

        for entry in meal_plan_doc.meal_plan_entry:
            if entry.meal_id:  # ✅ Check if meal_id exists
                unique_meals.add(entry.meal_id)
                meal_frequency[entry.meal_id] = meal_frequency.get(entry.meal_id, 0) + 1

        frappe.logger().info(f"Unique meals found: {unique_meals}")
        frappe.logger().info(f"Meal frequencies: {meal_frequency}")

        if not unique_meals:
            frappe.msgprint("No valid meals found in meal plan entries")
            frappe.logger().warning("No valid meals found in meal plan entries")
            return None

        MAX_COST = 99999999.99  

        for meal_id in unique_meals:
            try:
                # ✅ Check if meal exists before getting it
                if not frappe.db.exists("Meals", meal_id):
                    frappe.logger().warning(f"Meal {meal_id} does not exist, skipping")
                    continue

                meal_doc = frappe.get_doc("Meals", meal_id)
                frequency = meal_frequency[meal_id]

                frappe.logger().info(f"Processing meal {meal_id} (frequency: {frequency})")

                if hasattr(meal_doc, 'recipes') and meal_doc.recipes:
                    frappe.logger().info(f"Meal {meal_id} has {len(meal_doc.recipes)} recipes")
                    
                    for recipe in meal_doc.recipes:
                        recipe_name = recipe.get('recipe_name')
                        if not recipe_name:
                            frappe.logger().warning(f"Recipe in meal {meal_id} has no recipe_name")
                            continue

                        try:
                            # ✅ Check if recipe exists before getting it
                            if not frappe.db.exists("Recipe", recipe_name):
                                frappe.logger().warning(f"Recipe {recipe_name} does not exist, skipping")
                                continue

                            recipe_doc = frappe.get_doc("Recipe", recipe_name)
                            frappe.logger().info(f"Processing recipe {recipe_name}")

                            if hasattr(recipe_doc, 'ingredients') and recipe_doc.ingredients:
                                frappe.logger().info(f"Recipe {recipe_name} has {len(recipe_doc.ingredients)} ingredients")
                                
                                for ingredient in recipe_doc.ingredients:
                                    item_code = ingredient.get('ingredient')
                                    try:
                                        per_person_qty = float(ingredient.get('qty', 0)) or 0
                                        packet_cost = float(ingredient.get('cost', 0)) or 0
                                    except Exception as e:
                                        frappe.logger().warning(f"Invalid qty or cost for {item_code}: {e}")
                                        per_person_qty = 0
                                        packet_cost = 0

                                    if not item_code:
                                        frappe.logger().warning(f"Ingredient in recipe {recipe_name} has no item_code")
                                        continue

                                    # Total quantity needed (unrounded): per person qty × individuals × frequency
                                    total_qty = per_person_qty * frequency * total_individuals

                                    # Round up total quantity for whole packets
                                    rounded_qty = math.ceil(total_qty) if total_qty > 0 else 0

                                    # Total cost = number of packets * cost per packet
                                    total_cost = rounded_qty * packet_cost

                                    if total_cost > MAX_COST:
                                        frappe.logger().warning(f"Cost for {item_code} capped from {total_cost} to {MAX_COST}")
                                        total_cost = MAX_COST

                                    total_cost = round(total_cost, 2)

                                    uom = ingredient.get('uom', '') or ''

                                    if item_code in ingredient_totals:
                                        ingredient_totals[item_code]['qty'] += rounded_qty
                                        ingredient_totals[item_code]['cost'] += total_cost
                                        
                                        if not ingredient_totals[item_code].get('uom'):
                                            ingredient_totals[item_code]['uom'] = uom
                                    else:
                                        ingredient_totals[item_code] = {
                                            'item_code': item_code,
                                            'qty': rounded_qty,
                                            'cost': total_cost,
                                            'uom': uom
                                        }

                                    frappe.logger().info(f"{item_code}: {rounded_qty} units × {packet_cost} = {total_cost}")
                            else:
                                frappe.logger().warning(f"Recipe {recipe_name} has no ingredients")

                        except Exception as recipe_error:
                            frappe.logger().error(f"Error processing recipe {recipe_name}: {str(recipe_error)}")
                else:
                    frappe.logger().warning(f"Meal {meal_id} has no recipes")

            except Exception as meal_error:
                frappe.logger().error(f"Error processing meal {meal_id}: {str(meal_error)}")

        frappe.logger().info(f"Found {len(ingredient_totals)} total ingredients")

        if not ingredient_totals:
            frappe.msgprint("No ingredients found to create shopping list")
            frappe.logger().warning("No ingredients found to create shopping list")
            return None

        for ingredient_data in ingredient_totals.values():
            ingredient_data['qty'] = math.ceil(ingredient_data['qty']) if ingredient_data['qty'] > 0 else 0
            ingredient_data['cost'] = round(ingredient_data['cost'], 2)

            shopping_list_doc.append("shopping_details", {
                "item_code": ingredient_data['item_code'],
                "qty": ingredient_data['qty'],
                "cost": ingredient_data['cost'],
                "uom": ingredient_data.get('uom', '')  
            })
            frappe.logger().info(f"Added ingredient to list: {ingredient_data}")

        shopping_list_doc.save()
        frappe.msgprint(f"Shopping List created/updated: {shopping_list_doc.name} for {total_individuals} people")
        frappe.logger().info(f"[DONE] Shopping List: {shopping_list_doc.name} for {total_individuals} people")

        return shopping_list_doc.name

    except Exception as e:
        error_msg = f"Error generating shopping list: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error(error_msg)
        frappe.msgprint(error_msg)
        return None

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