frappe.ui.form.on('Meal Plan', {
    refresh: function(frm) {
        setup_meal_drag_and_drop(frm);
        render_meal_plan_table(frm);
        load_existing_meals(frm);
    
        if(frm.doc.docstatus ==1){
            console.log("Fetching meal ingredients")
            fetch_meal_ingredients(frm);
        }
        
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

    let meal_container = $(frm.fields_dict.meal_list.wrapper);
    
    meal_container.find(".draggable-meal").remove(); 

    let previouslySelected = localStorage.getItem("selected_meal_category") || "All";

    if (!meal_container.find("#meal_category_filter").length) {
        let filter_html = `
            <div style="margin-bottom: 10px;">
                <label for="meal_category_filter"><b>Filter by Category:</b></label>
                <select id="meal_category_filter" style="width: 100%; padding: 5px;">
                    <option value="All">All</option>
                </select>
            </div>
        `;
        meal_container.append(filter_html);
    }

    let filterDropdown = $("#meal_category_filter");

    if (filterDropdown.find("option").length === 1) {
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Meal Category",
                fields: ["name"]
            },
            callback: function(response) {
                if (response.message) {
                    response.message.forEach(cat => {
                        filterDropdown.append(`<option value="${cat.name}">${cat.name}</option>`);
                    });
                    filterDropdown.val(previouslySelected);
                }
            }
        });
    } else {
        filterDropdown.val(previouslySelected);
    }

    function loadFilteredMeals() {
        let selected_category = filterDropdown.val();
        localStorage.setItem("selected_meal_category", selected_category);
        meal_container.find(".draggable-meal").remove(); 

        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Meals",
                fields: ["name", "meal_name", "meal_category"]
            },
            callback: function(response) {
                if (response.message) {
                    let uniqueMeals = new Set(); 

                    response.message.forEach(meal => {
                        if (selected_category !== "All" && meal.meal_category !== selected_category) {
                            return;
                        }

                        if (uniqueMeals.has(meal.name)) return; // ✅ Skip duplicates
                        uniqueMeals.add(meal.name);

                        let item = $("<div>")
                            .text(meal.meal_name)
                            .attr("data-meal", meal.name)
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

                        item.on("dragstart", function(event) {
                            event.originalEvent.dataTransfer.setData("meal", $(this).attr("data-meal"));
                            event.originalEvent.dataTransfer.setData("meal_name", $(this).text());
                        });

                        meal_container.append(item);
                    });
                }
            }
        });
    }

    
    if (!frm.__meals_loaded) {
        loadFilteredMeals();
        frm.__meals_loaded = true;
    }

    filterDropdown.off("change").on("change", function() {
        loadFilteredMeals();
    });
    // Attach drop events
    let meal_types = ["Breakfast", "Lunch", "Dinner", "Snack & Beverage", "Dessert"];

    meal_types.forEach(type => {
        $(`td[data-meal-type="${type}"]`).on("dragover", function(event) {
            event.preventDefault();
        });

        $(`td[data-meal-type]`).on("drop", function(event) {
            event.preventDefault();
            let meal_id = event.originalEvent.dataTransfer.getData("meal");
            let meal_name = event.originalEvent.dataTransfer.getData("meal_name");
            let selected_date = $(event.target).closest("tr").attr("data-date");
            let meal_type = $(event.target).attr("data-meal-type");
        
            if (meal_id && meal_name) {
                if ($(event.target).find(`[data-meal-id="${meal_id}"]`).length > 0) {
                    return;
                }
        
                let mealItem = $(`
                    <div class="meal-item" data-meal-id="${meal_id}" style="padding:5px; background:#f2f2f2; margin:3px; position:relative; display:flex; justify-content:space-between; align-items:center;">
                        <span>${meal_name}</span>
                        <button class="remove-meal" style="border:none; background:red; color:white; padding:2px 5px; cursor:pointer;">X</button>
                    </div>
                `);
        
                mealItem.find(".remove-meal").on("click", function() {
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
    
    let exists = frm.doc.meal_plan_entry.some(entry =>
        entry.meal_id === meal_id &&
        entry.date === date &&
        entry.meal_type === meal_type
    );

    if (!exists) {
        let row = frm.add_child("meal_plan_entry");
        row.meal_id = meal_id;
        row.meal_name = meal_name;
        row.meal_type = meal_type;
        row.date = date;
        frm.refresh_field("meal_plan_entry");
    }
}

function remove_meal_from_plan(frm, meal_id, date, meal_type) {
    let entries = frm.doc.meal_plan_entry || [];
    

    let updatedEntries = entries.filter(entry => 
        !(entry.meal_id === meal_id && entry.date === date && entry.meal_type === meal_type)
    );

    
    frm.doc.meal_plan_entry = updatedEntries;
    frm.refresh_field("meal_plan_entry");
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

    // Ensure the total does not exceed the given total_individuals
    if (total_entered > total_individuals) {
        frappe.msgprint(__('The sum of small, normal, and large appetite individuals cannot exceed Total Individuals (' + total_individuals + '). Please adjust the values.'));
        return;
    }

    // Calculate total servings
    let total_servings = (small * 0.75) + (normal * 1) + (large * 1.25);
    frm.set_value('total_servings', total_servings);
}


function fetch_meal_ingredients(frm) {
    console.log("Fetching meal ingredients..."); 

    let total_servings = frm.doc.total_servings || 1;
    let meal_ids = frm.doc.meal_plan_entry.map(entry => entry.meal_id); 

    if (meal_ids.length === 0) {
        frappe.msgprint(__('No meals selected in the meal plan.'));
        return;
    }

    console.log("Meal IDs to fetch:", meal_ids); 

    frappe.call({
        method: "food_processing.food_processing.doctype.meal_plan.meal_plan.fetch_ingredients",
        args: {
            meal_ids: meal_ids,
            total_servings: total_servings
        },
        callback: function(r) {
            console.log("Fetched ingredients:", r.message); 

            if (!r.message || r.message.length === 0) {
                frappe.msgprint(__('No ingredients found for the selected meals.'));
                return;
            }

            frappe.call({
                method: "frappe.client.insert",
                args: {
                    doc: {
                        doctype: "Shopping List",
                        shopping_details: r.message.map(ingredient => ({
                            item_code: ingredient.ingredient,
                            item_name: ingredient.ingredient_name,
                            qty: ingredient.qty,
                            cost: ingredient.cost
                        }))
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

                        frappe.set_route("Form", "Shopping List", res.message.name);
                    }
                }
            });
        }
    });
}
