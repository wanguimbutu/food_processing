frappe.ui.form.on('Meal Plan', {
    refresh: function(frm) {
        setup_meal_drag_and_drop(frm);
    },
    small_appetite: function(frm) {
        validate_and_calculate(frm);
    },
    normal_appetite: function(frm) {
        validate_and_calculate(frm);
    },
    large_appetite: function(frm) {
        validate_and_calculate(frm);
    }
});

function setup_meal_drag_and_drop(frm) {
    if (!frm.fields_dict.meal_list) return;

    let meal_container = $(frm.fields_dict.meal_list.wrapper);
    meal_container.empty();

    let mealList = $("<div>").css({
        "border": "1px solid #ddd",
        "padding": "10px",
        "margin-bottom": "10px",
        "background": "#f8f9fa"
    }).text("Drag Meals Below:");

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
                            "width": "50%"
                        })
                        .attr("draggable", true);

                    item.on("dragstart", function(event) {
                        event.originalEvent.dataTransfer.setData("meal", $(this).attr("data-meal"));
                    });

                    mealList.append(item);
                });

                meal_container.append(mealList);
            }
        }
    });

    let dropZone = $("<div>")
        .addClass("meal-drop-zone")
        .css({
            "border": "2px dashed #007bff",
            "padding": "15px",
            "min-height": "100px",
            "background": "#e9f5ff",
            "text-align": "center",
            "margin-top": "20px"
        })
        .text("Drop Meals Here");

    dropZone.on("dragover", function(event) {
        event.preventDefault();
    });

    dropZone.on("drop", function(event) {
        event.preventDefault();
        let meal_id = event.originalEvent.dataTransfer.getData("meal");

        if (meal_id) {
            frappe.call({
                method: "frappe.client.get",
                args: {
                    doctype: "Meals",
                    name: meal_id
                },
                callback: function(response) {
                    if (response.message) {
                        let meal = response.message;
                        prompt_for_meal_details(frm, meal);
                    }
                }
            });
        }
    });

    meal_container.append(dropZone);
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
                                item_code: ingredient.ingredient_id,  // Assuming there is an ID field
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
