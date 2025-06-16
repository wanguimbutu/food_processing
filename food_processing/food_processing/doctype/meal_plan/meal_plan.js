frappe.ui.form.on('Meal Plan', {
    refresh: function(frm) {
        setup_meal_drag_and_drop(frm);
        render_meal_plan_table(frm)
        load_existing_meals(frm);
        
        if (frm.doc.meal_plan_html && frm.fields_dict.meal_plan_html) {
            console.log("Loading saved meal_plan_html:", frm.doc.meal_plan_html);
            frm.fields_dict.meal_plan_html.$wrapper.html(frm.doc.meal_plan_html);
        }

        
        frm.add_custom_button(__('Select Groups'), function() {
            frappe.prompt([
                {
                    label: 'From Date',
                    fieldname: 'from_date',
                    fieldtype: 'Date',
                    reqd: 1
                },
                {
                    label: 'To Date',
                    fieldname: 'to_date',
                    fieldtype: 'Date',
                    reqd: 1
                }
            ], function(date_data) {
                frm.set_value('start_date', date_data.from_date);
                frm.set_value('end_date', date_data.to_date);
                frm.refresh_fields(['start_date', 'end_date']);

                // Fetch open tasks for Meal Plan Allocation
                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Task',
                        filters: {
                            subject: 'Meal Plan Allocation',
                            status: 'Open'
                        },
                        fields: ['name', 'project']
                    },
                    callback: function(response) {
                        if (response.message) {
                            let tasks = response.message;
                            if (tasks.length === 0) {
                                frappe.msgprint(__('No open Meal Plan Allocation tasks found.'));
                                return;
                            }

                            let project_ids = [...new Set(tasks.map(task => task.project))];

                            // Fetch projects within the selected date range
                            frappe.call({
                                method: 'frappe.client.get_list',
                                args: {
                                    doctype: 'Project',
                                    filters: [
                                        ['name', 'in', project_ids],
                                        ['expected_start_date', '>=', date_data.from_date],
                                        ['expected_end_date', '<=', date_data.to_date]
                                    ],
                                    fields: ['name', 'customer', 'custom_no_of_people']
                                },
                                callback: function(proj_res) {
                                    if (proj_res.message) {
                                        let projects = proj_res.message;
                                        let project_map = {};

                                        let fields = projects.map((proj, index) => {
                                            let label = `${proj.name} - ${proj.customer} (${proj.custom_no_of_people || 0} people)`;
                                            project_map[proj.name] = proj.custom_no_of_people || 0;
                                            
                                            return {
                                                label: label,
                                                fieldname: `proj_${index}`,
                                                fieldtype: 'Check'
                                            };
                                        });

                                        if (fields.length === 0) {
                                            frappe.msgprint(__('No projects match the selected date range.'));
                                            return;
                                        }

                                        // Display checkboxes for project selection
                                        frappe.prompt(fields, function(data) {
                                            let selected_projects = [];
                                            let total_people = 0;

                                            Object.keys(data).forEach(fieldname => {
                                                if (data[fieldname]) {
                                                    let proj_name = fieldname.replace('proj_', '');
                                                    let selected_proj = projects[proj_name].name;
                                                    selected_projects.push(selected_proj);
                                                    total_people += project_map[selected_proj];
                                                }
                                            });

                                            // Update the form fields
                                            frm.set_value('selected_projects', selected_projects.join(', '));
                                            frm.set_value('total_individuals', total_people);
                                            frm.refresh_fields(['selected_projects', 'total_individuals']);

                                        }, __('Select Groups'), __('Confirm'));
                                    }
                                }
                            });
                        }
                    }
                });
            }, __('Select Date Range'), __('Next'));
        });
        frm.add_custom_button(__('Check Overlapping Plans'), function() {
            if (!frm.doc.start_date || !frm.doc.end_date) {
                frappe.msgprint(__('Please set both Start Date and End Date before checking.'));
                return;
            }

            frappe.call({
                method: "food_processing.food_processing.doctype.meal_plan.meal_plan.check_meal_plan_overlap",
                args: {
                    meal_plan_name: frm.doc.name,
                    start_date: frm.doc.start_date,
                    end_date: frm.doc.end_date
                },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.msgprint(r.message || "Updated from overlapping meal plan.");
                        frm.reload_doc();  // Refresh the form with copied data
                    }
                }
            });
            
            
        }).addClass("btn-secondary");
    },

    small_appetite: function(frm) {
        validate_and_calculate(frm);
    },
    normal_appetite: function(frm) {
        validate_and_calculate(frm);
    },
    large_appetite: function(frm) {
        validate_and_calculate(frm);
    },
    start_date: function(frm) {
        render_meal_plan_table(frm); 
        load_existing_meals(frm);
    },
    end_date: function(frm) {
        render_meal_plan_table(frm); 
        load_existing_meals(frm);
    },
    after_submit:function(frm){
        frappe.msgprint("Meal Plan Submitted");
        fetch_meal_ingredients(frm);
    },
   
    on_submit: function(frm) {        
        console.log("Meal Plan Submitted:", frm.doc.name);
        fetch_meal_ingredients(frm);

        if (!frm.doc.task) {
            frappe.msgprint(__("No associated task found."));
            console.warn(" No associated Task found in Meal Plan.");
            return;
        }

        console.log("🔹 Marking Task as Completed:", frm.doc.custom_task);

        //  Update the Task to Completed
        frappe.call({
            method: "frappe.client.set_value",
            args: {
                doctype: "Task",
                name: frm.doc.task,
                fieldname: {
                    status: "Completed",
                    completed_on: frappe.datetime.get_today(),
                    completed_by: frappe.session.user
                }
            },
            callback: function(response) {
                if (response.message) {
                    console.log(" Task marked as Completed:", frm.doc.custom_task);
                    frappe.msgprint(__("Task has been marked as completed."));
                } else {
                    frappe.msgprint(__("Failed to update task."));
                    console.error(" Error marking Task as Completed:", response);
                }
            },
            error: function(err) {
                console.error(" API Call Failed when updating Task:", err);
            }
        }); 

        if (frm.doc.selected_projects) {
            let selected_projects = frm.doc.selected_projects.split(', ').map(p => p.trim());
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Task',
                    filters: {
                        project: ['in', selected_projects],
                        subject: 'Meal Plan Allocation',
                        status: 'Open'
                    },
                    fields: ['name']
                },
                callback: function(response) {
                    if (response.message.length > 0) {
                        let tasks = response.message;

                        // Loop through each task and update its status to 'Working'
                        tasks.forEach(task => {
                            frappe.call({
                                method: 'frappe.client.set_value',
                                args: {
                                    doctype: 'Task',
                                    name: task.name,  
                                    fieldname: 'status',
                                    value: 'Working'
                                }
                            });
                        });

                        frappe.msgprint(__('Meal Plan Allocation tasks marked as Working.'));
                    } else {
                        frappe.msgprint(__('No open Meal Plan Allocation tasks found to update.'));
                    }
                }
            });
        }
       /* if(frm.doc.docstatus ==1){
            console.log("Fetching meal ingredients")
            fetch_meal_ingredients(frm);
        }*/
        if (frm.doc.packing_list) {
            frappe.call({
                method: 'frappe.client.set_value',
                args: {
                    doctype: 'Packing List',
                    name: frm.doc.packing_list,
                    fieldname: {
                        meal_plan: frm.doc.name
                    }
                },
                callback: function(r) {
                    if (!r.exc) {
                        frm.save();
                    }
                }
            });
        
            frappe.validated = false;
        }
        
        validate_and_calculate(frm);

    }
    
});



