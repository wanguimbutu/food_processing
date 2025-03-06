frappe.ui.form.on('Meal Plan', {
    refresh: function(frm) {
        if (!frm.fields_dict.recipe_list) {
            return;
        }

        let recipe_container = $(frm.fields_dict.recipe_list.wrapper);
        recipe_container.empty(); // Clear previous content

        // Create a container for draggable recipes
        let recipeList = $("<div>").css({
            "border": "1px solid #ddd",
            "padding": "10px",
            "margin-bottom": "10px",
            "background": "#f8f9fa"
        }).text("Drag Recipes Below:");

        // Fetch recipes dynamically
        frappe.call({
            method: "frappe.client.get_list",
            args: {
                doctype: "Recipe",
                fields: ["name", "recipe_name"]
            },
            callback: function(response) {
                if (response.message) {
                    response.message.forEach(recipe => {
                        let item = $("<div>")
                            .text(recipe.recipe_name)
                            .attr("data-recipe", recipe.name)
                            .addClass("draggable-recipe")
                            .css({
                                "border": "1px solid #ccc",
                                "padding": "5px",
                                "margin": "5px 0",
                                "background-color": "#ffffff",
                                "cursor": "grab"
                            })
                            .attr("draggable", true);

                        // Set drag start event
                        item.on("dragstart", function(event) {
                            event.originalEvent.dataTransfer.setData("recipe", $(this).attr("data-recipe"));
                        });

                        recipeList.append(item);
                    });

                    recipe_container.append(recipeList);
                }
            }
        });

        // Enable Drag & Drop on the Meal Plan Table
        let table_wrapper = $(frm.fields_dict.meal_plan_entry.grid.wrapper);

        table_wrapper.on("dragover", function(event) {
            event.preventDefault();
        });

        table_wrapper.on("drop", function(event) {
            event.preventDefault();
            let recipe_id = event.originalEvent.dataTransfer.getData("recipe");

            if (recipe_id) {
                frappe.call({
                    method: "frappe.client.get",
                    args: {
                        doctype: "Recipe",
                        name: recipe_id
                    },
                    callback: function(response) {
                        if (response.message) {
                            let recipe = response.message;
                            let row = frm.add_child("meal_plan_entry");
                            row.recipe = recipe.name;
                            row.recipe_name = recipe.recipe_name;
                            frm.refresh_field("meal_plan_entry");
                        }
                    }
                });
            }
        });
    }
});
