frappe.pages['meal-assignment'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Meal Assignment',
		single_column: true
	});

	let currentDate = frappe.datetime.nowdate();
    let container = $('<div class="meal-assignment-container p-4 overflow-auto"></div>').appendTo(page.body);
    let currentMonday = getMonday(new Date());
    const selectedDate = new Date();

    page.set_primary_action('Submit Meal Plan', function() {
        submitMealPlanForWeek(currentMonday); 
    }, 'check');
    page.add_action_item('Go to Shopping Lists', function() {
    frappe.set_route('List', 'Shopping List');
});




    function getMonday(date) {
        let d = new Date(date);
        let day = d.getDay(),
            diff = d.getDate() - day + (day === 0 ? -6 : 1);
        return new Date(d.setDate(diff));
    }

    function submitMealPlanForWeek(mondayDate) {
    const mondayStr = frappe.datetime.obj_to_str(mondayDate);  // Use system format (YYYY-MM-DD)
    const totalIndividuals = parseInt($('#total-people').text()) || 0;

    console.log("Saving meal plan summary for date:", mondayStr);

    frappe.call({
        method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.save_meal_plan_summary',
        args: {
            monday: mondayStr,
            total_individuals: totalIndividuals
        },
        callback: function(res) {
            if (res.message === "OK") {
                console.log("Summary saved. Proceeding to submit Meal Plan...");

                frappe.call({
                    method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.submit_meal_plan',
                    args: {
                        monday: mondayStr
                    },
                    callback: function(r) {
                        console.log("Response from submit_meal_plan:", r);

                        if (!r || !r.message) {
                            frappe.msgprint(__('No response from server'));
                            return;
                        }

                        if (r.message === 'submitted') {
                            frappe.msgprint(__('Meal Plan submitted successfully'));

                            // Call create_shopping_list
                            console.log("Calling create_shopping_list for:", mondayStr);
                            frappe.call({
                                method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.create_shopping_list',
                                args: {
                                    monday: mondayStr
                                },
                                callback: function(resp) {
                                    console.log("Response from create_shopping_list:", resp);
                                    if (resp.message === 'created') {
                                        frappe.msgprint(__('Shopping List created successfully'));
                                    } else {
                                        frappe.msgprint(__('Error creating Shopping List'));
                                    }
                                }
                            });

                        } else if (r.message === 'not_found') {
                            frappe.msgprint(__('No Meal Plan found for this week'));
                        } else if (r.message === 'already_submitted') {
                            frappe.msgprint(__('Meal Plan already submitted'));
                        } else {
                            frappe.msgprint(__('Error submitting Meal Plan'));
                        }
                    },
                    error: function(err) {
                        console.error("Error during frappe.call to submit_meal_plan:", err);
                        frappe.msgprint(__('Server error submitting Meal Plan'));
                    }
                });

            } else {
                frappe.msgprint(__('Could not update total individuals before submitting the Meal Plan'));
            }
        },
        error: function(err) {
            console.error("Error updating total individuals:", err);
            frappe.msgprint(__('Failed to update total individuals before submit'));
        }
    });
}

    
    // Fixed function to get visible dates for the current week
    function getVisibleDates(monday) {
        const dates = [];
        for (let i = 0; i < 7; i++) {
            const date = new Date(monday);
            date.setDate(monday.getDate() + i);
            dates.push(frappe.datetime.obj_to_str(date));
        }
        return dates;
    }
    
    // Fixed function to fetch and render meal assignments
    function fetchAndRenderMealAssignments(monday) {
        const visibleDates = getVisibleDates(monday);
    
        frappe.call({
            method: "food_processing.food_processing.page.meal_assignment.meal_assignment.get_meal_entries_for_dates",
            args: {
                dates_json: JSON.stringify(visibleDates)
            },
            callback: function (r) {
                const entries = r.message || [];
                console.log("Fetched meal entries:", entries); // Debug log
    
                entries.forEach(entry => {
                    // Find the cell based on date and meal_type
                    const selector = `[data-date="${entry.date}"][data-meal-type="${entry.meal_type}"][data-customer="${entry.customer}"]`;

                    const cell = $(selector);
    
                    if (cell.length > 0) {
                        cell.html(`
                            <div class="flex items-center justify-between px-1">
                                <span class="truncate" title="${entry.meal_name}">${entry.meal_name}</span>
                                <button class="text-red-500 text-xs remove-meal">&times;</button>
                            </div>
                        `);
                        
                        // Add click handler for remove button
                        cell.find('.remove-meal').on('click', function(e) {
                            e.stopPropagation();
                            removeMealAssignment(entry.date, entry.meal_type, entry.customer);
                        });
                    }
                });
            },
            error: function(err) {
                console.error("Error fetching meal assignments:", err);
            }
        });
    }
    
    // Function to remove meal assignment
    function removeMealAssignment(date, mealType, customer) {
        frappe.call({
            method: "food_processing.food_processing.page.meal_assignment.meal_assignment.remove_meal_assignment",
            args: {
                date: date,
                meal_type: mealType,
                customer: customer
            },
            callback: function(r) {
                if (r.message === "OK") {
                    const selector = `[data-date="${date}"][data-meal-type="${mealType}"][data-customer="${customer}"]`;
                    $(selector).empty();
                    frappe.msgprint("Meal assignment removed");
                    fetchAndRenderMealAssignments(currentMonday);
                } else if (r.message === "cancelled") {
                    frappe.msgprint("Cannot modify cancelled meal plan");
                } else {
                    frappe.msgprint("Error removing meal assignment");
                }
            }
        });
    }
        
    function saveMealAssignment(assignments) {
    
    const total_individuals = parseInt($('#total-people').text()) || 0;

    const assignmentData = {
        date: assignments.date,
        meal_type: assignments.meal_type,
        meal_id: assignments.meal_id,
        meal_name: assignments.meal_name,
        customer: assignments.customer,
        total_individuals: total_individuals
    };

    console.log("Sending assignment data:", assignmentData); // Debug log
    //frappe.msgprint(`Attempting to save: ${assignmentData.meal_name} for ${assignmentData.customer}`); // Debug message
    
    frappe.call({
        method: "food_processing.food_processing.page.meal_assignment.meal_assignment.save_meal_assignment",
        args: {
            assignments_json: JSON.stringify(assignmentData)
        },
        callback: function(r) {
            console.log("Save response:", r); // Debug log
            if (r.message === "OK") {
                //frappe.msgprint("Meal assignment saved successfully!");
                // Refresh the display to show the saved assignment
                fetchAndRenderMealAssignments(currentMonday);
            } else {
                console.error("Server returned:", r.message);
                frappe.msgprint("Save failed - Server response: " + (r.message || "Unknown error"));
            }
        },
        error: function(err) {
            console.error("Error saving meal assignment:", err);
            frappe.msgprint("Network error while saving: " + (err.message || "Connection failed"));
        }
    });
}
    
    function formatDate(date) {
        return frappe.datetime.obj_to_str(date);
    }

    function shortDateDisplay(date) {
        let d = new Date(date);
        let days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        return days[d.getDay()] + ' ' + frappe.datetime.str_to_user(formatDate(d));
    }

    const meals = ['Breakfast', 'Lunch', 'Dinner'];

    const COLORS = [
        '#FFB6C1', '#ADD8E6', '#90EE90', '#FFD700', '#FFA07A',
        '#20B2AA', '#9370DB', '#FF69B4', '#87CEEB', '#32CD32'
    ];

    function getColorForCustomer(customer, assignedColors) {
        if (assignedColors[customer]) return assignedColors[customer];
        let color = COLORS[Object.keys(assignedColors).length % COLORS.length];
        assignedColors[customer] = color;
        return color;
    }

    function updateTotalPeople(taskData, monday) {
        let total = 0;
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
    
        taskData.forEach(entry => {
            const start = new Date(entry.exp_start_date);
            const end = new Date(entry.exp_end_date);
    
            if (end >= monday && start <= sunday) {
                total += parseInt(entry.custom_no_of_people || 0);
            }
        });
    
        console.log("Final total:", total);
        $('#total-people').text(total);
    }

    function renderWeekView(baseDate) {
        container.empty();
        
        // Update currentMonday for the new week
        currentMonday = getMonday(baseDate);
        let monday = currentMonday;
        let sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);

        let mondayStr = formatDate(monday);
        let sundayStr = formatDate(sunday);

        let nav = $(`
            <div class="mb-4 flex justify-between items-center">
                <button class="btn btn-secondary" id="prev-week">Previous</button>
                <h4>Week of ${frappe.datetime.str_to_user(mondayStr)}</h4>
                <button class="btn btn-secondary" id="next-week">Next</button>
            </div>
        `);
        container.append(nav);
        
        // Week summary section
        const summary = $(`
            <div id="week-summary" class="p-4 bg-white border rounded shadow mb-4">
                <div class="flex flex-col sm:flex-row flex-wrap gap-4 items-start sm:items-center justify-between">
                    <div class="text-sm font-medium">
                        Total People This Week: <span id="total-people" class="font-semibold text-blue-600">0</span>
                    </div>

                    <div class="flex flex-wrap gap-4 items-center text-sm">
                        <label class="flex items-center">Small:
                            <input type="number" id="servings-small" class="border rounded px-2 py-1 w-16 ml-1" min="0" value="0" />
                        </label>
                        <label class="flex items-center">Normal:
                            <input type="number" id="servings-normal" class="border rounded px-2 py-1 w-16 ml-1" min="0" value="0" />
                        </label>
                        <label class="flex items-center">Large:
                            <input type="number" id="servings-large" class="border rounded px-2 py-1 w-16 ml-1" min="0" value="0" />
                        </label>
                    </div>
                </div>
            </div>
        `);

        container.append(summary);

        $('#prev-week').click(() => {
            let prevWeek = new Date(monday);
            prevWeek.setDate(monday.getDate() - 7);
            renderWeekView(prevWeek);
        });

        $('#next-week').click(() => {
            let nextWeek = new Date(monday);
            nextWeek.setDate(monday.getDate() + 7);
            renderWeekView(nextWeek);
        });

        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Task',
                filters: [
                    ['subject', '=', 'Meal Plan Allocation'],
                    ['exp_start_date', '<=', sundayStr],
                    ['exp_end_date', '>=', mondayStr]
                ],
                fields: [
                    'custom_customer',
                    'custom_customer_name',
                    'custom_no_of_people',
                    'exp_start_date',
                    'exp_end_date'
                ],
                limit: 1000
            },
            callback: function(r) {
                const tasks = r.message || [];
                const customerMap = {};
                const assignedColors = {};
                updateTotalPeople(tasks, monday);

                tasks.forEach(task => {
                    const customer = task.custom_customer;
                    const no_of_people = task.custom_no_of_people;
                    const start = frappe.datetime.str_to_obj(task.exp_start_date);
                    const end = frappe.datetime.str_to_obj(task.exp_end_date);
                    
                    const taskKey = `${customer}_${task.exp_start_date}_${task.exp_end_date}`;

                    getColorForCustomer(customer, assignedColors);

                    if (!customerMap[taskKey]) {
                        customerMap[taskKey] = {
                            customer: customer,
                            customer_name: task.custom_customer_name || customer,
                            no_of_people: no_of_people,
                            days: {},
                            exp_start_date: task.exp_start_date,
                            exp_end_date: task.exp_end_date
                        };
                    }

                    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
                        let key = formatDate(new Date(d));
                        if (new Date(key) >= monday && new Date(key) <= sunday) {
                            customerMap[taskKey].days[key] = true;
                        }
                    }
                });
                
                const table = $('<table class="table table-bordered table-sm w-max text-center"></table>');

                const thead = $('<thead></thead>');
                const headerRow1 = $('<tr></tr>');
                headerRow1.append('<th rowspan="2" style="min-width:150px;">Customer</th>');
                headerRow1.append('<th rowspan="2"># People</th>');

                for (let i = 0; i < 7; i++) {
                    const d = new Date(monday);
                    d.setDate(monday.getDate() + i);
                    headerRow1.append(`<th colspan="3">${shortDateDisplay(d)}</th>`);
                }
                thead.append(headerRow1);

                const headerRow2 = $('<tr></tr>');
                for (let i = 0; i < 7; i++) {
                    meals.forEach(meal => {
                        headerRow2.append(`<th>${meal}</th>`);
                    });
                }
                thead.append(headerRow2);
                table.append(thead);

                const tbody = $('<tbody></tbody>');

                Object.keys(customerMap).forEach(taskKey => {
                    const entry = customerMap[taskKey];
                    const customer = entry.customer;
                    const color = assignedColors[customer];
                    const colorBox = `<span style="
                        display:inline-block;
                        width:12px; height:12px;
                        background-color:${color};
                        border-radius:3px;
                        margin-right:6px;
                        vertical-align:middle;
                    "></span>`;

                    const row = $(`<tr><td style="text-align:left;" title="${customer}">${colorBox}${entry.customer_name}</td><td>${entry.no_of_people}</td></tr>`);

                    for (let i = 0; i < 7; i++) {
                        const d = new Date(monday);
                        d.setDate(monday.getDate() + i);
                        const key = formatDate(d);
                        const highlight = entry.days[key] === true;

                        const start = new Date(entry.exp_start_date);
                        const end = new Date(entry.exp_end_date);

                        const isActive = d.getTime() >= start.getTime() && d.getTime() <= end.getTime();

                        for (let j = 0; j < 3; j++) {
                            const mealType = meals[j];
                            const cell = $(`<td class="border text-center min-w-[100px] h-[50px] text-xs align-middle calendar-cell"></td>`);
                            cell.attr('data-date', key);
                            cell.attr('data-meal-type', mealType);
                            cell.attr('data-customer', customer);

                            if (highlight || isActive) {
                                cell.css('background-color', color);
                                cell.addClass('droppable-cell');

                                // Drag events
                                cell.on('dragover', function (e) {
                                    e.preventDefault();
                                    $(this).addClass('ring ring-blue-400');
                                });

                                cell.on('dragleave', function () {
                                    $(this).removeClass('ring ring-blue-400');
                                });

                                cell.on('drop', function (e) {
                                    e.preventDefault();
                                    $(this).removeClass('ring ring-blue-400');
                                    const mealName = e.originalEvent.dataTransfer.getData('text/plain');
                                    const meal = allMeals.find(m => m.meal_name === mealName);
                                    const meal_id = meal?.name || "";
                                    const cellDate = key;
                                    const mealType = meals[j];
                                    const currentCustomer = customer;

                                    $(this).html(`
                                        <div class="flex items-center justify-between px-1">
                                            <span class="truncate" title="${mealName}">${mealName}</span>
                                            <button class="text-red-500 text-xs remove-meal">&times;</button>
                                        </div>
                                    `);

                                    // Add remove click handler
                                    $(this).find('.remove-meal').on('click', function(e) {
                                        e.stopPropagation();
                                        removeMealAssignment(cellDate, mealType, currentCustomer);
                                    });

                                    saveMealAssignment({
                                        date: cellDate,
                                        meal_type: mealType,
                                        meal_id: meal_id,
                                        meal_name: mealName,
                                        customer: currentCustomer,
                                        small_appetite: parseInt($("#servings-small").val()) || 0,
                                        normal_appetite: parseInt($("#servings-normal").val()) || 0,
                                        large_appetite: parseInt($("#servings-large").val()) || 0,
                                        total_individuals: parseInt($('#total-people').text()) || 0
                                    });
                                });

                                cell.on('click', function () {
                                    if (!selectedMeal) return;

                                    const meal = allMeals.find(m => m.meal_name === selectedMeal);
                                    const meal_id = meal?.name || "";
                                    const cellDate = key;
                                    const mealType = meals[j];
                                    const currentCustomer = customer;

                                    $(this).html(`
                                        <div class="flex items-center justify-between px-1">
                                            <span class="truncate" title="${selectedMeal}">${selectedMeal}</span>
                                            <button class="text-red-500 text-xs remove-meal">&times;</button>
                                        </div>
                                    `);

                                    // Add remove click handler
                                    $(this).find('.remove-meal').on('click', function(e) {
                                        e.stopPropagation();
                                        removeMealAssignment(cellDate, mealType, currentCustomer);
                                    });

                                    saveMealAssignment({
                                        date: cellDate,
                                        meal_type: mealType,
                                        meal_id: meal_id,
                                        meal_name: selectedMeal,
                                        customer: currentCustomer,
                                        small_appetite: parseInt($("#servings-small").val()) || 0,
                                        normal_appetite: parseInt($("#servings-normal").val()) || 0,
                                        large_appetite: parseInt($("#servings-large").val()) || 0,
                                        total_individuals: parseInt($('#total-people').text()) || 0
                                    });
                                });
                            }

                            row.append(cell);
                        }
                    }

                    tbody.append(row);
                });

                table.append(tbody);

                const scrollContainer = $('<div style="overflow-x:auto; width:100%;"></div>');
                scrollContainer.append(table);

                container.append(scrollContainer);

                // Fetch and render existing meal assignments after the table is created
                fetchAndRenderMealAssignments(monday);

                let mealsPerPage = 5;
                let currentMealPage = 1;
                let allMeals = [];
                let filteredMeals = [];
                let selectedCategory = null;

                const mealContainer = $('<div class="mt-6"></div>');
                container.append(mealContainer);

                let selectedMeal = null;

                function renderMealCards(meals) {
                    const grid = $('<div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2 mt-4"></div>');
                    meals.forEach(meal => {
                        let categories = (meal.meal_plan_category || []).map(cat => cat.category).join(', ') || 'Uncategorized';
                        const card = $(`
                            <div class="rounded border bg-white text-xs p-2 h-16 overflow-hidden shadow hover:shadow-md transition cursor-pointer"
                                draggable="true"
                                data-meal="${meal.meal_name}">
                                <div class="font-semibold truncate" title="${meal.meal_name}">${meal.meal_name}</div>
                                <div class="text-gray-500 truncate" title="${categories}">${categories}</div>
                            </div>
                        `);

                        card.on('dragstart', function (e) {
                            e.originalEvent.dataTransfer.setData('text/plain', $(this).data('meal'));
                        });

                        card.on('click', function () {
                            if (selectedMeal === $(this).data('meal')) {
                                selectedMeal = null;
                                card.removeClass('border-blue-500 ring ring-blue-300');
                            } else {
                                selectedMeal = $(this).data('meal');
                                $('.grid div').removeClass('border-blue-500 ring ring-blue-300');
                                card.addClass('border-blue-500 ring ring-blue-300');
                            }
                        });

                        grid.append(card);
                    });
                    return grid;
                }

                function renderMealsPage(page) {
                    mealContainer.empty();

                    const start = (page - 1) * mealsPerPage;
                    const end = start + mealsPerPage;
                    const pageMeals = filteredMeals.slice(start, end);

                    const filterDiv = $('<div class="flex items-center gap-4 mb-4"></div>');
                    const categorySelect = $('<select class="form-control w-60" id="meal-category-filter"><option value="">All Categories</option></select>');
                    filterDiv.append('<label><strong>Filter by Category:</strong></label>');
                    filterDiv.append(categorySelect);
                    mealContainer.append(filterDiv);

                    categorySelect.change(function () {
                        selectedCategory = $(this).val();
                        applyMealFilter();
                        currentMealPage = 1;
                        renderMealsPage(currentMealPage);
                    });

                    if (pageMeals.length === 0) {
                        mealContainer.append('<p>No meals to display.</p>');
                    } else {
                        mealContainer.append(renderMealCards(pageMeals));
                    }

                    const controls = $(`
                        <div class="flex justify-between mt-4">
                            <button class="btn btn-sm btn-secondary" id="prev-meals" ${page === 1 ? 'disabled' : ''}>Previous</button>
                            <button class="btn btn-sm btn-secondary" id="next-meals" ${(end >= filteredMeals.length) ? 'disabled' : ''}>Next</button>
                        </div>
                    `);
                    mealContainer.append(controls);

                    $('#prev-meals').click(() => {
                        if (currentMealPage > 1) {
                            currentMealPage--;
                            renderMealsPage(currentMealPage);
                        }
                    });

                    $('#next-meals').click(() => {
                        if (end < filteredMeals.length) {
                            currentMealPage++;
                            renderMealsPage(currentMealPage);
                        }
                    });

                    if ($('#meal-category-filter option').length <= 1) {
                        const categories = new Set();
                        allMeals.forEach(m => {
                            (m.meal_plan_category || []).forEach(cat => {
                                if (cat.category) categories.add(cat.category);
                            });
                        });

                        [...categories].sort().forEach(cat => {
                            categorySelect.append(`<option value="${cat}">${cat}</option>`);
                        });

                        if (selectedCategory) {
                            categorySelect.val(selectedCategory);
                        }
                    }
                }

                function applyMealFilter() {
                    if (!selectedCategory) {
                        filteredMeals = [...allMeals];
                    } else {
                        filteredMeals = allMeals.filter(meal => {
                            return (meal.meal_plan_category || []).some(cat => cat.category === selectedCategory);
                        });
                    }
                }

                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Meals',
                        fields: ['name', 'meal_name'],
                        limit: 1000
                    },
                    callback: function(r) {
                        const meals = r.message || [];
                        let mealNames = meals.map(m => m.name);

                        let fetched = 0;
                        meals.forEach((meal, idx) => {
                            frappe.call({
                                method: 'frappe.client.get',
                                args: {
                                    doctype: 'Meals',
                                    name: meal.name
                                },
                                callback: function(docRes) {
                                    meals[idx].meal_plan_category = docRes.message.meal_plan_category || [];
                                    fetched++;
                                    if (fetched === meals.length) {
                                        allMeals = meals;
                                        applyMealFilter();
                                        renderMealsPage(currentMealPage);
                                    }
                                }
                            });
                        });
                    }
                });
            }
        });
    }

    // Initialize the page
    renderWeekView(currentDate);
};