function render_meal_plan_table(frm) {
    let start_date = frm.doc.start_date;
    let end_date = frm.doc.end_date;

    if (!start_date || !end_date) {
        return; 
    }

    let start = moment(start_date);
    let end = moment(end_date);

    if (end.isBefore(start)) {
        frappe.msgprint(__('End date cannot be before start date.'));
        return;
    }

    let html = `
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Breakfast</th>
                    <th>Lunch</th>
                    <th>Dinner</th>
                    <th>Snack & Beverage</th>
                    <th>Dessert</th>
                </tr>
            </thead>
            <tbody>
    `;

    for (let date = moment(start); date.isSameOrBefore(end); date.add(1, 'days')) {
        let formatted_date = date.format('YYYY-MM-DD');
        let display_date = date.format('ddd MM/DD/YY'); 

        html += `
            <tr data-date="${formatted_date}">
                <td>${display_date}</td>
                <td data-meal-type="Breakfast" class="drop-zone"></td>
                <td data-meal-type="Lunch" class="drop-zone"></td>
                <td data-meal-type="Dinner" class="drop-zone"></td>
                <td data-meal-type="Snack & Beverage" class="drop-zone"></td>
                <td data-meal-type="Dessert" class="drop-zone"></td>
            </tr>
        `;
    }

    html += `</tbody></table>`;

    frm.fields_dict.meal_plan_table.$wrapper.html(html);


    setup_meal_drag_and_drop(frm);
    
}
function setup_meal_drag_and_drop(frm) {
    if (!frm.fields_dict.meal_list) return;

    const meal_container = $(frm.fields_dict.meal_list.wrapper);
    meal_container.find(".draggable-meal").remove();

    let currentPage = 1;
    const itemsPerPage = 5;
    let currentSort = "asc";
    let selectedCategory = localStorage.getItem("selected_meal_category") || "All";

    // Inject UI elements once
    if (!meal_container.find("#meal_category_filter").length) {
        const html = `
            <div style="margin-bottom: 10px;">
                <label><b>Filter by Category:</b></label>
                <select id="meal_category_filter" style="width: 100%; padding: 5px;">
                    <option value="All">All</option>
                </select>
            </div>
            <div style="margin: 10px 0;">
                <label><b>Sort by:</b></label>
                <select id="meal_sort" style="width: 100%; padding: 5px;">
                    <option value="asc">Name A-Z</option>
                    <option value="desc">Name Z-A</option>
                </select>
            </div>
            <div id="pagination_controls" style="margin-top:10px; display:flex; justify-content:space-between;">
                <button id="prev_page">Previous</button>
                <span id="page_info">Page 1</span>
                <button id="next_page">Next</button>
            </div>
        `;
        meal_container.append(html);
    }

    const filterDropdown = $("#meal_category_filter");
    const sortDropdown = $("#meal_sort");

    if (filterDropdown.find("option").length === 1) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Meal Category",
                fields: ["name"]
            },
            callback: function (res) {
                if (res.message) {
                    res.message.forEach(cat => {
                        filterDropdown.append(`<option value="${cat.name}">${cat.name}</option>`);
                    });
                    filterDropdown.val(selectedCategory);
                }
            }
        });
    } else {
        filterDropdown.val(selectedCategory);
    }

    function loadMeals() {
        selectedCategory = filterDropdown.val();
        localStorage.setItem("selected_meal_category", selectedCategory);
        currentSort = sortDropdown.val();
    
        let filters = [];
    
        if (selectedCategory === "All") {
            frappe.call({
                method: "frappe.client.get_list",
                args: {
                    doctype: "Meals",
                    fields: ["name", "meal_name","meal_id"],
                    limit_start: (currentPage - 1) * itemsPerPage,
                    limit_page_length: itemsPerPage,
                    order_by: `meal_name ${currentSort}`,
                },
                callback: render_meals
            });
        } else {
            frappe.call({
                method: "food_processing.food_processing.doctype.meal_plan.meal_plan.get_meals_by_category",
                args: {
                    category: selectedCategory,
                    start: (currentPage - 1) * itemsPerPage,
                    page_length: itemsPerPage,
                    sort_order: currentSort
                },
                callback: render_meals
            });
        }
        
        function render_meals(res) {
            meal_container.find(".draggable-meal").remove();
        
            if (res.message && res.message.length > 0) {
                res.message.forEach(meal => {
                    let item = $("<div>")
                        .text(meal.meal_name)
                        .attr("data-meal", meal.meal_id)
                        .addClass("draggable-meal")
                        .css({
                            "border": "1px solid #ccc",
                            "padding": "5px",
                            "margin": "5px 0",
                            "background-color": "#ffffff",
                            "cursor": "grab",
                            "width": "80%",
                            "text-align": "center"
                        })
                        .attr("draggable", true);
        
                    item.on("dragstart", function (event) {
                        event.originalEvent.dataTransfer.setData("meal", $(this).attr("data-meal"));
                        event.originalEvent.dataTransfer.setData("meal_name", $(this).text());
                    });
        
                    meal_container.append(item);
                });
        
                $("#page_info").text(`Page ${currentPage}`);
                $("#prev_page").prop("disabled", currentPage === 1);
                $("#next_page").prop("disabled", res.message.length < itemsPerPage);
            } else {
                $("#page_info").text("No meals found");
                $("#next_page").prop("disabled", true);
            }
        }
    }        
    

    if (!frm.__meals_loaded) {
        loadMeals();
        frm.__meals_loaded = true;
    }

    filterDropdown.off("change").on("change", function () {
        currentPage = 1;
        loadMeals();
    });

    sortDropdown.off("change").on("change", function () {
        currentPage = 1;
        loadMeals();
    });

    $("#prev_page").on("click", function () {
        if (currentPage > 1) {
            currentPage--;
            loadMeals();
        }
    });

    $("#next_page").on("click", function () {
        currentPage++;
        loadMeals();
    });

    // Setup drop zones
    ["Breakfast", "Lunch", "Dinner", "Snack & Beverage", "Dessert"].forEach(type => {
        $(`td[data-meal-type="${type}"]`).on("dragover", function (event) {
            event.preventDefault();
        });

        $(`td[data-meal-type]`).on("drop", function (event) {
            event.preventDefault();
            let meal_id = event.originalEvent.dataTransfer.getData("meal");
            let meal_name = event.originalEvent.dataTransfer.getData("meal_name");
            let selected_date = $(event.target).closest("tr").attr("data-date");
            let meal_type = $(event.target).attr("data-meal-type");

            if (meal_id && meal_name) {
                if ($(event.target).find(`[data-meal-id="${meal_id}"]`).length > 0) return;

                let mealItem = $(`
                    <div class="meal-item" data-meal-id="${meal_id}" style="padding:5px; background:#f2f2f2; margin:3px; display:flex; justify-content:space-between;">
                        <span>${meal_name}</span>
                        <button class="remove-meal" style="background:red; color:white; border:none; padding:2px 5px;">X</button>
                    </div>
                `);

                meal_container.on("click", ".remove-meal", function () {
                    const mealItem = $(this).closest(".meal-item");
                    const meal_id = mealItem.attr("data-meal-id");
                    const selected_date = mealItem.closest("tr").attr("data-date");
                    const meal_type = mealItem.closest("td").attr("data-meal-type");
                
                    mealItem.remove();
                    remove_meal_from_plan(frm, meal_id, selected_date, meal_type);
                });
                

                $(event.target).append(mealItem);
                add_meal_to_plan(frm, meal_id, meal_name, selected_date, meal_type);
            }
        });
    });
}

