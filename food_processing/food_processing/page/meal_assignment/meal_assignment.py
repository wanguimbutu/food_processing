from datetime import timedelta
import frappe

@frappe.whitelist()
def save_meal_assignment(assignments_json):
    try:
        import json
        from frappe.utils import getdate
        from datetime import timedelta

        data = json.loads(assignments_json)

        # Extract core fields
        date = getdate(data['date'])
        meal_type = data['meal_type']
        meal_id = data['meal_id']
        meal_name = data['meal_name']
        customer = data.get('customer', '')
        project_key = data.get('project_key', '') or ''
        project_name = data.get('project_name', '') or ''
        task_name = data.get('task_name', '') or ''

        # Week boundaries
        monday = date - timedelta(days=date.weekday())
        sunday = monday + timedelta(days=6)

        # Fetch total_individuals from Task
        total_individuals = 0
        if task_name:
            try:
                task_doc = frappe.get_doc("Task", task_name)
                total_individuals = int(task_doc.custom_no_of_people or 0)
                frappe.log_error("Meal Assignment Debug", f"[TASK LOOKUP] People = {total_individuals} from task {task_name}")
            except Exception as e:
                frappe.logger().error(f"[ERROR] Failed to get people count from task {task_name}: {e}")
                frappe.log_error("Meal Assignment Error", f"Failed to fetch custom_no_of_people from task {task_name}")

        frappe.log_error("Meal Assignment Debug", f"[DEBUG] Customer = {customer}, Project = {project_name}, Task = {task_name}, People = {total_individuals}")

        #  Find or create Meal Plan for the week + customer + task
        meal_plan = frappe.get_all("Meal Plan", filters={
            "start_date": monday,
            "customer": customer,
            "task": task_name
        }, fields=["name", "docstatus"], order_by="`tabMeal Plan`.creation desc")

        if meal_plan:
            meal_plan_doc = frappe.get_doc("Meal Plan", meal_plan[0].name)
            if meal_plan_doc.docstatus == 2:  # Cancelled → create amendment
                amendment_doc = frappe.copy_doc(meal_plan_doc)
                amendment_doc.docstatus = 0
                amendment_doc.amended_from = meal_plan_doc.name
                amendment_doc.name = None
                amendment_doc.insert()
                meal_plan_doc = amendment_doc
        else:
            # Create new Meal Plan (unique to this task)
            meal_plan_doc = frappe.new_doc("Meal Plan")
            meal_plan_doc.start_date = monday
            meal_plan_doc.end_date = sunday
            meal_plan_doc.customer = customer
            meal_plan_doc.group_name = customer
            meal_plan_doc.title = f"Meal Plan - {customer} - {task_name} - Week of {monday.strftime('%d %b %Y')}"
            meal_plan_doc.project = project_name
            meal_plan_doc.task = task_name

            if total_individuals > 0:
                meal_plan_doc.total_individuals = total_individuals
                frappe.log_error("Meal Assignment Debug", f"[DEBUG] Set total_individuals = {total_individuals} on NEW plan")

        # Update total_individuals if more accurate
        if total_individuals > 0 and (
            not meal_plan_doc.total_individuals or total_individuals < meal_plan_doc.total_individuals
        ):
            meal_plan_doc.total_individuals = total_individuals
            frappe.log_error("Meal Assignment Debug", f"[DEBUG] Overwrote total_individuals = {total_individuals} on plan {meal_plan_doc.name}")

        # Add or update meal plan entry
        existing = [
            e for e in meal_plan_doc.meal_plan_entry
            if getdate(e.date) == date and e.meal_type == meal_type and e.get('project_key', '') == project_key
        ]

        if existing:
            e = existing[0]
            e.meal_id = meal_id
            e.meal_name = meal_name
            e.customer = customer
            e.project_key = project_key
        else:
            meal_plan_doc.append("meal_plan_entry", {
                "date": date,
                "meal_type": meal_type,
                "meal_id": meal_id,
                "meal_name": meal_name,
                "customer": customer,
                "project_key": project_key
            })

        # Set selected_projects
        if project_name:
            existing_projects = set(meal_plan_doc.selected_projects.split(", ")) if meal_plan_doc.selected_projects else set()
            existing_projects.add(project_name)
            meal_plan_doc.selected_projects = ", ".join(sorted(existing_projects))

        meal_plan_doc.save()
        frappe.db.commit()

        frappe.log_error("Meal Assignment Debug", f"[DEBUG] Saved plan: {meal_plan_doc.name} for {customer} / {task_name}")
        return "OK"

    except Exception as e:
        error_msg = f"Error in save_meal_assignment: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error("Meal Assignment Error", error_msg)
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
        filters = {"start_date": monday, "docstatus": 0}
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
def submit_weekly_meal_plans_combined_or_individual(monday, combine_shopping_list=False):
    """
    Submit all draft meal plans for the week and generate shopping lists:
       - If combine_shopping_list=True: create ONE combined shopping list for all plans (using total individuals across them).
       - If False: create individual shopping lists per submitted plan.
    """
    from frappe.utils import getdate
    monday = getdate(monday)

    meal_plans = frappe.get_all("Meal Plan", filters={
        "start_date": monday,
        "docstatus": 0
    }, fields=["name", "group_name"])

    if not meal_plans:
        return {"status": "no_plans_found", "message": "No draft meal plans found"}

    shopping_lists = []
    submitted_plans = []

    if combine_shopping_list:
        # ✅ Combined shopping list for all plans
        plan_names = [plan.name for plan in meal_plans]

        # Submit all first
        for plan in meal_plans:
            try:
                plan_doc = frappe.get_doc("Meal Plan", plan.name)
                if not plan_doc.group_name:
                    plan_doc.group_name = plan_doc.customer
                plan_doc.submit()
                submitted_plans.append(plan_doc.name)
            except Exception as e:
                frappe.logger().error(f"Error submitting plan {plan.name}: {str(e)}")

        # Generate one combined shopping list using corrected formula
        combined_list_name = create_combined_shopping_list(plan_names)
        if combined_list_name:
            shopping_lists.append(combined_list_name)

    else:
        # ✅ Individual shopping lists
        for plan in meal_plans:
            try:
                plan_doc = frappe.get_doc("Meal Plan", plan.name)
                if not plan_doc.group_name:
                    plan_doc.group_name = plan_doc.customer

                plan_doc.submit()
                submitted_plans.append(plan_doc.name)

                list_name = _generate_shopping_list(plan_doc)
                if list_name:
                    shopping_lists.append(list_name)

            except Exception as e:
                frappe.logger().error(f"Error submitting plan {plan.name}: {str(e)}")

    return {
        "status": "success",
        "submitted_plans": submitted_plans,
        "shopping_lists": shopping_lists
    }

