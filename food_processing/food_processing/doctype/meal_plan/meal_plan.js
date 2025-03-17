frappe.ui.form.on('Meal Plan', {
    refresh: function(frm) {
        setup_meal_drag_and_drop(frm);
        render_meal_plan_table(frm);
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
        render_meal_plan_table(frm); // Re-render when start_date changes
    },
    end_date: function(frm) {
        render_meal_plan_table(frm); // Re-render when end_date changes
    }
});
function render_meal_plan_table(frm) {
    let start_date = frm.doc.start_date;
    let end_date = frm.doc.end_date;

    if (!start_date || !end_date) {
        return; // Don't render table if dates are missing
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
        let display_date = date.format('ddd MM/DD/YY'); // Example: Mon 03/17/25

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

    // Reinitialize drag-and-drop after table update
    setup_meal_drag_and_drop(frm);
}
function setup_meal_drag_and_drop(frm) {
    if (!frm.fields_dict.meal_list) return;

    let meal_container = $(frm.fields_dict.meal_list.wrapper);
    meal_container.empty();

    // Fetch meals from the database
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Meals",
            fields: ["name", "meal_name"]
        },
        callback: function(response) {
            if (response.message) {
                response.message.forEach(meal => {
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

    // Attach drop event to each meal type cell in the table
    let meal_types = ["Breakfast", "Lunch", "Dinner", "Snack & Beverage","Dessert"];

    meal_types.forEach(type => {
        $(`td[data-meal-type="${type}"]`).on("dragover", function(event) {
            event.preventDefault();
        });

        $(`td[data-meal-type="${type}"]`).on("drop", function(event) {
            event.preventDefault();
            let meal_id = event.originalEvent.dataTransfer.getData("meal");
            let meal_name = event.originalEvent.dataTransfer.getData("meal_name");
            
            if (meal_id && meal_name) {
                let selected_date = $(event.target).closest("tr").attr("data-date");
                let meal_type = $(event.target).attr("data-meal-type");

                // Add to UI immediately
                $(event.target).append(`<div class="meal-item" style="padding:5px; background:#f2f2f2; margin:3px;">${meal_name}</div>`);

                // Add to meal_plan_entry (child table)
                add_meal_to_plan(frm, meal_id, meal_name, selected_date, meal_type);
            }
        });
    });
}

function add_meal_to_plan(frm, meal_id, meal_name, date, meal_type) {
    let row = frm.add_child("meal_plan_entry");
    row.meal_id = meal_id;
    row.meal_name = meal_name;
    row.meal_type = meal_type;
    row.date = date;
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


function fetch_meal_ingredients(frm, meal_id) {
    if (!meal_id) {
        return;
    }

    let total_servings = frm.doc.total_servings || 1; // Ensure we have a valid total_servings value

    frappe.call({
        method: "food_processing.food_processing.doctype.meal_plan.meal_plan.fetch_ingredients",
        args: {
            meal_id: meal_id,
            total_servings: total_servings
        },
        callback: function(r) {
            if (r.message) {
                let ingredients = r.message;

                // Create a new Shopping List document
                frappe.call({
                    method: "frappe.client.insert",
                    args: {
                        doc: {
                            doctype: "Shopping List",
                            shopping_details: ingredients.map(ingredient => ({
                                item_code: ingredient.ingredient,  // Assuming there is an ID field
                                item_name: ingredient.ingredient_name,
                                qty: ingredient.qty,
                                cost: ingredient.cost
                            }))
                        }
                    },
                    callback: function(res) {
                        if (res.message) {
                            frappe.msgprint({
                                title: __("Success"),
                                message: `Ingredients added to Shopping List <b>${res.message.name}</b>.`,
                                indicator: "green"
                            });

                            // Open the Shopping List for user confirmation
                            frappe.set_route("Form", "Shopping List", res.message.name);
                        }
                    }
                });
            }
        }
    });
}