function add_meal_to_plan(frm, meal_id, meal_name, date, meal_type) {
    frappe.call({
        method: "food_processing.food_processing.doctype.meal_plan.meal_plan.is_lsg_meal",
        args: { meal_id: meal_id },
        callback: function(response) {
            let is_lsg = response.message;

            let row = frm.add_child("meal_plan_entry");
            row.meal_id = meal_id;
            row.meal_name = meal_name;
            row.meal_type = meal_type;
            row.date = date;

            if (is_lsg) {
                frappe.prompt([
                    {
                        label: "Selected Percentage",
                        fieldname: "selected_percentage",
                        fieldtype: "Float",
                        reqd: 1,
                        description: "Enter the percentage as a decimal (e.g., 0.2 for 20%)"
                    }
                ], function(values) {
                    row.selected_percentage = values.selected_percentage;
                    frm.refresh_field("meal_plan_entry");
                    calculate_meal_costs(frm);  
                }, "Enter Percentage for LSG Meal", "Submit");
            } else {
                frm.refresh_field("meal_plan_entry");
                calculate_meal_costs(frm);  
            }
        }
    });
}


function remove_meal_from_plan(frm, meal_id, date, meal_type) {
    let entries = frm.doc.meal_plan_entry || [];
    
    let updatedEntries = entries.filter(entry => 
        !(entry.meal_id === meal_id && entry.date === date && entry.meal_type === meal_type)
    );

    frm.doc.meal_plan_entry = updatedEntries;
    frm.refresh_field("meal_plan_entry");

    calculate_meal_costs(frm);
}