import math
def create_combined_shopping_list(meal_plan_names):
    if isinstance(meal_plan_names, str):
        meal_plan_names = frappe.parse_json(meal_plan_names)

    if not meal_plan_names:
        frappe.throw("No meal plans provided.")

    frappe.logger().info(f"[START] Combined shopping list for plans: {meal_plan_names}")

    combined_ingredients = {}
    total_individuals = 0
    combined_meal_freq = {}
    group_names = set()

    # First pass: gather total individuals + meal frequencies
    for plan_name in meal_plan_names:
        plan = frappe.get_doc("Meal Plan", plan_name)
        individuals = plan.total_individuals or 1
        total_individuals += individuals
        group_names.add(plan.group_name or "")

        for entry in plan.meal_plan_entry:
            if entry.meal_id:
                key = entry.meal_id
                combined_meal_freq[key] = combined_meal_freq.get(key, 0) + 1

    frappe.logger().info(f"Combined meal frequency: {combined_meal_freq}")
    frappe.logger().info(f"Total individuals across plans: {total_individuals}")

    # Second pass: expand recipes using global total_individuals
    for meal_id, frequency in combined_meal_freq.items():
        try:
            if not frappe.db.exists("Meals", meal_id):
                continue

            meal_doc = frappe.get_doc("Meals", meal_id)
            if not meal_doc.recipes:
                continue

            for recipe in meal_doc.recipes:
                recipe_name = recipe.get('recipe_name')
                if not recipe_name or not frappe.db.exists("Recipe", recipe_name):
                    continue

                recipe_doc = frappe.get_doc("Recipe", recipe_name)

                for ingredient in recipe_doc.ingredients:
                    item_code = ingredient.get('ingredient')
                    if not item_code:
                        continue

                    try:
                        per_person_qty = float(ingredient.get('qty', 0)) or 0   # stock UOM
                        packet_cost    = float(ingredient.get('cost', 0)) or 0 # per purchase UOM
                    except Exception as e:
                        frappe.logger().warning(f"Invalid qty/cost for {item_code}: {e}")
                        per_person_qty = 0
                        packet_cost = 0

                    # ✅ Match individual shopping list formula
                    total_qty = per_person_qty * frequency * total_individuals  # stock UOM

                    # Conversion factor → stock→purchase
                    cf_raw = get_item_conversion_factor(item_code)
                    if cf_raw and cf_raw > 0:
                        stock_to_purchase = (cf_raw if cf_raw < 1 else 1.0 / cf_raw)
                    else:
                        stock_to_purchase = 1.0

                    purchase_qty = total_qty * stock_to_purchase
                    total_cost   = purchase_qty * packet_cost

                    uom = ingredient.get('unit_of_measure', '') or ''

                    if item_code in combined_ingredients:
                        combined_ingredients[item_code]['qty']  += purchase_qty
                        combined_ingredients[item_code]['cost'] += total_cost
                        if not combined_ingredients[item_code].get('uom') and uom:
                            combined_ingredients[item_code]['uom'] = uom
                    else:
                        combined_ingredients[item_code] = {
                            'item_code': item_code,
                            'qty': purchase_qty,
                            'cost': total_cost,
                            'uom': uom
                        }

        except Exception as meal_error:
            frappe.logger().error(f"Error processing meal {meal_id}: {meal_error}")

    if not combined_ingredients:
        frappe.msgprint("No ingredients found in the selected meal plans.")
        frappe.logger().warning("No ingredients found for combined list.")
        return None

    shopping_list_doc = frappe.new_doc("Shopping List")
    shopping_list_doc.combined = 1
    shopping_list_doc.meal_plan_names = ", ".join(meal_plan_names)
    shopping_list_doc.title = f"Combined List: {frappe.utils.nowdate()}"
    shopping_list_doc.meal_plan_link = ", ".join(meal_plan_names)
    shopping_list_doc.customer_group = ", ".join(sorted(group_names))

    for item_code, item_data in combined_ingredients.items():
        shopping_list_doc.append("shopping_details", {
            "item_code": item_code,
            "qty": item_data['qty'],
            "cost": item_data['cost'],
            "uom": item_data.get('uom', '')
        })

    shopping_list_doc.save()
    frappe.msgprint(f"Combined Shopping List created: {shopping_list_doc.name} with {len(combined_ingredients)} unique ingredients")
    frappe.logger().info(f"[DONE] Combined Shopping List: {shopping_list_doc.name}")

    return shopping_list_doc.name

