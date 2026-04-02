frappe.pages['meal-assignment'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Meal Assignment',
		single_column: true
	});
    frappe.require([
        "https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"
    ], function() {
        console.log("html2pdf loaded");
    }
    )

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
        frappe.confirm(
            'Do you want to generate a <strong>combined shopping list</strong> for all customers this week?',
            function () {
                // YES - Combined
                submitWithCombinedOption(mondayDate, true);
            },
            function () {
                // NO - Separate per customer
                submitWithCombinedOption(mondayDate, false);
            }
        );
    }


    function submitWithCombinedOption(mondayDate, combine) {
        const mondayStr = frappe.datetime.obj_to_str(mondayDate);

        frappe.call({
            method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.submit_meal_plan_and_create_shopping_list',
            args: {
                monday: mondayStr,
                combine: combine
            },
            callback: function (r) {
                if (r.message && r.message.status === 'success') {
                    frappe.msgprint(__('Meal Plan(s) submitted and Shopping List(s) created successfully!'));
                } else {
                    const errorMsg = r.message ? r.message.message : 'Unknown error';
                    frappe.msgprint(__(`Error: ${errorMsg}`));
                }
            },
            error: function (err) {
                frappe.msgprint(__('Server error during submission'));
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
        
        console.log("=== DEBUGGING MEAL ASSIGNMENTS ===");
        console.log("Fetching assignments for dates:", visibleDates);

        frappe.call({
            method: "food_processing.food_processing.page.meal_assignment.meal_assignment.get_meal_entries_for_dates",
            args: {
                dates_json: JSON.stringify(visibleDates)
            },
            callback: function (r) {
                const entries = r.message || [];
                console.log("✓ Fetched meal entries:", entries);
                console.log("✓ Number of entries:", entries.length);

                if (entries.length === 0) {
                    console.log(" No meal entries to display");
                    return;
                }

                // Debug: Check what cells exist before trying to match
                console.log("=== CHECKING EXISTING CELLS ===");
                const allCells = $('[data-date][data-meal-type][data-customer][data-project-key]');
                console.log("✓ Total cells with all data attributes:", allCells.length);
                
                // Log a few sample cells to see their attributes
                allCells.slice(0, 3).each(function(index) {
                    console.log(`Sample cell ${index + 1}:`, {
                        date: $(this).attr('data-date'),
                        mealType: $(this).attr('data-meal-type'),
                        customer: $(this).attr('data-customer'),
                        projectKey: $(this).attr('data-project-key')
                    });
                });

                entries.forEach((entry, index) => {
                    console.log(`\n=== PROCESSING ENTRY ${index + 1} ===`);
                    console.log("Entry data:", entry);
                    
                    // Build the selector step by step for better debugging
                    const selector = `[data-date="${entry.date}"][data-meal-type="${entry.meal_type}"][data-customer="${entry.customer}"][data-project-key="${entry.project_key}"]`;
                    console.log("Looking for selector:", selector);

                    const cell = $(selector);
                    console.log("Found cells with this selector:", cell.length);

                    if (cell.length === 0) {
                        console.log("NO MATCHING CELL FOUND!");
                        
                        // Debug: Try to find cells with partial matches
                        console.log("--- DEBUGGING PARTIAL MATCHES ---");
                        
                        // Check date match
                        const dateMatches = $(`[data-date="${entry.date}"]`);
                        console.log(`Cells with date "${entry.date}":`, dateMatches.length);
                        
                        // Check meal type match
                        const mealTypeMatches = $(`[data-meal-type="${entry.meal_type}"]`);
                        console.log(`Cells with meal type "${entry.meal_type}":`, mealTypeMatches.length);
                        
                        // Check customer match
                        const customerMatches = $(`[data-customer="${entry.customer}"]`);
                        console.log(`Cells with customer "${entry.customer}":`, customerMatches.length);
                        
                        // Check project key match
                        const projectMatches = $(`[data-project-key="${entry.project_key}"]`);
                        console.log(`Cells with project key "${entry.project_key}":`, projectMatches.length);
                        
                        // Try date + meal type combination
                        const dateAndMeal = $(`[data-date="${entry.date}"][data-meal-type="${entry.meal_type}"]`);
                        console.log(`Cells with date + meal type:`, dateAndMeal.length);
                        
                        if (dateAndMeal.length > 0) {
                            console.log("Available date+meal combinations:");
                            dateAndMeal.each(function() {
                                console.log({
                                    date: $(this).attr('data-date'),
                                    mealType: $(this).attr('data-meal-type'),
                                    customer: $(this).attr('data-customer'),
                                    projectKey: $(this).attr('data-project-key')
                                });
                            });
                        }
                        
                    } else {
                        console.log("✓ FOUND MATCHING CELL! Updating content...");
                        
                        cell.html(`
                            <div class="flex items-center justify-between px-1">
                                <span class="truncate" title="${entry.meal_name}">${entry.meal_name}</span>
                                <button class="text-red-500 text-xs remove-meal">&times;</button>
                            </div>
                        `);
                        
                        // Add click handler for remove button
                        cell.find('.remove-meal').on('click', function(e) {
                            e.stopPropagation();
                            removeMealAssignment(entry.date, entry.meal_type, entry.customer, entry.project_key);
                        });
                        
                        console.log("✓ Cell updated successfully");
                    }
                });
                
                console.log("=== END DEBUGGING ===\n");
            },
            error: function(err) {
                console.error("Error fetching meal assignments:", err);
            }
        });
    }

    
    // Function to remove meal assignment
    function removeMealAssignment(date, mealType, customer,projectKey) {
        frappe.call({
            method: "food_processing.food_processing.page.meal_assignment.meal_assignment.remove_meal_assignment",
            args: {
                date: date,
                meal_type: mealType,
                customer: customer,
                project_key:projectKey
            },
            callback: function(r) {
                if (r.message === "OK") {
                    const selector = `[data-date="${date}"][data-meal-type="${mealType}"][data-customer="${customer}"][data-project-key="${projectKey}"]`;
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
        console.log("Sending assignment data:", assignments);

        frappe.call({
            method: "food_processing.food_processing.page.meal_assignment.meal_assignment.save_meal_assignment",
            args: {
                assignments_json: JSON.stringify(assignments)
            },
            callback: function(r) {
                console.log("Save response:", r);
                if (r.message === "OK") {
                    fetchAndRenderMealAssignments(currentMonday);
                } else {
                    frappe.msgprint("Save failed: " + (r.message || "Unknown error"));
                }
            },
            error: function(err) {
                console.error("Error saving meal assignment:", err);
                frappe.msgprint("Network error while saving: " + (err.message || "Connection failed"));
            }
        });
    }

    function formatDate(date) {
        // Always produce YYYY-MM-DD in local time to avoid UTC shift issues
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    }

    function parseLocalDate(dateStr) {
        // Parse "YYYY-MM-DD" as local midnight, not UTC midnight
        const [y, m, d] = dateStr.split('-').map(Number);
        return new Date(y, m - 1, d);
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
            const start = parseLocalDate(entry.exp_start_date);
            const end = parseLocalDate(entry.exp_end_date);
    
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

        const dietSummarySection = $('<div id="diet-summary-section" class="mb-6"></div>');
        const calendarSection = $('<div id="calendar-section"></div>');
        container.append(dietSummarySection);
        container.append(calendarSection);
        
        frappe.call({
        method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.get_meal_plan_tasks_with_diets',
        args: { monday: mondayStr },
        callback: function (r) {
            const tasks = r.message || [];

            console.log("Meal Plan Tasks with Diets:", tasks);

            if (tasks.length === 0) {
                console.log("No Meal Plan Allocation tasks found for this week");
                return;
            }

            const dietTable = $(`
                <table class="table table-bordered bg-white shadow mb-4 text-sm w-auto">
                    <thead class="bg-gray-100">
                        <tr>
                            <th>Customer</th>
                            <th>Customer Name</th>
                            <th>Diet Name</th>
                            <th>Total People</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
            `);
            const dietBody = dietTable.find('tbody');
            tasks.forEach(task => {
                (task.dietary_requirements || []).forEach(diet => {
                    const row = $(`
                        <tr>
                            <td>${task.custom_customer || ''}</td>
                            <td>${task.custom_customer_name || ''}</td>
                            <td>${diet.diet_name || ''}</td>
                            <td>${diet.total_people || 0}</td>
                        </tr>
                    `);
                    dietBody.append(row);
                });
            });

            if (dietBody.children().length > 0) {
                dietSummarySection.append('<h4 class="mt-4 mb-2 font-semibold">Dietary Requirements Summary</h4>');
                dietSummarySection.append(dietTable);
            } else {
                console.log("Tasks found but no dietary data present");
            }
        },
        error: function (err) {
            console.error("Error fetching meal plan tasks with diets:", err);
        }
    });
        let nav = $(`
            <div class="mb-4 flex justify-between items-center">
                <button class="btn btn-secondary" id="prev-week">Previous</button>
                <h4>Week of ${frappe.datetime.str_to_user(mondayStr)}</h4>
                <button class="btn btn-secondary" id="next-week">Next</button>
            </div>
             <div class="mb-4 flex justify-end">
                    <button class="btn btn-primary" id="download-pdf">Download PDF</button>
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
            method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.get_meal_plan_tasks_with_diets',
            args: { monday: mondayStr },
            callback: function(r) {
                const tasks = r.message || [];
                const customerMap = {};
                const assignedColors = {};
                updateTotalPeople(tasks, monday);

                tasks.forEach(task => {
                    const customer = task.custom_customer;
                    const no_of_people = task.custom_no_of_people;
                    const start = parseLocalDate(task.exp_start_date);
                    const end = parseLocalDate(task.exp_end_date);

                    const taskKey = `${customer}_${task.task_name}_${task.exp_start_date}_${task.exp_end_date}`;
                    getColorForCustomer(customer, assignedColors);

                    if (!customerMap[taskKey]) {
                        customerMap[taskKey] = {
                            customer: customer,
                            customer_name: task.custom_customer_name || customer,
                            no_of_people: no_of_people,
                            days: {},
                            exp_start_date: task.exp_start_date,
                            exp_end_date: task.exp_end_date,
                            task_name: task.task_name,
                            project: task.project,
                            reservation: task.custom_reservation || ''
                        };
                    }

                    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
                        let key = formatDate(d);
                        const inRange = key >= formatDate(monday) && key <= formatDate(sunday);
                        if (inRange) {
                            customerMap[taskKey].days[key] = true;
                        }
                    }
                    if (Object.keys(customerMap[taskKey].days).length === 0) {
                        console.warn(`[DAYS EMPTY] ${customer} | task ${task.task_name} | start=${task.exp_start_date} end=${task.exp_end_date} | week ${formatDate(monday)}-${formatDate(sunday)}`);
                    }
                });

                const reservationNames = [...new Set(
                    Object.values(customerMap).map(e => e.reservation).filter(Boolean)
                )];

                let allMeals = [];
                let filteredMeals = [];
                let selectedMeal = null;
                let currentMealPage = 1;
                let mealsPerPage = 5;
                let selectedCategory = null;
                const mealContainer = $('<div class="mt-6"></div>');

                function renderCalendar(mealSchedules) {
                    console.log("renderCalendar: reservations in map:", Object.values(customerMap).map(e => e.reservation));
                    console.log("renderCalendar: mealSchedules keys:", Object.keys(mealSchedules));
                    // Apply per-meal selections from the linked reservation
                    Object.keys(customerMap).forEach(k => {
                        const entry = customerMap[k];
                        const sched = entry.reservation ? (mealSchedules[entry.reservation] || {}) : {};
                        Object.keys(entry.days).forEach(dk => {
                            const daySchedule = sched[dk];
                            // Only replace with schedule object if at least one meal is selected
                            // otherwise keep true so isActive fallback still highlights the day
                            if (daySchedule && (daySchedule.Breakfast || daySchedule.Lunch || daySchedule.Dinner)) {
                                entry.days[dk] = daySchedule;
                            }
                        });
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
                        const dayData = entry.days[key];

                        const start = parseLocalDate(entry.exp_start_date);
                        const end = parseLocalDate(entry.exp_end_date);
                        const isActive = d.getTime() >= start.getTime() && d.getTime() <= end.getTime();

                        for (let j = 0; j < 3; j++) {
                            const mealType = meals[j];
                            const cell = $(`<td class="border text-center min-w-[100px] h-[50px] text-xs align-middle calendar-cell"></td>`);
                            cell.attr('data-date', key);
                            cell.attr('data-meal-type', mealType);
                            cell.attr('data-customer', customer);
                            cell.attr('data-project-key', taskKey);
                            cell.attr('data-task-name', entry.task_name || '');
                            cell.attr('data-project-name', entry.project_name || '');
                            const shouldHighlight = dayData && typeof dayData === 'object'
                                ? !!dayData[mealType]
                                : (dayData === true || isActive);
                            if (isActive || dayData) {
                                console.log(`[CELL] ${customer} | ${key} | meal=${mealType} | dayData=${JSON.stringify(dayData)} | isActive=${isActive} | shouldHighlight=${shouldHighlight}`);
                            }
                            if (shouldHighlight) {
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
                                    const taskName = $(this).data('task-name');
                                    const projectName = $(this).data('project-name');

                                    const taskKey = $(this).data('project-key');
                                    const entry = customerMap[taskKey] || {};

                                    $(this).html(`
                                        <div class="flex items-center justify-between px-1">
                                            <span class="truncate" title="${mealName}">${mealName}</span>
                                            <button class="text-red-500 text-xs remove-meal">&times;</button>
                                        </div>
                                    `);

                                    // Add remove click handler
                                    $(this).find('.remove-meal').on('click', function(e) {
                                        e.stopPropagation();
                                        removeMealAssignment(cellDate, mealType, currentCustomer, taskKey);
                                    });

                                    saveMealAssignment({
                                        date: cellDate,
                                        meal_type: mealType,
                                        meal_id: meal_id,
                                        meal_name: mealName,
                                        customer: currentCustomer,
                                        project_key: taskKey,
                                        project_name: projectName,
                                        task_name: taskName,
                                        small_appetite: parseInt($("#servings-small").val()) || 0,
                                        normal_appetite: parseInt($("#servings-normal").val()) || 0,
                                        large_appetite: parseInt($("#servings-large").val()) || 0,
                                        
                                    });
                                });

                                // Fix the click handler in the cell.on('click') function
                                cell.on('click', function () {
                                    if (!selectedMeal) return;

                                    const meal = allMeals.find(m => m.meal_name === selectedMeal);
                                    const meal_id = meal?.name || "";
                                    const cellDate = key;
                                    const mealType = meals[j];
                                    const currentCustomer = customer;
                                    const taskName = $(this).data('task-name');
                                    const projectName = $(this).data('project-name');

                                    const taskKey = $(this).data('project-key'); // ✅ This was already correct
                                    const entry = customerMap[taskKey] || {};
                                    
                                    $(this).html(`
                                        <div class="flex items-center justify-between px-1">
                                            <span class="truncate" title="${selectedMeal}">${selectedMeal}</span>
                                            <button class="text-red-500 text-xs remove-meal">&times;</button>
                                        </div>
                                    `);

                                    // Add remove click handler
                                    $(this).find('.remove-meal').on('click', function(e) {
                                        e.stopPropagation();
                                        removeMealAssignment(cellDate, mealType, currentCustomer, taskKey);
                                    });

                                    saveMealAssignment({
                                        date: cellDate,
                                        meal_type: mealType,
                                        meal_id: meal_id,
                                        meal_name: selectedMeal,
                                        customer: currentCustomer,
                                        project_key: taskKey, // ✅ ADD THIS LINE - was missing!
                                        project_name: projectName,
                                        task_name: taskName,
                                        small_appetite: parseInt($("#servings-small").val()) || 0,
                                        normal_appetite: parseInt($("#servings-normal").val()) || 0,
                                        large_appetite: parseInt($("#servings-large").val()) || 0,
                                    });
                                });
                            }

                            row.append(cell);
                        }
                    }

                    tbody.append(row);
                });

                table.append(tbody);

                const scrollContainer = $('<div id="meal-calendar" style="overflow-x:auto; width:100%; padding: 20px; background: white;"></div>');
                scrollContainer.append(table);

                container.append(scrollContainer);

                fetchAndRenderMealAssignments(monday);
                container.append(mealContainer);
                } // end renderCalendar

                if (reservationNames.length) {
                    frappe.call({
                        method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.get_meal_schedules',
                        args: { reservation_names: JSON.stringify(reservationNames) },
                        callback: function(sr) { renderCalendar(sr.message || {}); }
                    });
                } else {
                    renderCalendar({});
                }

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
                method: "food_processing.food_processing.page.meal_assignment.meal_assignment.get_all_meals_with_categories",
                callback: function(r) {
                    allMeals = r.message || [];

                    // Optional: sort meals by creation (oldest first or newest first)
                    allMeals.sort((a, b) => new Date(a.creation) - new Date(b.creation));

                    applyMealFilter();
                    renderMealsPage(currentMealPage);
                }
            });

            }
        });
    }

    function buildAndDownloadPDF(tasks, mealEntries, mealSchedules, dates) {
        const fullDayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

        // meal lookup: date -> customer -> mealType -> mealName
        const mealLookup = {};
        mealEntries.forEach(e => {
            const d = typeof e.date === 'string' ? e.date.split(' ')[0] : String(e.date);
            if (!mealLookup[d]) mealLookup[d] = {};
            if (!mealLookup[d][e.customer]) mealLookup[d][e.customer] = {};
            mealLookup[d][e.customer][e.meal_type] = e.meal_name;
        });

        // reservation schedule lookup: reservationName -> date -> {Breakfast, Lunch, Dinner}
        // mealSchedules already keyed by reservation name

        const weekLabel = frappe.datetime.str_to_user(formatDate(currentMonday));

        let html = `
            <div style="font-family: Arial, sans-serif; color: #1a1a1a; padding: 16px 20px;">
                <div style="text-align:center; border-bottom: 2px solid #2c3e50; padding-bottom: 8px; margin-bottom: 20px;">
                    <div style="font-size: 20px; font-weight: bold; letter-spacing: 1px;">WEEKLY MEAL PLAN</div>
                    <div style="font-size: 13px; color: #555; margin-top: 4px;">Week of ${weekLabel}</div>
                </div>
        `;

        dates.forEach((dateStr, idx) => {
            // Find customers active on this day (task date range covers this date)
            const dayDate = parseLocalDate(dateStr);
            const activeRows = [];

            tasks.forEach(task => {
                const start = parseLocalDate(task.exp_start_date);
                const end = parseLocalDate(task.exp_end_date);
                if (dayDate < start || dayDate > end) return;

                const reservation = task.custom_reservation || '';
                const sched = reservation ? (mealSchedules[reservation] || {}) : {};
                const daySchedule = sched[dateStr]; // {Breakfast, Lunch, Dinner} or undefined

                const assigned = (mealLookup[dateStr] || {})[task.custom_customer] || {};

                // Decide which meals to show
                // If daySchedule exists and has at least one true, use it; else show all 3
                const showBreakfast = daySchedule ? !!daySchedule.Breakfast : true;
                const showLunch     = daySchedule ? !!daySchedule.Lunch     : true;
                const showDinner    = daySchedule ? !!daySchedule.Dinner    : true;

                activeRows.push({
                    customer_name: task.custom_customer_name || task.custom_customer,
                    no_of_people: task.custom_no_of_people || 0,
                    showBreakfast, showLunch, showDinner,
                    breakfast: assigned['Breakfast'] || '',
                    lunch:     assigned['Lunch']     || '',
                    dinner:    assigned['Dinner']    || ''
                });
            });

            if (activeRows.length === 0) return;

            const totalPeople = activeRows.reduce((s, r) => s + parseInt(r.no_of_people || 0), 0);
            const userDate = frappe.datetime.str_to_user(dateStr);

            html += `
                <div style="margin-bottom: 22px; page-break-inside: avoid;">
                    <div style="background: #2c3e50; color: #fff; padding: 7px 12px; font-size: 13px; font-weight: bold; letter-spacing: 0.5px;">
                        ${fullDayNames[idx].toUpperCase()} &nbsp;·&nbsp; ${userDate}
                    </div>
                    <table style="width:100%; border-collapse:collapse; font-size:11px;">
                        <thead>
                            <tr style="background:#ecf0f1;">
                                <th style="border:1px solid #bdc3c7; padding:5px 8px; text-align:left; width:30%;">Customer</th>
                                <th style="border:1px solid #bdc3c7; padding:5px 8px; text-align:center; width:7%;">Pax</th>
                                <th style="border:1px solid #bdc3c7; padding:5px 8px; text-align:left; width:21%;">Breakfast</th>
                                <th style="border:1px solid #bdc3c7; padding:5px 8px; text-align:left; width:21%;">Lunch</th>
                                <th style="border:1px solid #bdc3c7; padding:5px 8px; text-align:left; width:21%;">Dinner</th>
                            </tr>
                        </thead>
                        <tbody>
            `;

            activeRows.forEach((row, i) => {
                const bg = i % 2 === 0 ? '#ffffff' : '#f9f9f9';

                function mealCell(show, name) {
                    if (!show) return `<td style="border:1px solid #bdc3c7; padding:5px 8px; background:#f0f0f0; color:#aaa; text-align:center;">–</td>`;
                    if (name) return `<td style="border:1px solid #bdc3c7; padding:5px 8px; background:#eafaf1; font-weight:600;">${name}</td>`;
                    return `<td style="border:1px solid #bdc3c7; padding:5px 8px; color:#e74c3c; font-style:italic;">Not assigned</td>`;
                }

                html += `
                    <tr style="background:${bg};">
                        <td style="border:1px solid #bdc3c7; padding:5px 8px; font-weight:500;">${row.customer_name}</td>
                        <td style="border:1px solid #bdc3c7; padding:5px 8px; text-align:center; font-weight:bold;">${row.no_of_people}</td>
                        ${mealCell(row.showBreakfast, row.breakfast)}
                        ${mealCell(row.showLunch, row.lunch)}
                        ${mealCell(row.showDinner, row.dinner)}
                    </tr>
                `;
            });

            html += `
                        </tbody>
                        <tfoot>
                            <tr style="background:#dfe6e9; font-weight:bold; font-size:11px;">
                                <td style="border:1px solid #bdc3c7; padding:5px 8px;">Total</td>
                                <td style="border:1px solid #bdc3c7; padding:5px 8px; text-align:center;">${totalPeople}</td>
                                <td colspan="3" style="border:1px solid #bdc3c7; padding:5px 8px;"></td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            `;
        });

        html += `<div style="margin-top:12px; font-size:9px; color:#999; text-align:right;">
            Generated ${frappe.datetime.str_to_user(frappe.datetime.nowdate())}
        </div></div>`;

        html2pdf().set({
            margin: [0.35, 0.35, 0.35, 0.35],
            filename: `Meal_Plan_${formatDate(currentMonday)}.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2, useCORS: true, logging: false },
            jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' }
        }).from(html, 'string').save();
    }

    $(document).on('click', '#download-pdf', function () {
        const mondayStr = formatDate(currentMonday);
        const dates = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(currentMonday);
            d.setDate(currentMonday.getDate() + i);
            dates.push(formatDate(d));
        }

        const $btn = $('#download-pdf').prop('disabled', true).text('Generating...');

        let pending = 3;
        let tasksData = [], entriesData = [], schedulesData = {};

        function checkAndBuild() {
            pending--;
            if (pending > 0) return;
            $btn.prop('disabled', false).text('Download PDF');
            buildAndDownloadPDF(tasksData, entriesData, schedulesData, dates);
        }

        frappe.call({
            method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.get_meal_plan_tasks_with_diets',
            args: { monday: mondayStr },
            callback: function(r) {
                tasksData = r.message || [];
                // Once tasks are loaded, fetch schedules using their reservations
                const reservationNames = [...new Set(tasksData.map(t => t.custom_reservation).filter(Boolean))];
                if (reservationNames.length) {
                    frappe.call({
                        method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.get_meal_schedules',
                        args: { reservation_names: JSON.stringify(reservationNames) },
                        callback: function(sr) {
                            schedulesData = sr.message || {};
                            checkAndBuild();
                        }
                    });
                } else {
                    checkAndBuild();
                }
                checkAndBuild(); // count tasks call as done
            }
        });

        frappe.call({
            method: 'food_processing.food_processing.page.meal_assignment.meal_assignment.get_meal_entries_for_dates',
            args: { dates_json: JSON.stringify(dates) },
            callback: function(r) {
                entriesData = r.message || [];
                checkAndBuild();
            }
        });
    });

    // Initialize the page
    renderWeekView(currentDate);


};