function prompt_for_meal_details(frm, meal) {
    let meal_types = ["BREAKFAST", "LUNCH", "DINNER", "SNACKS", "DESSERT"];

    frappe.prompt([
        {
            label: "Select Date",
            fieldname: "selected_date",
            fieldtype: "Date",
            reqd: 1
        },
        {
            label: "Meal Type",
            fieldname: "meal_type",
            fieldtype: "Select",
            options: meal_types.join("\n"),
            reqd: 1
        }
    ],
    function(values) {
        let row = frm.add_child("meal_plan_entry");
        row.meal_id = meal.name;
        row.meal_name = meal.meal_name;
        row.meal_type = values.meal_type;
        row.date = values.selected_date;
        frm.refresh_field("meal_plan_entry");

        fetch_meal_ingredients(frm, meal.name);
    },
    "Add Meal to Meal Plan",
    "Add");
}
function load_existing_meals(frm) {
    if (!frm.doc.meal_plan_entry || frm.doc.meal_plan_entry.length === 0) return;


    $("td[data-meal-type]").empty();

    frm.doc.meal_plan_entry.forEach(entry => {
        let cell = $(`tr[data-date="${entry.date}"] td[data-meal-type="${entry.meal_type}"]`);
        if (cell.length) {
            cell.append(`<div class="meal-item" style="padding:5px; background:#f2f2f2; margin:3px;">${entry.meal_name}</div>`);
        }
    });
}