@frappe.whitelist()
def submit_meal_plan_and_create_shopping_list(monday, combine=False):
    from frappe.utils import getdate
    from datetime import timedelta

    monday = getdate(monday)
    sunday = monday + timedelta(days=6)
    combine = frappe.parse_json(combine)

    # 🔍 Filter draft Meal Plans in that week
    meal_plans = frappe.get_all("Meal Plan", filters={
    "start_date": ["<=", sunday],
    "end_date": [">=", monday],
    "docstatus": 0
    }, fields=["name", "group_name", "start_date", "end_date"])

    if not meal_plans:
        return {
            "status": "error",
            "message": "No draft meal plans found for the selected week."
        }

    if combine:
        plan_names = [mp.name for mp in meal_plans]

        shopping_list = create_combined_shopping_list(plan_names)

        for plan_name in plan_names:
            frappe.get_doc("Meal Plan", plan_name).submit()

        return {
            "status": "success",
            "message": f"Combined shopping list created for {len(plan_names)} meal plans.",
            "list": shopping_list
        }

    else:
        results = []

        for mp in meal_plans:
            try:
                plan_doc = frappe.get_doc("Meal Plan", mp.name)

                shopping_list = _generate_shopping_list(plan_doc)

                plan_doc.submit()

                results.append({
                    "group": plan_doc.group_name,
                    "meal_plan": plan_doc.name,
                    "shopping_list": shopping_list
                })

            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Error processing meal plan {mp.name}")
                results.append({
                    "group": mp.group_name,
                    "meal_plan": mp.name,
                    "error": str(e)
                })

        return {
            "status": "success",
            "message": f"Submitted {len(results)} meal plans and created individual shopping lists.",
            "details": results
        }


