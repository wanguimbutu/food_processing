frappe.ui.form.on('Meal Plan', {
    refresh: function(frm) {
        setup_meal_drag_and_drop(frm);
    },

    start_date: function(frm) {
        update_meal_dates(frm);
    },

    end_date: function(frm) {
        update_meal_dates(frm);
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
    },
    "Add Meal to Meal Plan",
    "Add");
}


function update_meal_dates(frm) {
    if (!frm.doc.start_date || !frm.doc.end_date) return;

    let startDate = new Date(frm.doc.start_date);
    let endDate = new Date(frm.doc.end_date);

    frm.clear_table("meal_plan_entry");

    let currentDate = startDate;
    while (currentDate <= endDate) {
        let formattedDate = frappe.datetime.str_to_obj(frappe.datetime.obj_to_str(currentDate));

        let row = frm.add_child("meal_plan_entry");
        row.date = frappe.datetime.obj_to_str(currentDate, 'YYYY-MM-DD'); 

        currentDate.setDate(currentDate.getDate() + 1);
    }

    frm.refresh_field("meal_plan_entry");
}