function validate_and_calculate(frm) {
    let small = frm.doc.small_appetite || 0;
    let normal = frm.doc.normal_appetite || 0;
    let large = frm.doc.large_appetite || 0;
    let total_individuals = frm.doc.total_individuals || 0;

    let total_entered = small + normal + large;

    if (total_entered > total_individuals) {
        frappe.msgprint(__('The sum of small, normal, and large appetite individuals cannot exceed Total Individuals (' + total_individuals + '). Please adjust the values.'));
        return;
    }

    let total_servings = (small * 0.75) + (normal * 1) + (large * 1.25);
    frm.set_value('total_servings', total_servings);
}

function fetch_meal_ingredients(frm) {
    console.log("Fetching meal ingredients...");

    let total_servings = frm.doc.total_servings || 1;
    let total_individuals = frm.doc.total_individuals || 1;
    let meal_entries = frm.doc.meal_plan_entry || [];

    if (meal_entries.length === 0) {
        frappe.msgprint(__('No meals selected in the meal plan.'));
        return;
    }

    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Shopping List",
            filters: { "meal_plan": frm.doc.name,
               
            },
            fields: ["name"]
        },
        callback: function(existing) {
            if (existing.message.length > 0) {
                console.log("A shopping list already exists. Skipping creation.");
                return;
            }

            let meal_data = meal_entries.map(entry => ({
                meal_id: entry.meal_id,
                meal_type: entry.meal_type,
                meal_category: entry.meal_category,
                selected_percentage: entry.selected_percentage || 0
            }));

            console.log("Meal Entries to fetch:", meal_data);

            frappe.call({
                method: "food_processing.food_processing.doctype.meal_plan.meal_plan.fetch_ingredients",
                args: {
                    meal_data: meal_data,
                    total_servings: total_servings,
                    total_individuals: total_individuals
                },
                callback: function(r) {
                    console.log("Fetched ingredients:", r.message);

                    if (!r.message || r.message.length === 0) {
                        frappe.msgprint(__('No ingredients found for the selected meals.'));
                        return;
                    }

                    let shopping_list = r.message.map(ingredient => {
                        let qty = ingredient.qty;
                        let entry = meal_entries.find(e => e.meal_id === ingredient.meal_id);
                        
                        if (entry) {
                            if (entry.meal_category === "LSG" && entry.selected_percentage) {
                                qty *= entry.selected_percentage;
                            } else {
                                qty *= total_servings;
                            }
                        }

                        return {
                            item_code: ingredient.ingredient,
                            item_name: ingredient.ingredient_name,
                            qty: qty,
                            cost: ingredient.cost,
                            uom:ingredient.unit_of_measure
                        };
                    });

                    console.log("Final Shopping List:", shopping_list);

                    frappe.call({
                        method: "frappe.client.insert",
                        args: {
                            doc: {
                                doctype: "Shopping List",
                                meal_plan: frm.doc.name,
                                shopping_details: shopping_list,
                                group_name:frm.doc.group_name,
                                required_by: frm.doc.required_by,
                                packing_list:frm.doc.packing_list
                            }
                        },
                        callback: function(res) {
                            console.log("Created Shopping List:", res.message);
                            if (res.message) {
                                frappe.msgprint({
                                    title: __("Success"),
                                    message: `Ingredients added to Shopping List <b>${res.message.name}</b>.`,
                                    indicator: "green"
                                });
                            
                            
                               //frappe.set_route('Form', 'Shopping List', res.message.name);
                            }
                            
                        }
                    });
                }
            });
        }
    });
}