def get_projects_for_week(monday):
    """Get projects that have tasks in the given week"""
    try:
        from datetime import timedelta
        
        sunday = monday + timedelta(days=6)
        
        # Get tasks for the week
        tasks = frappe.get_all("Task", filters={
            "subject": "Meal Plan Allocation",
            "exp_start_date": ["<=", sunday],
            "exp_end_date": [">=", monday],
            "custom_is_meals_at_camp": 1
        }, fields=["project"])
        
        projects = [task.project for task in tasks if task.project]
        return list(set(projects))  # Remove duplicates
        
    except Exception as e:
        frappe.logger().error(f"Error getting projects for week: {str(e)}")
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
            monday = date - timedelta(days=date.weekday())
            
            # Find meal plans for this week that are NOT cancelled
            meal_plans = frappe.get_all("Meal Plan", 
                filters={
                    "start_date": monday,
                    "docstatus": ["!=", 2]  
                }, 
                fields=["name", "docstatus"]
            )
            
            for meal_plan in meal_plans:
                # Skip if meal plan is cancelled
                if meal_plan.docstatus == 2:
                    continue
                    
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
def create_shopping_list(monday):
    """API method: Create shopping list for the meal plan of a given Monday"""
    try:
        frappe.logger().info(f"[API CALL] Creating shopping list for Monday: {monday}")

        meal_plans = frappe.get_all("Meal Plan", filters={"start_date": monday}, fields=["name"])

        if not meal_plans:
            error_msg = f"No Meal Plan found for Monday: {monday}"
            frappe.msgprint(error_msg)
            frappe.logger().error(error_msg)
            return None

        # Get meal plans
        meal_plan = frappe.get_doc("Meal Plan", meal_plans[0].name)
        frappe.logger().info(f"Found meal plan: {meal_plan.name}")

        return _generate_shopping_list(meal_plan)

    except Exception as e:
        error_msg = f"Error creating shopping list: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error(error_msg)
        frappe.msgprint(error_msg)
        return None


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
            shopping_list_doc.meal_pan = meal_plan_doc.group_name or ""
            shopping_list_doc.selected_projects = meal_plan_doc.selected_projects or ""
            frappe.logger().info("Creating new Shopping List")

        ingredient_totals = {}
        unique_meals = set()
        meal_frequency = {}

        if not meal_plan_doc.meal_plan_entry:
            frappe.msgprint(f"No meal entries found in meal plan {meal_plan_doc.name}")
            frappe.logger().warning(f"No meal entries in meal plan {meal_plan_doc.name}")
            return None

        for entry in meal_plan_doc.meal_plan_entry:
            if entry.meal_id:
                unique_meals.add(entry.meal_id)
                meal_frequency[entry.meal_id] = meal_frequency.get(entry.meal_id, 0) + 1

        MAX_COST = 99999999.99

        for meal_id in unique_meals:
            try:
                if not frappe.db.exists("Meals", meal_id):
                    frappe.logger().warning(f"Meal {meal_id} does not exist, skipping")
                    continue

                meal_doc = frappe.get_doc("Meals", meal_id)
                frequency = meal_frequency[meal_id]
                frappe.logger().info(f"Processing meal {meal_id} (frequency: {frequency})")

                if hasattr(meal_doc, 'recipes') and meal_doc.recipes:
                    for recipe in meal_doc.recipes:
                        recipe_name = recipe.get('recipe_name')
                        if not recipe_name or not frappe.db.exists("Recipe", recipe_name):
                            continue

                        recipe_doc = frappe.get_doc("Recipe", recipe_name)

                        if hasattr(recipe_doc, 'ingredients') and recipe_doc.ingredients:
                            for ingredient in recipe_doc.ingredients:
                                item_code = ingredient.get('ingredient')
                                if not item_code:
                                    continue

                                try:
                                    per_person_qty = float(ingredient.get('qty', 0)) or 0   # stock UOM
                                    packet_cost    = float(ingredient.get('cost', 0)) or 0 # per purchase UOM
                                except Exception as e:
                                    frappe.logger().warning(f"Invalid qty or cost for {item_code}: {e}")
                                    per_person_qty = 0
                                    packet_cost = 0

                                total_qty = per_person_qty * frequency * total_individuals  # stock UOM

                                # Normalize conversion factor → stock→purchase
                                cf_raw = get_item_conversion_factor(item_code)
                                if cf_raw and cf_raw > 0:
                                    stock_to_purchase = (cf_raw if cf_raw < 1 else 1.0 / cf_raw)
                                else:
                                    stock_to_purchase = 1.0

                                purchase_qty = total_qty * stock_to_purchase  # purchase UOM
                                total_cost = purchase_qty * packet_cost       # raw float

                                if total_cost > MAX_COST:
                                    total_cost = MAX_COST

                                uom = ingredient.get('unit_of_measure', '') or ''

                                if item_code in ingredient_totals:
                                    ingredient_totals[item_code]['qty']  += purchase_qty
                                    ingredient_totals[item_code]['cost'] += total_cost
                                else:
                                    ingredient_totals[item_code] = {
                                        'item_code': item_code,
                                        'qty': purchase_qty,
                                        'cost': total_cost,
                                        'uom': uom
                                    }

                                frappe.msgprint(
                                    f"[COST TRACE] {item_code}: stock_qty={total_qty}, cf_raw={cf_raw}, "
                                    f"stock->purchase={stock_to_purchase}, purchase_qty={purchase_qty}, "
                                    f"packet_cost(per purchase)={packet_cost}, total_cost={total_cost}"
                                )

            except Exception as meal_error:
                frappe.logger().error(f"Error processing meal {meal_id}: {str(meal_error)}")

        if not ingredient_totals:
            frappe.msgprint("No ingredients found to create shopping list")
            frappe.logger().warning("No ingredients found to create shopping list")
            return None

        for item_code, ingredient_data in ingredient_totals.items():
            shopping_list_doc.append("shopping_details", {
                "item_code": item_code,
                "qty": ingredient_data['qty'],     # raw float
                "cost": ingredient_data['cost'],   # raw float
                "uom": ingredient_data.get('uom', '')
            })

        shopping_list_doc.save()
        frappe.msgprint(
            f"Shopping List created/updated: {shopping_list_doc.name} for {total_individuals} people "
            f"with {len(ingredient_totals)} unique ingredients"
        )
        return shopping_list_doc.name

    except Exception as e:
        error_msg = f"Error generating shopping list: {str(e)}"
        frappe.logger().error(error_msg)
        frappe.log_error(error_msg)
        frappe.msgprint(error_msg)
        return None

