frappe.pages['meal-assignment'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Meal Assignment',
		single_column: true
	});

	let currentDate = frappe.datetime.nowdate();
    let container = $('<div class="meal-assignment-container p-4 overflow-auto"></div>').appendTo(page.body);

    function getMonday(date) {
        let d = new Date(date);
        let day = d.getDay(),
            diff = d.getDate() - day + (day === 0 ? -6 : 1);
        return new Date(d.setDate(diff));
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

    function renderWeekView(baseDate) {
        container.empty();

        let monday = getMonday(baseDate);
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

                tasks.forEach(task => {
                    const customer = task.custom_customer;
                    const no_of_people = task.custom_no_of_people;
                    const start = frappe.datetime.str_to_obj(task.exp_start_date);
                    const end = frappe.datetime.str_to_obj(task.exp_end_date);

                    getColorForCustomer(customer, assignedColors);

                    if (!customerMap[customer]) {
                        customerMap[customer] = {
                            no_of_people: no_of_people,
                            days: {}
                        };
                    }

                    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
                        let key = formatDate(new Date(d));
                        if (new Date(key) >= monday && new Date(key) <= sunday) {
                            customerMap[customer].days[key] = true;
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

                Object.keys(customerMap).forEach(customer => {
                    const entry = customerMap[customer];
                    const color = assignedColors[customer];
                    const colorBox = `<span style="
                        display:inline-block;
                        width:12px; height:12px;
                        background-color:${color};
                        border-radius:3px;
                        margin-right:6px;
                        vertical-align:middle;
                    "></span>`;

                    const row = $(`<tr><td style="text-align:left;">${colorBox}${customer}</td><td>${entry.no_of_people}</td></tr>`);

                    for (let i = 0; i < 7; i++) {
						const d = new Date(monday);
						d.setDate(monday.getDate() + i);
						const key = formatDate(d);
						const highlight = entry.days[key] === true;
					
			
						const start = new Date(entry.exp_start_date);
						const end = new Date(entry.exp_end_date);
					
						const isActive = d.getTime() >= start.getTime() && d.getTime() <= end.getTime();
					
						for (let j = 0; j < 3; j++) {
							const cell = $(`<td class="border text-center min-w-[100px] h-[50px] text-xs align-middle"></td>`);
					
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
									$(this).html(`
										<div class="flex items-center justify-between px-1">
											<span class="truncate">${mealName}</span>
											<button class="text-red-500 text-xs remove-meal">&times;</button>
										</div>
									`);
								});
								cell.on('click', function () {
									if (!selectedMeal) return; 
									
									$(this).html(`
										<div class="flex items-center justify-between px-1">
											<span class="truncate">${selectedMeal}</span>
											<button class="text-red-500 text-xs remove-meal">&times;</button>
										</div>
									`);
								});
								
					
								
								cell.on('click', '.remove-meal', function (e) {
									e.stopPropagation();
									$(this).closest('td').empty();
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

    renderWeekView(currentDate);
};