function calculate_meal_costs(frm) {
    let meal_entries = frm.doc.meal_plan_entry || [];

    if (meal_entries.length === 0) {
        console.log("No meals selected, skipping cost calculation.");
        return;
    }

    let meal_ids = [...new Set(meal_entries.map(entry => entry.meal_id))];

    if (meal_ids.length === 0) {
        console.log("No valid meal IDs found, skipping cost calculation.");
        return;
    }

    let daily_costs = {};
    let total_cost = 0;
    let total_individuals = frm.doc.total_individuals || 1; 

    console.log("Fetching meal costs for:", meal_ids);

    frappe.call({
        method: "food_processing.food_processing.doctype.meal_plan.meal_plan.get_meal_cost_data",
        args: {
            meal_ids: meal_ids
        },
        callback: function(response) {
            console.log("API Response: ", response);
    
            if (!response.message || response.message.length === 0) {
                frappe.msgprint(__('No valid meal costs found. Please check meal selections.'));
                return;
            }
    
            let meal_cost_map = {};
    
            response.message.forEach(meal => {
                meal_cost_map[meal.meal_id] = {
                    cost: meal.total_meal_cost || 0,
                    category: meal.category || "Unknown"  
                };
            });
    
            console.log("Meal Cost Map:", meal_cost_map);
    
            meal_entries.forEach(entry => {
                let meal_info = meal_cost_map[entry.meal_id] || { cost: 0, category: "Unknown" };
                let meal_cost = meal_info.cost * total_individuals;
    
                if (!daily_costs[entry.date]) {
                    daily_costs[entry.date] = 0;
                }
                daily_costs[entry.date] += meal_cost;
                total_cost += meal_cost;
            });
    
            console.log("Daily Costs Calculated:", daily_costs);
    
            frm.clear_table("daily_meal_costs");
            Object.keys(daily_costs).forEach(date => {
                let row = frm.add_child("daily_meal_costs");
                row.date = date;
                row.meal_cost = daily_costs[date];
            });
    
            frm.set_value("total_meal_plan_cost", total_cost);
    
            frm.refresh_field("daily_meal_costs");
            frm.refresh_field("total_meal_plan_cost");
        }
    });
}    