def get_item_conversion_factor(item_code):
    """
    Get conversion factor for an item from Item doctype or UOM Conversion Detail
    Returns the conversion factor or None if not found
    """
    try:
        # First, check if the item exists
        if not frappe.db.exists("Item", item_code):
            frappe.logger().warning(f"Item {item_code} does not exist")
            return None
        
        # Get the item document
        item_doc = frappe.get_doc("Item", item_code)
        
        # Option 1: Check if there's a direct conversion_factor field in Item
        if hasattr(item_doc, 'conversion_factor') and item_doc.conversion_factor:
            frappe.logger().info(f"Found direct conversion factor {item_doc.conversion_factor} for {item_code}")
            return float(item_doc.conversion_factor)
        
        # Option 2: Check UOM Conversion Detail child table
        if hasattr(item_doc, 'uoms') and item_doc.uoms:
            # Look for the first UOM conversion entry
            for uom_conversion in item_doc.uoms:
                if uom_conversion.conversion_factor:
                    conversion_factor = float(uom_conversion.conversion_factor)
                    frappe.logger().info(f"Found UOM conversion factor {conversion_factor} for {item_code} (UOM: {uom_conversion.uom})")
                    return conversion_factor
        
        # Option 3: Check if there's a default conversion factor in stock UOM
        stock_uom = getattr(item_doc, 'stock_uom', None)
        if stock_uom:
            # Query UOM Conversion Factor doctype if it exists
            uom_conversion = frappe.get_all("UOM Conversion Factor", 
                filters={
                    "from_uom": stock_uom,
                    "to_uom": ["!=", stock_uom]
                }, 
                fields=["value"], 
                limit=1
            )
            
            if uom_conversion:
                conversion_factor = float(uom_conversion[0].value)
                frappe.logger().info(f"Found UOM Conversion Factor {conversion_factor} for {item_code}")
                return conversion_factor
        
        frappe.logger().info(f"No conversion factor found for {item_code}")
        return None
        
    except Exception as e:
        frappe.logger().error(f"Error getting conversion factor for {item_code}: {str(e)}")
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
    
    
@frappe.whitelist()
def get_all_meals_with_categories():
    meals = frappe.get_all("Meals", fields=["name", "meal_name", "creation"])
    for m in meals:
        m["meal_plan_category"] = frappe.get_all(
            "Meal Plan Category",
            filters={"parent": m.name},
            fields=["category"]
        )
    return meals
