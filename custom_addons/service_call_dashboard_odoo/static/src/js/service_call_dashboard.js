/** @odoo-module */
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, onMounted, useState } = owl;
import { jsonrpc } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { Dialog } from "@web/core/dialog/dialog";


export class ServiceProjectDashboard extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.flag = 0;

        // Initialize state with safe defaults
        this.state = useState({
            isClearingFilter: false,
            isApplyingFilter: false,
            sidebarActive: false,
            currentView: 'companies',
            companies: [],
            departments: [],
            subdepartments: [],
            selectedCompany: null,
            selectedDepartment: null,
            selectedSubDepartment: null,
            selectedState: null,
            selectedCity: null,
            states: [],
            cities: [],
            selectedCities: [],
            teamStats: {
                total_team: 0,
                free_team: 0,
                running_overdue: 0,
                occupied: 0,
                on_leave: 0
            },
            filterActive: false,
            planned_today_tasks: 0,
            resolved_today_tasks: 0,
            total_stage_tasks_today: 0,
            new_stage_tasks_today: 0,
            calls_assigned_today: 0,
            calls_unassigned_today: 0,
            calls_on_hold_today: 0,
            calls_closed_today: 0

        });

        // Bind methods to ensure proper 'this' context
        this.toggleMainSidebar = this.toggleMainSidebar.bind(this);
        this.selectState = this.selectState.bind(this);
        this.selectCity = this.selectCity.bind(this);
        this.handleTeamClick = this.handleTeamClick.bind(this);
        this.handleFreeClick = this.handleFreeClick.bind(this);
        this.handleOverdueClick = this.handleOverdueClick.bind(this);
        this.handleOccupiedClick = this.handleOccupiedClick.bind(this);
        this.handleOnLeaveClick = this.handleOnLeaveClick.bind(this);

//        onWillStart(this.onWillStart.bind(this));
        onMounted(this.onMounted.bind(this));
        onMounted(() => {
            const fromInput = document.querySelector('.from-date');
            const toInput = document.querySelector('.to-date');

            if (fromInput && toInput) {
                const today = new Date();
                const oneMonthAgo = new Date();
                oneMonthAgo.setMonth(today.getMonth() - 1);

                fromInput.value = oneMonthAgo.toISOString().split('T')[0]; // yyyy-mm-dd
                toInput.value = today.toISOString().split('T')[0];         // yyyy-mm-dd
                console.log("From Date", fromInput.value)
                console.log("To Date", toInput.value)
            }
            // Add click event listener for overlay with null checks
            document.addEventListener('click', (e) => {
                const sidebar = document.querySelector('.main-sidebar');
                const toggleBtn = document.querySelector('.sidebar-toggle-btn');

                if (this.state.sidebarActive &&
                    sidebar &&
                    toggleBtn &&
                    !sidebar.contains(e.target) &&
                    !toggleBtn.contains(e.target)) {
                    this.toggleMainSidebar();
                }
            });

            // Add filter button event listener with null check
            const filterButton = document.querySelector('.apply-date-filter');
            if (filterButton) {
                filterButton.addEventListener('click', async () => {
                    const fromDate = fromInput?.value;
                    const toDate = toInput?.value;
                    console.log("From Date", fromDate)
                    console.log("To Date", toDate)
                    if (fromDate && toDate && new Date(toDate) < new Date(fromDate)) {
                        alert("End date cannot be earlier than start date.");
                        return;
                    }
                    // Call the functions only if date range is valid
                    await this.updateTotals();
                    this.saveFiltersToStorage();
                });
            }

            // Add chart loading button event listener with null check
            const loadChartsButton = document.querySelector('.load-charts-button');
            if (loadChartsButton) {
                loadChartsButton.addEventListener('click', async () => {
                    await this.loadCharts();
                });
            }

            // Add charts section display toggle with null check
            const chartsButton = document.querySelector('.load-charts-button');
            const chartsSection = document.querySelector('.charts-section_data');
            if (chartsButton && chartsSection) {
                chartsButton.addEventListener('click', function() {
                    chartsSection.style.display = 'block';
                });
            }
            // Add form button event listeners with null check
            document.querySelectorAll(".load-form-button").forEach(button => {
                button.addEventListener("click", this.onClickOpenTaskForm.bind(this));
            });

            // Add app sidebar toggle functionality
            const appSidebarToggle = document.querySelector('.app-sidebar-toggle');
            const appSidebar = document.querySelector('.app-sidebar');

            if (appSidebarToggle && appSidebar) {
                appSidebarToggle.addEventListener('click', () => {
                    this.toggleMainSidebar();
                });
            }

            // Add click outside listener to close sidebar
            document.addEventListener('click', (e) => {
                const sidebar = document.querySelector('.main-sidebar');
                const toggleBtn = document.querySelector('.sidebar-toggle-btn');

                if (this.state.sidebarActive &&
                    !sidebar.contains(e.target) &&
                    !toggleBtn.contains(e.target)) {
                    this.toggleMainSidebar();
                }
            });

        });
    }


   async onMounted() {
        try {
            console.log("Component mounted, loading companies and filters...");
            await this.loadCompanies();
            this.loadFiltersFromStorage();
//            await this.updatePreviousTotal();// Load filters from localStorage
            const sidebarState = JSON.parse(localStorage.getItem('sidebarState'));
            const mainSidebar = document.querySelector('.main-sidebar');
            const dashboardContent = document.querySelector('.oh_service_call_dashboards');
            const toggleButton = document.querySelector('.sidebar-toggle-btn');

            if (sidebarState) {
                // If sidebar was open, set it to open
                if (mainSidebar && dashboardContent && toggleButton) {
                    mainSidebar.classList.add('show');
                    dashboardContent.classList.add('sidebar-active');
                    toggleButton.classList.add('active');
                }
            }
            await this.updateCallsToday(); // Fetch data based on loaded filters
            await this.updateTeamStats();
            await this.updateTotals();
            // Initialize any DOM-dependent features here
            const sidebar = document.querySelector('.main-sidebar');
            if (sidebar) {
                sidebar.addEventListener('click', (e) => {
                    // Prevent event bubbling if needed
                    e.stopPropagation();
                });
            }
        } catch (error) {
            console.error('Error in onMounted:', error);
        }
    }

    saveFiltersToStorage() {
        const filters = this.getFilterParams();
        console.log("Saving filters to localStorage:", filters);
        localStorage.setItem('serviceDashboardFilters', JSON.stringify(filters));
    }

   async loadFiltersFromStorage() {
       console.log("Attempting to load filters from localStorage...");
       const filters = JSON.parse(localStorage.getItem('serviceDashboardFilters'));
       console.log("Loaded filters from localStorage:", filters);
       if (filters) {
           this.state.selectedCompany = filters.company_id ? { id: filters.company_id } : null;
           this.state.selectedDepartment = filters.department_id ? { id: filters.department_id } : null;
           this.state.selectedSubDepartment = filters.subdepartment_id ? { id: filters.subdepartment_id } : null;
           this.state.selectedState = filters.state_id ? { id: filters.state_id } : null;
           this.state.selectedCity = filters.city ? { name: filters.city } : null;
           this.state.startDate = filters.start_date; // Load start date
           this.state.endDate = filters.end_date;     // Load end date
           this.state.selectedCities = filters.selectedCities || [];
           // Set the date input values
           const fromDateInput = document.querySelector('.from-date');
           const toDateInput = document.querySelector('.to-date');
           if (fromDateInput) fromDateInput.value = this.state.startDate || '';
           if (toDateInput) toDateInput.value = this.state.endDate || '';

            // Log the state after loading filters
           console.log("State after loading filters:", this.state);
           if (this.state.selectedCompany) {
                this.state.departments = await this.rpc('/get/service_departments/by_company', {
                    company_id: this.state.selectedCompany.id
                });
            }

            // If a department is selected, fetch its subdepartments
           if (this.state.selectedDepartment) {
                this.state.subdepartments = await this.rpc('/get/service_sub_departments', {
                    department_id: this.state.selectedDepartment.id
                });
           }

           if (this.state.selectedSubDepartment) {
                this.state.states = await this.rpc('/get/states/by_subdepartment', {
                    subdepartment_id: this.state.selectedSubDepartment.id
                });
            }
           // If a state is selected, fetch its cities
           if (this.state.selectedState) {
                this.state.cities = await this.rpc('/get/cities/by_state', {
                    subdepartment_id: this.state.selectedSubDepartment.id,
                    state_id: this.state.selectedState.id
                });
           }

       }
   }

   toggleCitySelection(cityItem) {
        const cityName = cityItem.name;
        const index = this.state.selectedCities.indexOf(cityName);
        if (index > -1) {
            // Already selected â€” remove
            this.state.selectedCities.splice(index, 1);
        } else {
            // Not selected â€” add
            this.state.selectedCities.push(cityName);
        }
        console.log("Selected Cities: ", this.state.selectedCities)
        // Save the selected cities to local storage
        this.saveFiltersToStorage(); // Call this to update local storage with the new selection
    }

    // Toggle main sidebar with null checks
    toggleMainSidebar() {
        const mainSidebar = document.querySelector('.main-sidebar');
        const dashboardContent = document.querySelector('.oh_service_call_dashboards');
        const toggleButton = document.querySelector('.sidebar-toggle-btn');

        if (mainSidebar && dashboardContent && toggleButton) {
            mainSidebar.classList.toggle('show');
            dashboardContent.classList.toggle('sidebar-active');
            toggleButton.classList.toggle('active');
            const isOpen = mainSidebar.classList.contains('show');
            localStorage.setItem('sidebarState', JSON.stringify(isOpen));

            // Update the icon direction
            const icon = toggleButton.querySelector('i');
            if (icon) {
                if (mainSidebar.classList.contains('show')) {
                    icon.classList.remove('bi-chevron-double-right');
                    icon.classList.add('bi-chevron-double-right');
                } else {
                    icon.classList.remove('bi-chevron-double-left');
                    icon.classList.add('bi-chevron-double-right');
                }
            }
        }
    }


    // Add this new method to handle filter parameters consistently
    getFilterParams() {
        const fromDate = document.querySelector('.from-date')?.value;
        const toDate = document.querySelector('.to-date')?.value;

        return {
            company_id: this.state.selectedCompany?.id || null,
            department_id: this.state.selectedDepartment?.id || null,
            subdepartment_id: this.state.selectedSubDepartment?.id || null,
            state_id: this.state.selectedState?.id || null,
//            city: this.state.selectedCity?.name || null,
            city: this.state.selectedCities || [],  // now an array of names
            start_date: fromDate || null,
            end_date: toDate || null,
            selectedCities: this.state.selectedCities || []
        };
    }

    async render_employee_task_chart() {
        try {
            const params = this.getFilterParams();
            const data = await this.rpc("/call/task/by_employee", params);
            console.log("Data received for employee task chart:", data);
            const datasets = data.labels.map((label, index) => {
                return {
                    label: label,
                    data: [data.data[index]],  // Single value
                    backgroundColor: data.colors[index],
                    borderColor: data.colors[index],
                    borderWidth: 1
                };
            });
            const ctx = document.getElementById("employee_task_chart").getContext('2d');
            if (!ctx) {
                throw new Error("Chart context not found");
            }

            // Destroy existing chart if it exists
            if (ctx.__chart__) {
                ctx.__chart__.destroy();
            }

            // Store the chart instance
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: [''], // Just one dummy category, since each dataset has its own bar
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (evt, elements) => {
                        if (elements && elements.length > 0) {
                            const clickedElement = elements[0];
                            const clickedLabel = data.labels[clickedElement.index];

                            if (clickedLabel) {
                                this.show_tasks_by_employee(clickedLabel);
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,

                            ticks: {
                                stepSize: 1,
                                callback: function(value) {
                                    if (Math.floor(value) === value) {
                                        return value;
                                    }
                                }
                            }
                        },
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: 'Tasks per Employee',
                            font: {
                                size: 16
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Tasks: ${context.raw}`;
                                }
                            }
                        }
                    }
                }
            });

            return ctx.__chart__;
        } catch (error) {
            console.error("Error rendering employee task chart:", error);
            throw error;
        }
    }

    async render_task_tags_chart() {
        try {
            const params = this.getFilterParams();
            const data = await this.rpc("/call/task/by_tags", params);
            console.log("Data received for task tags chart:", data);

            const ctx = document.getElementById("task_tags_chart");
            if (!ctx) {
                throw new Error("Chart context not found");
            }

            // Destroy existing chart if it exists
            if (ctx.__chart__) {
                ctx.__chart__.destroy();
            }

            // Store the chart instance
            ctx.__chart__ = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Number of Calls',
                        data: data.data,
                        backgroundColor: data.colors,
                        borderColor: data.colors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (evt, elements) => {
                        if (elements && elements.length > 0) {
                            const clickedElement = elements[0];
                            const clickedLabel = data.labels[clickedElement.index];

                            if (clickedLabel) {
                                this.show_tasks_by_tag(clickedLabel);
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Number of Tasks'
                            },
                            ticks: {
                                stepSize: 1,
                                callback: function(value) {
                                    if (Math.floor(value) === value) {
                                        return value;
                                    }
                                }
                            }
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Employees'
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Tasks by Tags',
                        font: {
                            size: 16
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Tasks: ${context.raw}`;
                            }
                        }
                    }
                }
            });
            return ctx.__chart__;
        } catch (error) {
            console.error("Error rendering task tags chart:", error);
            throw error;
        }
    }

    async render_task_stage_chart() {
        try {
            const params = this.getFilterParams();
            const data = await this.rpc("/call/stage/wise_chart", params);
            console.log("Data received for task stages chart:", data);

            const ctx = document.getElementById("task_stages_chart");
            if (!ctx) {
                throw new Error("Chart context not found");
            }

            // Destroy existing chart if it exists
            if (ctx.__chart__) {
                ctx.__chart__.destroy();
            }

            // Store the chart instance
            ctx.__chart__ = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: 'Number of Calls',
                        data: data.data,
                        backgroundColor: data.colors,
                        borderColor: data.colors,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (evt, elements) => {
                        if (elements && elements.length > 0) {
                            const clickedElement = elements[0];
                            const clickedLabel = data.labels[clickedElement.index];

                            if (clickedLabel) {
                                this.show_tasks_by_stage(clickedLabel);
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                stepSize: 1,
                                callback: function(value) {
                                    if (Math.floor(value) === value) {
                                        return value;
                                    }
                                }
                            }
                        },
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        },
                        title: {
                            display: true,
                            text: 'Tasks by Stages',
                            font: {
                                size: 16
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `Tasks: ${context.raw}`;
                                }
                            }
                        }
                    }
                }
            });

            return ctx.__chart__;
        } catch (error) {
            console.error("Error rendering task stages chart:", error);
            throw error;
        }
    }

//   async render_customer_task_chart() {
//        try {
//            const params = this.getFilterParams();
//            const data = await this.rpc("/call/customer/wise_chart", params);
//            console.log("Data received for customer task chart:", data);
//
//            const ctx = document.getElementById("customer_tasks_chart");
//            if (!ctx) {
//                throw new Error("Chart context not found");
//            }
//
//            // Destroy existing chart if it exists
//            if (ctx.__chart__) {
//                ctx.__chart__.destroy();
//            }
//
//            // Store the chart instance
//            ctx.__chart__ = new Chart(ctx, {
//                type: 'bar',
//                data: {
//                    labels: data.labels,
//                    datasets: [{
//                        label: 'Number of Calls',
//                        data: data.data,
//                        backgroundColor: data.colors,
//                        borderColor: data.colors,
//                        borderWidth: 1
//                    }]
//                },
//                options: {
//                    responsive: true,
//                    maintainAspectRatio: false,
//                    scales: {
//                        y: {
//                            beginAtZero: true,
//                            ticks: {
//                                stepSize: 1
//                            }
//                        }
//                    },
//                    plugins: {
//                        legend: {
//                            display: false
//                        }
//                    }
//                }
//            });
//        } catch (error) {
//            console.error("Error rendering customer task chart:", error);
//        }
//   }

//   async render_internal_external_task_chart() {
//        try {
//            const params = this.getFilterParams();
//            const data = await this.rpc("/call/task/customer_internal_external_chart", params);
//            console.log("Data received for internal/external task chart:", data);
//
//            const ctx = document.getElementById("chartElements");
//            if (!ctx) {
//                throw new Error("Chart context not found");
//            }
//
//            // Destroy existing chart if it exists
//            if (ctx.__chart__) {
//                ctx.__chart__.destroy();
//            }
//
//            // Store the chart instance
//            ctx.__chart__ = new Chart(ctx, {
//                type: 'pie',
//                data: {
//                    labels: data.labels,
//                    datasets: [{
//                        data: data.data,
//                        backgroundColor: data.colors,
//                        borderColor: data.colors,
//                        borderWidth: 1
//                    }]
//                },
//                options: {
//                    responsive: true,
//                    maintainAspectRatio: false,
//                    plugins: {
//                        legend: {
//                            position: 'bottom'
//                        }
//                    }
//                }
//            });
//        } catch (error) {
//            console.error("Error rendering internal/external task chart:", error);
//        }
//   }

   async render_filter() {
        try {
            const data = await this.rpc('/calls/filter');
            const [projects, employees] = data;

            const projectSelect = document.getElementById('project_selection');
            const employeeSelect = document.getElementById('employee_selection');

            if (projectSelect && employeeSelect) {
                projects.forEach(project => {
                    projectSelect.insertAdjacentHTML('beforeend',
                        `<option value="${project.id}">${project.name}</option>`);
                });

                employees.forEach(employee => {
                    employeeSelect.insertAdjacentHTML('beforeend',
                        `<option value="${employee.id}">${employee.name}</option>`);
                });
            }
        } catch (error) {
            console.error("Error rendering filters:", error);
        }
   }

   async show_tasks_by_tag(tag) {
        if (!tag) {
            console.error("Invalid tag provided");
            return;
        }
        try {
            console.log("Navigating to tasks for tag:", tag);
            this.action.doAction({
                name: _t(`Tasks for Tag: ${tag}`),  // Fixed template string syntax
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: [['tag_ids.name', 'ilike', tag], ['is_fsm', '=', true]],
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current'
            });
        } catch (error) {
            console.error("Error showing tasks for tag:", tag, error);
        }
   }

   async show_tasks_by_employee(employee) {
        if (!employee) {
            console.error("Employee name is undefined or null");
            return;
        }

        try {
            console.log("Navigating to tasks for employee:", employee);
            this.action.doAction({
                name: _t(`Tasks for Employee: ${employee}`),  // Fixed template string syntax
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                domain: [['user_ids.name', '=', employee], ['is_fsm', '=', true]],
                views: [
                    [false, 'list'],
                    [false, 'form'],
                    [false, 'kanban']
                ],
                target: 'current'
            });
        } catch (error) {
            console.error("Error showing tasks for employee:", employee, error);
        }
   }

//   total_unassigned_task(e) {
//        e.stopPropagation();
//        e.preventDefault();
//        this.action.doAction({
//            name: _t("Unassigned Calls"),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            domain: [['user_ids', '=', false], ['is_fsm', '=', true]],
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current'
//        });
//   }
   async show_total_calls_today(e) {
        const result = await this.rpc('/call/task/click', {
            task_type: 'total',
            company_id: this.state.selectedCompany?.id,
            department_id: this.state.selectedDepartment?.id,
            subdepartment_id: this.state.selectedSubDepartment?.id
        });
        if (result.error) {
            throw new Error(result.error);
        }
        if (result.task_ids) {
            await this.action.doAction({
                name: 'Total Tasks Today',
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', result.task_ids], ['is_fsm', '=', true]],
                target: 'current'
            });
        }
   }


    async new_stage_tasks_today_click(e) {
        const result = await this.rpc('/call/task/click', {
            task_type: 'in_progress',
            company_id: this.state.selectedCompany?.id,
            department_id: this.state.selectedDepartment?.id,
            subdepartment_id: this.state.selectedSubDepartment?.id
        });

        if (result.error) {
            throw new Error(result.error);
        }
        if (result.task_ids) {
            await this.action.doAction({
               name: 'In Progress Calls',
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', result.task_ids],['is_fsm', '=', true]],
                target: 'current'
            });
        }
    }

    async show_assigned_calls_today(e) {
        const result = await this.rpc('/call/task/click', {
            task_type: 'assigned',
            company_id: this.state.selectedCompany?.id,
            department_id: this.state.selectedDepartment?.id,
            subdepartment_id: this.state.selectedSubDepartment?.id
        });
        if (result.error) {
            throw new Error(result.error);
        }
        if (result.task_ids) {
            await this.action.doAction({
               name: 'Assigned Tasks Today',
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', result.task_ids],['is_fsm', '=', true]],
                target: 'current'
            });
        }
    }

    async show_unassigned_calls_today(e) {
        const result = await this.rpc('/call/task/click', {
            task_type: 'unassigned',
            company_id: this.state.selectedCompany?.id,
            department_id: this.state.selectedDepartment?.id,
            subdepartment_id: this.state.selectedSubDepartment?.id
        });
        if (result.error) {
            throw new Error(result.error);
        }
        if (result.task_ids) {
            await this.action.doAction({
               name: 'Unassigned Tasks Today',
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', result.task_ids],['is_fsm', '=', true]],
                target: 'current'
            });
        }
    }

    async calls_on_hold_today_click(e) {
        const result = await this.rpc('/call/task/click', {
            task_type: 'on_hold',
            company_id: this.state.selectedCompany?.id,
            department_id: this.state.selectedDepartment?.id,
            subdepartment_id: this.state.selectedSubDepartment?.id
        });
        if (result.error) {
            throw new Error(result.error);
        }
        if (result.task_ids) {
            await this.action.doAction({
                name: 'On Hold Tasks Today',
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', result.task_ids],['is_fsm', '=', true]],
                target: 'current'
            });
        }
    }

    async show_closed_calls_today(e) {
        const result = await this.rpc('/call/task/click', {
            task_type: 'closed',
            company_id: this.state.selectedCompany?.id,
            department_id: this.state.selectedDepartment?.id,
            subdepartment_id: this.state.selectedSubDepartment?.id
        });
        if (result.error) {
            throw new Error(result.error);
        }
        if (result.task_ids) {
            await this.action.doAction({
                name: 'Closed Tasks Today',
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', result.task_ids],['is_fsm', '=', true]],
                target: 'current'
            });
        }
    }

    //    new code added by satyam
    async today_in_planned_count_click(e) {
            const result = await this.rpc('/call/task/click', {
                task_type: 'today_planned',
                company_id: this.state.selectedCompany?.id,
                department_id: this.state.selectedDepartment?.id,
                subdepartment_id: this.state.selectedSubDepartment?.id
            });
            if (result.error) {
                throw new Error(result.error);
            }
            if (result.task_ids) {
                await this.action.doAction({
                    name: 'Planned Calls Today',
                    type: 'ir.actions.act_window',
                    res_model: 'project.task',
                    views: [[false, 'list'], [false, 'form']],
                    domain: [['id', 'in', result.task_ids],['is_fsm', '=', true]],
                    target: 'current'
                });
            }
        }



    async today_in_resolved_count_click(e) {
        const result = await this.rpc('/call/task/click', {
            task_type: 'today_resolved',
            company_id: this.state.selectedCompany?.id,
            department_id: this.state.selectedDepartment?.id,
            subdepartment_id: this.state.selectedSubDepartment?.id
        });
        if (result.error) {
            throw new Error(result.error);
        }
        if (result.task_ids) {
            await this.action.doAction({
                name: 'Call Resolved Today',
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', result.task_ids],['is_fsm', '=', true]],
                target: 'current'
            });
        }
    }

//// Helper method to get user's accessible departments
//async getUserAccessibleDepartments() {
//    try {
//        console.log("In user acces department function")
//        // Get current user info
//        const currentUser = await this.rpc('/web/dataset/call_kw', {
//            model: 'res.users',
//            method: 'read',
//            args: [this.env.services.user.userId, ['employee_id']],
//            kwargs: {}
//        });
//        console.log("this is my my cuirrent user", currentUser)
//
//        const userData = currentUser[0];  // Your RPC result
//        const employeeId = userData.employee_id?.[0];  // 21
////        const employeeName = userData.employee_id?.[1];  // "user"
//
//        console.log('Employee ID:', employeeId);
//
//
//        // Get employee's department
//        const employee = await this.rpc('/web/dataset/call_kw', {
//            model: 'hr.employee',
//            method: 'read',
//            args: [employeeId, ['department_id']],
//            kwargs: {}
//        });
//        console.log("this is my dept", employee[0].department_id[0])
//        let baseDeptIds = [];
//        if (employee.length && employee[0].department_id) {
//            baseDeptIds.push(employee[0].department_id[0]);
//        }
//
//        // Get departments from call.visibility
//        const visibilityRecords = await this.rpc('/web/dataset/call_kw', {
//            model: 'call.visibility',
//            method: 'search_read',
//            args: [[['employee_id', '=', employeeId]]],
//            kwargs: { fields: ['department_id'] }
//        });
//
//        const visibilityDeptIds = visibilityRecords
//            .filter(record => record.department_id)
//            .map(record => record.department_id[0]);
//        console.log("dept vis", visibilityDeptIds)
//        // Combine and remove duplicates
//        return [...new Set([...baseDeptIds, ...visibilityDeptIds])];
//
//    } catch (err) {
//        console.error("Error getting user accessible departments:", err);
//        return [];
//    }
//}

async all_tasks_total_click(e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }

    try {
        const params = this.getFilterParams();
        const result = await this.rpc('/call/task/click', {
            task_type: 'all_tasks_total',
            ...params
        });

        const domain = (result.task_ids && result.task_ids.length > 0)
            ? [['id', 'in', result.task_ids]]
            : [['id', '=', 0]];

        await this.action.doAction({
            name: _t('Total Assigned Tasks'),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current',
            context: {
                group_by: 'stage_id',
            },
        });

    } catch (err) {
        console.error("Error", err);
        this.notification.add(_t("Failed to load tasks."), { type: 'danger' });
    }
}


//async all_tasks_total_click(e) {
//    e.stopPropagation();
//    e.preventDefault();
//
//    try {
//        const params = this.getFilterParams();
//
//        // Apply domain filters based on what was sent
//
//        if (params.start_date && params.end_date) {
//            domain.push(['create_date', '>=', params.start_date]);
//            domain.push(['create_date', '<=', params.end_date]);
//        }
//
//        if (params.company_id) {
//            domain.push(['company_id', '=', params.company_id]);
//        }
//
//
//
//        // Apply department filters based on admin status
//        if (params.department_id) {
//            domain.push(['department_id', 'child_of', params.department_id]);
//        } else if (params.subdepartment_id) {
//            domain.push(['department_id', '=', params.subdepartment_id]);
//        }
//        console.log("this is domain", domain)
//        if (params.state_id || params.city) {
//            const partner_domain = [];
//            console.log("I am Inside the state")
//            if (params.state_id) {
//                console.log("i am here in state", params.state_id)
//                partner_domain.push(['state_id', '=', params.state_id]);
//            }
//            if (params.city && params.city !== '' && !(Array.isArray(params.city) && params.city.length === 0)) {
//                partner_domain.push(['city', 'ilike', params.city]);
//            }
//            console.log("New Partner Domain", partner_domain)
//
//            // Search partner_ids based on state and city
//            const partner_ids = await this.rpc('/web/dataset/call_kw', {
//                model: 'res.partner',
//                method: 'search',
//                args: [partner_domain],
//                kwargs: {}
//            });
//
//            if (partner_ids.length) {
//                domain.push(['partner_id', 'in', partner_ids]);
//            } else {
//                // Optional: handle no partners found
//                alert("No partners found for the selected city/state.");
//                return;
//            }
//        }
//        // Open view with domain
//        await this.action.doAction({
//            name: _t('Total Assigned Tasks'),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            views: [[false, 'list'], [false, 'form']],
//            domain: domain,
//            target: 'current',
//            context: {
//                group_by: 'stage_id',
//            },
//        });
//
//    } catch (err) {
//        console.error("Error", err);
//    }
//}

async all_assigned_tasks_total_click(e) {
    e.stopPropagation();
    e.preventDefault();

    try {
        const params = this.getFilterParams();

        const result = await this.rpc('/call/task/click', {
            task_type: 'assigned',
            company_id: params.company_id,
            department_id: params.department_id,
            subdepartment_id: params.subdepartment_id,
            start_date: params.start_date,
            end_date: params.end_date,
        });

        if (result.error) {
            throw new Error(result.error);
        }

        if (result.task_ids && result.task_ids.length) {
            await this.action.doAction({
                name: _t('Total Assigned Calls'),
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'list'], [false, 'form']],
                domain: [['id', 'in', result.task_ids], ['is_fsm', '=', true]],
                target: 'current',
                context: {
                    group_by: 'stage_id',
                },
            });
        } else {
            alert("No assigned tasks found.");
        }
    } catch (err) {
        console.error("Error in all_assigned_tasks_total_click", err);
    }
}


//async all_assigned_tasks_total_click(e) {
//    e.stopPropagation();
//    e.preventDefault();
//
//    try {
//        const params = this.getFilterParams();
//        let domain;
//        domain = [['is_fsm', '=', true],["stage_id.name", '=', 'Assigned']];
//        // Apply domain filters based on what was sent
//
//        if (params.start_date && params.end_date) {
//            domain.push(['create_date', '>=', params.start_date]);
//            domain.push(['create_date', '<=', params.end_date]);
//        }
//
//        if (params.company_id) {
//            domain.push(['company_id', '=', params.company_id]);
//        }
//        if (params.department_id) {
//            domain.push(['department_id', 'child_of', params.department_id])
//        } else if (params.subdepartment_id) {
//            domain.push(['department_id', '=', params.subdepartment_id]);
//        }
//
//        if (params.state_id || params.city) {
//            const partner_domain = [];
//            console.log("I am Inside the state")
//            if (params.state_id) {
//                console.log("i am here in state", params.state_id)
//                partner_domain.push(['state_id', '=', params.state_id]);
//            }
//            if (params.city && params.city !== '' && !(Array.isArray(params.city) && params.city.length === 0)) {
//                partner_domain.push(['city', 'ilike', params.city]);
//            }
//            console.log("New Partner Domain", partner_domain)
//
//            // Search partner_ids based on state and city
//            const partner_ids = await this.rpc('/web/dataset/call_kw', {
//                model: 'res.partner',
//                method: 'search',
//                args: [partner_domain],
//                kwargs: {}
//            });
//
//            if (partner_ids.length) {
//                domain.push(['partner_id', 'in', partner_ids]);
//            } else {
//                // Optional: handle no partners found
//                alert("No partners found for the selected city/state.");
//                return;
//            }
//        }
//        // Open view with domain
//        await this.action.doAction({
//            name: _t('Total Assigned Tasks'),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            views: [[false, 'list'], [false, 'form']],
//            domain: domain,
//            target: 'current',
//            context: {
//                group_by: 'stage_id',
//            },
//        });
//
//    } catch (err) {
//        console.error("Error in sync_all_assigned_tasks_total_click", err);
//    }
//}

//async all_unassigned_tasks_total_click(e) {
//    if (e) {
//        e.stopPropagation();
//        e.preventDefault();
//    }
//    try {
//        const params = this.getFilterParams();
//        const result = await this.rpc('/previous/total', {
//            task_type: 'all_unassigned_tasks_total',
//            ...params
//        });
//        let domain;
//        if (result.task_ids && result.task_ids.length > 0) {
//            domain = [['id', 'in', result.task_ids], ['is_fsm', '=', true]];
//        } else {
//            // Fallback domain if no specific IDs
//            domain = [["user_ids", "=", false], ['is_fsm', '=', true]];
//            // Add other filter params
//            if (params.start_date && params.end_date) {
//                domain.push(['create_date', '>=', params.start_date]);
//                domain.push(['create_date', '<=', params.end_date]);
//            }
//            if (params.company_id) domain.push(['company_id', '=', params.company_id]);
//            if (params.department_id) domain.push(['department_id', 'child_of', params.department_id]);
//            if (params.subdepartment_id) domain.push(['department_id', '=', params.subdepartment_id]);
//
//            if (params.state_id || params.city) {
//                const partner_domain = [];
//
//                if (params.state_id) {
//                    partner_domain.push(['state_id', '=', params.state_id]);
//                }
//                if (params.city && params.city !== '' && !(Array.isArray(params.city) && params.city.length === 0)) {
//                    partner_domain.push(['city', 'ilike', params.city]);
//                }
//
//                // Search partner_ids based on state and city
//                const partner_ids = await this.rpc('/web/dataset/call_kw', {
//                    model: 'res.partner',
//                    method: 'search',
//                    args: [partner_domain],
//                    kwargs: {}
//                });
//
//
//                if (partner_ids.length) {
//                    domain.push(['partner_id', 'in', partner_ids]);
//                } else {
//                    // Optional: handle no partners found
//                    alert("No partners found for the selected city/state.");
//                    return;
//                }
//            }
//        }
//
//        await this.action.doAction({
//            name: _t('Total Assigned Tasks'),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            views: [[false, 'list'], [false, 'form']],
//            domain: domain,
//            target: 'current'
//        });
//    } catch (error) {
//
//        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
//    }
//}

async all_unassigned_tasks_total_click(e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }

    try {
        const params = this.getFilterParams();
        const result = await this.rpc('/call/task/click', {
            task_type: 'unassigned',
            ...params
        });

        const domain = (result.task_ids && result.task_ids.length > 0)
            ? [['id', 'in', result.task_ids]]
            : [['id', '=', 0]];

        await this.action.doAction({
            name: _t('All Unassigned Calls'),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current'
        });
    } catch (error) {
        console.error("Failed to load unassigned tasks:", error);
        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
    }
}


//async all_on_hold_tasks_total_click(e) {
//    if (e) {
//        e.stopPropagation();
//        e.preventDefault();
//    }
//    try {
//        const params = this.getFilterParams();
//        const result = await this.rpc('/previous/total', {
//            task_type: 'all_on_hold_tasks_total',
//            ...params
//        });
//        let domain;
//        if (result.task_ids && result.task_ids.length > 0) {
//            domain = [['id', 'in', result.task_ids], ['is_fsm', '=', true]];
//        } else {
//            // Fallback domain if no specific IDs Pending
//            domain = [['is_fsm', '=', true],["stage_id.name", '=', 'Pending']];
//            // Add other filter params
//            if (params.start_date && params.end_date) {
//                domain.push(['create_date', '>=', params.start_date]);
//                domain.push(['create_date', '<=', params.end_date]);
//            }
//            if (params.company_id) domain.push(['company_id', '=', params.company_id]);
//            if (params.department_id) domain.push(['department_id', 'child_of', params.department_id]);
//            if (params.subdepartment_id) domain.push(['department_id', '=', params.subdepartment_id]);
//            if (params.state_id || params.city) {
//                const partner_domain = [];
//
//                if (params.state_id) {
//                    partner_domain.push(['state_id', '=', params.state_id]);
//                }
//                if (params.city && params.city !== '' && !(Array.isArray(params.city) && params.city.length === 0)) {
//                    partner_domain.push(['city', 'ilike', params.city]);
//                }
//
//                // Search partner_ids based on state and city
//                const partner_ids = await this.rpc('/web/dataset/call_kw', {
//                    model: 'res.partner',
//                    method: 'search',
//                    args: [partner_domain],
//                    kwargs: {}
//                });
//
//
//                if (partner_ids.length) {
//                    domain.push(['partner_id', 'in', partner_ids]);
//                } else {
//                    // Optional: handle no partners found
//                    alert("No partners found for the selected city/state.");
//                    return;
//                }
//            }
//        }
//        await this.action.doAction({
//            name: _t('Total Assigned Tasks'),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            views: [[false, 'list'], [false, 'form']],
//            domain: domain,
//            target: 'current'
//        });
//    } catch (error) {
//        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
//    }
//}


async all_on_hold_tasks_total_click(e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }

    try {
        const params = this.getFilterParams();
        const result = await this.rpc('/call/task/click', {
            task_type: 'on_hold',
            ...params
        });

        const domain = (result.task_ids && result.task_ids.length > 0)
            ? [['id', 'in', result.task_ids]]
            : [['id', '=', 0]];

        await this.action.doAction({
            name: _t('On Hold Calls'),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current'
        });
    } catch (error) {
        console.error("Error loading on-hold tasks:", error);
        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
    }
}


//async all_closed_tasks_total_click(e) {
//    if (e) {
//        e.stopPropagation();
//        e.preventDefault();
//    }
//    try {
//        const params = this.getFilterParams();
//        const result = await this.rpc('/previous/total', {
//            task_type: 'all_closed_tasks_total',
//            ...params
//        });
//        let domain;
//        if (result.task_ids && result.task_ids.length > 0) {
//            domain = [['id', 'in', result.task_ids], ['is_fsm', '=', true]];
//        } else {
//            // Fallback domain if no specific IDs
//            domain = [
//                ["user_ids", "!=", false],
//                ["is_fsm", "=", true],
//                "|",
//                ["stage_id.name", "=", "Done"],
//                ["stage_id.name", "=", "Cancelled"]
//            ];
//
//            // Add other filter params
//            if (params.start_date && params.end_date) {
//                domain.push(['create_date', '>=', params.start_date]);
//                domain.push(['create_date', '<=', params.end_date]);
//            }
//            if (params.company_id) domain.push(['company_id', '=', params.company_id]);
//            if (params.department_id) domain.push(['department_id', 'child_of', params.department_id]);
//            if (params.subdepartment_id) domain.push(['department_id', '=', params.subdepartment_id]);
//            if (params.state_id || params.city) {
//                const partner_domain = [];
//
//                if (params.state_id) {
//                    partner_domain.push(['state_id', '=', params.state_id]);
//                }
//                if (params.city && params.city !== '' && !(Array.isArray(params.city) && params.city.length === 0)) {
//                    partner_domain.push(['city', 'ilike', params.city]);
//                }
//
//                // Search partner_ids based on state and city
//                const partner_ids = await this.rpc('/web/dataset/call_kw', {
//                    model: 'res.partner',
//                    method: 'search',
//                    args: [partner_domain],
//                    kwargs: {}
//                });
//
//
//                if (partner_ids.length) {
//                    domain.push(['partner_id', 'in', partner_ids]);
//                } else {
//                    // Optional: handle no partners found
//                    alert("No partners found for the selected city/state.");
//                    return;
//                }
//            }
//        }
//        await this.action.doAction({
//            name: _t('Total Assigned Tasks'),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            views: [[false, 'list'], [false, 'form']],
//            domain: domain,
//            target: 'current'
//        });
//    } catch (error) {
//
//        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
//    }
//}

async all_closed_tasks_total_click(e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }

    try {
        const params = this.getFilterParams();
        const result = await this.rpc('/call/task/click', {
            task_type: 'closed',
            ...params
        });

        const domain = (result.task_ids && result.task_ids.length > 0)
            ? [['id', 'in', result.task_ids]]
            : [['id', '=', 0]];

        await this.action.doAction({
            name: _t('Closed Calls'),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current'
        });
    } catch (error) {
        console.error("Error loading closed tasks:", error);
        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
    }
}


//async in_progress_count_click(e) {
//    if (e) {
//        e.stopPropagation();
//        e.preventDefault();
//    }
//    try {
//        const params = this.getFilterParams();
//        const result = await this.rpc('/previous/total', {
//            task_type: 'in_progress_count',
//            ...params
//        });
//
//        let domain;
//        if (result.task_ids && result.task_ids.length > 0) {
//            domain = [['id', 'in', result.task_ids], ['is_fsm', '=', true]];
//
//        } else {
//            // Fallback domain if no specific IDs
//            domain = [["user_ids", "!=", false], ['is_fsm', '=', true],["stage_id.name", '=', 'In Progress']];
//            // Add other filter params
//            if (params.start_date && params.end_date) {
//                domain.push(['create_date', '>=', params.start_date]);
//                domain.push(['create_date', '<=', params.end_date]);
//            }
//            if (params.company_id) domain.push(['company_id', '=', params.company_id]);
//            if (params.department_id) domain.push(['department_id', 'child_of', params.department_id]);
//            if (params.subdepartment_id) domain.push(['department_id', '=', params.subdepartment_id]);
//            if (params.state_id || params.city) {
//                const partner_domain = [];
//
//                if (params.state_id) {
//                    partner_domain.push(['state_id', '=', params.state_id]);
//                }
//                if (params.city && params.city !== '' && !(Array.isArray(params.city) && params.city.length === 0)) {
//                    partner_domain.push(['city', 'ilike', params.city]);
//                }
//
//                // Search partner_ids based on state and city
//                const partner_ids = await this.rpc('/web/dataset/call_kw', {
//                    model: 'res.partner',
//                    method: 'search',
//                    args: [partner_domain],
//                    kwargs: {}
//                });
//
//
//                if (partner_ids.length) {
//                    domain.push(['partner_id', 'in', partner_ids]);
//                } else {
//                    // Optional: handle no partners found
//                    alert("No partners found for the selected city/state.");
//                    return;
//                }
//            }
//        }
//
//        await this.action.doAction({
//            name: _t('Total Assigned Tasks'),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            views: [[false, 'list'], [false, 'form']],
//            domain: domain,
//            target: 'current'
//        });
//
//    } catch (error) {
//
//        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
//    }
//}

async in_progress_count_click(e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }

    try {
        const params = this.getFilterParams();
        const result = await this.rpc('/call/task/click', {
            task_type: 'in_progress',
            ...params
        });

        const domain = (result.task_ids && result.task_ids.length > 0)
            ? [['id', 'in', result.task_ids]]
            : [['id', '=', 0]];

        await this.action.doAction({
            name: _t('In Progress Calls'),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current'
        });

    } catch (error) {
        console.error("Error loading in-progress tasks:", error);
        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
    }
}


//async in_planned_count_click(e) {
//    if (e) {
//        e.stopPropagation();
//        e.preventDefault();
//    }
//    try {
//        const params = this.getFilterParams();
//        const result = await this.rpc('/previous/total', {
//            task_type: 'in_planned_count',
//            ...params
//        });
//        let domain;
//        if (result.task_ids && result.task_ids.length > 0) {
//            domain = [['id', 'in', result.task_ids], ['is_fsm', '=', true]];
//        } else {
//            // Fallback domain if no specific IDs
//            domain = [["user_ids", "!=", false], ['is_fsm', '=', true],["stage_id.name", '=', 'Planned']];
//            // Add other filter params
//            if (params.start_date && params.end_date) {
//                domain.push(['create_date', '>=', params.start_date]);
//                domain.push(['create_date', '<=', params.end_date]);
//            }
//            if (params.company_id) domain.push(['company_id', '=', params.company_id]);
//            if (params.department_id) domain.push(['department_id', 'child_of', params.department_id]);
//            if (params.subdepartment_id) domain.push(['department_id', '=', params.subdepartment_id]);
//            if (params.state_id || params.city) {
//                const partner_domain = [];
//
//                if (params.state_id) {
//                    partner_domain.push(['state_id', '=', params.state_id]);
//                }
//                if (params.city && params.city !== '' && !(Array.isArray(params.city) && params.city.length === 0)) {
//                    partner_domain.push(['city', 'ilike', params.city]);
//                }
//
//                // Search partner_ids based on state and city
//                const partner_ids = await this.rpc('/web/dataset/call_kw', {
//                    model: 'res.partner',
//                    method: 'search',
//                    args: [partner_domain],
//                    kwargs: {}
//                });
//
//
//                if (partner_ids.length) {
//                    domain.push(['partner_id', 'in', partner_ids]);
//                } else {
//                    // Optional: handle no partners found
//                    alert("No partners found for the selected city/state.");
//                    return;
//                }
//            }
//        }
//        await this.action.doAction({
//            name: _t('Total Assigned Tasks'),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            views: [[false, 'list'], [false, 'form']],
//            domain: domain,
//            target: 'current'
//        });
//    } catch (error) {
//        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
//    }
//}

async in_planned_count_click(e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }

    try {
        const params = this.getFilterParams();
        const result = await this.rpc('/call/task/click', {
            task_type: 'in_planned',
            ...params
        });

        const domain = (result.task_ids && result.task_ids.length > 0)
            ? [['id', 'in', result.task_ids]]
            : [['id', '=', 0]];  // fallback if no result

        await this.action.doAction({
            name: _t('Planned Tasks'),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current'
        });

    } catch (error) {
        console.error("Error loading planned tasks:", error);
        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
    }
}


//async in_resolved_count_click(e) {
//    if (e) {
//        e.stopPropagation();
//        e.preventDefault();
//    }
//    try {
//        const params = this.getFilterParams();
//        const result = await this.rpc('/previous/total', {
//            task_type: 'in_resolved_count',
//            ...params
//        });
//        let domain;
//        if (result.task_ids && result.task_ids.length > 0) {
//            domain = [['id', 'in', result.task_ids], ['is_fsm', '=', true]];
//        } else {
//            // Fallback domain if no specific IDs
//            domain = [["user_ids", "!=", false], ['is_fsm', '=', true],["stage_id.name", '=', 'Resolved']];
//            // Add other filter params
//            if (params.start_date && params.end_date) {
//                domain.push(['create_date', '>=', params.start_date]);
//                domain.push(['create_date', '<=', params.end_date]);
//            }
//            if (params.company_id) domain.push(['company_id', '=', params.company_id]);
//            if (params.department_id) domain.push(['department_id', 'child_of', params.department_id]);
//            if (params.subdepartment_id) domain.push(['department_id', '=', params.subdepartment_id]);
//            if (params.state_id || params.city) {
//                const partner_domain = [];
//
//                if (params.state_id) {
//                    partner_domain.push(['state_id', '=', params.state_id]);
//                }
//                if (params.city && params.city !== '' && !(Array.isArray(params.city) && params.city.length === 0)) {
//                    partner_domain.push(['city', 'ilike', params.city]);
//                }
//                // Search partner_ids based on state and city
//                const partner_ids = await this.rpc('/web/dataset/call_kw', {
//                    model: 'res.partner',
//                    method: 'search',
//                    args: [partner_domain],
//                    kwargs: {}
//                });
//
//
//                if (partner_ids.length) {
//                    domain.push(['partner_id', 'in', partner_ids]);
//                } else {
//                    // Optional: handle no partners found
//                    alert("No partners found for the selected city/state.");
//                    return;
//                }
//            }
//        }
//        await this.action.doAction({
//            name: _t('Total Assigned Tasks'),
//            type: 'ir.actions.act_window',
//            res_model: 'project.task',
//            views: [[false, 'list'], [false, 'form']],
//            domain: domain,
//            target: 'current'
//        });
//    } catch (error) {
//
//        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
//    }
//}

async in_resolved_count_click(e) {
    if (e) {
        e.stopPropagation();
        e.preventDefault();
    }

    try {
        const params = this.getFilterParams();
        const result = await this.rpc('/call/task/click', {
            task_type: 'in_resolved',
            ...params
        });

        const domain = (result.task_ids && result.task_ids.length > 0)
            ? [['id', 'in', result.task_ids]]
            : [['id', '=', 0]];  // fallback

        await this.action.doAction({
            name: _t('Resolved Tasks'),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            target: 'current'
        });

    } catch (error) {
        console.error("Error loading resolved tasks:", error);
        this.notification.add(_t("Error loading tasks"), { type: 'danger' });
    }
}


    // Update the updateTotals method
    async updateTotals() {
        try {
            const fromDate = document.querySelector('.from-date')?.value;
            const toDate = document.querySelector('.to-date')?.value;

            // Get all filter parameters
            const params = {
                ...this.getFilterParams(),  // Get company, department, subdepartment filters
                start_date: fromDate || null,
                end_date: toDate || null
            };

            const previousTotalsData = await this.rpc("/previous/total", params);

            // Fetch company settings again to ensure they're up to date
            const companyData = await this.rpc("/get/company/settings");
            console.log("Company Data", companyData)

            // Update all state properties
            Object.assign(this, {
                all_previous_tasks_total: previousTotalsData.all_previous_tasks_total || 0,
                all_assigned_tasks_total: previousTotalsData.all_assigned_tasks_total || 0,
                all_unassigned_tasks_total: previousTotalsData.all_unassigned_tasks_total || 0,
                all_on_hold_tasks_total: previousTotalsData.all_on_hold_tasks_total || 0,
                all_closed_tasks_total: previousTotalsData.all_closed_tasks_total || 0,
                in_progress_count: previousTotalsData.in_progress_count || 0,
                in_planned_count: previousTotalsData.in_planned_count || 0,
                in_resolved_count: previousTotalsData.in_resolved_count || 0,
                service_dashboard_planned_card: companyData.service_dashboard_planned_card,
                service_dashboard_resolved_card: companyData.service_dashboard_resolved_card,

//                Satyam
                service_dashboard_today_planned_card : companyData.service_dashboard_today_planned_card,
                service_dashboard_today_resolved_card : companyData.service_dashboard_today_resolved_card,

            });

            // Force a re-render to update the UI
            this.render();
        } catch (error) {
            console.error("Error updating totals:", error);
        }
    }

    // Add new method to load charts
    async loadCharts() {
        try {
            // Clear existing charts if they exist
            const tagChartCanvas = document.getElementById('task_tags_chart');
            const employeeChartCanvas = document.getElementById('employee_task_chart');

            const service_call_stages_chart = document.getElementById('task_stages_chart');

//            const service_call_customer_chart = document.getElementById('customer_tasks_chart');

//            const service_call_internal_external_chart = document.getElementById('chartElements');

            if (tagChartCanvas.__chart__) {
                tagChartCanvas.__chart__.destroy();
            }
            if (employeeChartCanvas.__chart__) {
                employeeChartCanvas.__chart__.destroy();
            }

             if (service_call_stages_chart.__chart__) {
                service_call_stages_chart.__chart__.destroy();
            }

//             if (service_call_customer_chart.__chart__) {
//                service_call_customer_chart.__chart__.destroy();
//            }

//             if (service_call_internal_external_chart.__chart__) {
//                service_call_internal_external_chart.__chart__.destroy();
//            }
            // Render both charts
            await this.render_task_tags_chart();
            await this.render_employee_task_chart();
            await this.render_task_stage_chart();
//            await this.render_customer_task_chart();
//            await this.render_internal_external_task_chart();
        } catch (error) {
            console.error("Error loading charts:", error);
        }
    }

    async onClickOpenTaskForm(ev) {
        try {
            // First get the Field Service project and user info
            const fsProject = await this.rpc("/get/fsm/project");
            console.log(fsProject)
            // Open a new task form with default project and user
            await this.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'project.task',
                views: [[false, 'form']],
                target: 'new',
                context: {
                    'form_view_initial_mode': 'edit',
                    'default_is_fsm': true,
                    'default_project_id': fsProject.id,  // Set default project
                    'default_user_ids': [[6, 0, [fsProject.user_id]]], // Set default user
                },
            });
        } catch (error) {
            console.error("Error opening new task form:", error);
            this.notification.add(
                "Error opening task form",
                { type: 'danger' }
            );
        }
    }

    async refreshPage() {
    // Show success message
//        this.notification.add(
//            "Dashboard refreshed successfully",
//            { type: 'success' }
//        );
       window.location.reload();
    }

    // Navigation methods for app buttons
    openServiceDashboard() {
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'service_call_dashboard',
            target: 'current'
        });
        this.toggleMainSidebar();
    }

    openCalendar() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'calendar.event',
            views: [[false, 'calendar'], [false, 'form']],
            target: 'current'
        });
        this.toggleMainSidebar();
    }

    openEmployees() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            views: [[false, 'kanban'], [false, 'form']],
            target: 'current'
        });
        this.toggleMainSidebar();
    }

    openSettings() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'res.config.settings',
            views: [[false, 'form']],
            target: 'current'
        });
        this.toggleMainSidebar();
    }

    async loadCompanies() {
        try {
            const companies = await this.rpc("/get/service_companies");
            this.state.companies = companies;
        } catch (error) {
            console.error("Error loading companies:", error);
            this.notification.add(
                "Error loading companies",
                { type: 'danger' }
            );
        }
    }

    // Navigation methods
    showCompanies() {
        this.state.currentView = 'companies';
        this.state.selectedCompany = null;
        this.state.selectedDepartment = null;
        this.state.selectedSubDepartment = null;
        this.state.selectedState = null;
        this.state.selectedCity = null;
        this.state.departments = [];
        this.state.subdepartments = [];
        this.state.states = [];
        this.state.cities = [];
    }

    showDepartments() {
        this.state.currentView = 'departments';
        this.state.selectedDepartment = null;
        this.state.selectedSubDepartment = null;
        this.state.selectedState = null;
        this.state.selectedCity = null;
        this.state.subdepartments = [];
        this.state.states = [];
        this.state.cities = [];
    }

    async toggleCompany(company) {
        try {
            // Toggle company selection
            if (this.state.selectedCompany?.id === company.id) {
                this.state.selectedCompany = null;
            } else {
                this.state.selectedCompany = company;
            }
            // Reset other selections
            this.state.selectedDepartment = null;
            this.state.selectedSubDepartment = null;
            this.state.selectedState = null;
            this.state.selectedCity = null;
            this.state.departments = [];
            this.state.subdepartments = [];
            this.state.states = [];
            this.state.cities = [];
            // If a company is selected, fetch its departments
            if (this.state.selectedCompany) {
                this.state.departments = await this.rpc('/get/service_departments/by_company', {
                    company_id: this.state.selectedCompany.id
                });
            }

            // Update team stats if filter is active
            if (this.state.filterActive) {
                await this.updateTeamStats();
            }

            this.render();
        } catch (error) {
            console.error('Error toggling company:', error);
        }
    }

    async toggleDepartment(department) {
        try {
            if (this.state.selectedDepartment?.id === department.id) {
                // Collapse the department selection
                this.state.selectedDepartment = null;
                this.state.selectedSubDepartment = null;
                this.state.selectedState = null;
                this.state.selectedCity = null;
                this.state.subdepartments = [];
                this.state.states = [];
                this.state.cities = [];
                this.state.teamStats = {
                    total_team: 0,
                    free_team: 0,
                    running_overdue: 0,
                    occupied: 0,
                    on_leave: 0
                };
                this.state.filterActive = false;
            } else {
                // Load sub-departments for the selected department
                this.state.selectedDepartment = department;
                this.state.selectedSubDepartment = null;
                this.state.selectedState = null;
                this.state.selectedCity = null;
                this.state.states = [];
                this.state.cities = [];
                this.state.filterActive = false;

                const subdepartments = await this.rpc("/get/service_sub_departments", {
                    department_id: department.id
                });
                this.state.subdepartments = subdepartments;
            }
        } catch (error) {
            console.error("Error toggling department:", error);
        }
    }

    async selectSubDepartment(subdepartment) {
        try {
            if (this.state.selectedSubDepartment?.id === subdepartment.id) {
                this.state.selectedSubDepartment = null;
                this.state.selectedState = null;
                this.state.selectedCity = null;
                this.state.states = [];
                this.state.cities = [];
            } else {
                this.state.selectedSubDepartment = subdepartment;
                this.state.selectedState = null;
                this.state.selectedCity = null;
                this.state.cities = [];

                const states = await this.rpc('/get/states/by_subdepartment', {
                    subdepartment_id: subdepartment.id,
                });
                this.state.states = states;
            }
        this.render();

        } catch (error) {
            console.error("Error selecting subdepartment:", error);
        }
    }

    async selectState(stateItem) {
        try {
            if (this.state.selectedState?.id === stateItem.id){
                this.state.selectedState = null;
                this.state.selectedCity = null;
//                this.state.filterActive = false;
                this.state.cities = [];
                }
            else{
                this.state.selectedState = stateItem;
                this.state.selectedCity = null;
                this.state.cities = await this.rpc('/get/cities/by_state', {
                    subdepartment_id: this.state.selectedSubDepartment.id,
                    state_id: stateItem.id
                });
            }
        } catch (error) {
            console.error("Error selecting state:", error);
        }
    }

    async selectCity(cityItem) {
        try {
            this.state.selectedCity = cityItem;
            this.state.filterActive = false;
        } catch (error) {
            console.error("Error selecting city:", error);
        }
    }

//    async handleTeamClick(e) {
//        e.stopPropagation();
//        e.preventDefault();
//        if (!this.state.teamStats || this.state.teamStats.total_team === 0) {
//            return; // Do nothing if no team
//        }
//        const params = this.getTeamFilterParams();
//        const domain = await this.TeambuildDomain(params, 'employee');
//        console.log("Now inside the click event")
//        this.action.doAction({
//            name: _t("Team Members"),
//            type: 'ir.actions.act_window',
//            res_model: 'hr.employee',
//            domain: domain,
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current'
//        });
//        console.log("Demo", domain)
//    }

async handleTeamClick(e) {
    e.stopPropagation();
    e.preventDefault();

    if (!this.state.teamStats || this.state.teamStats.total_team === 0) {
        return;
    }

    const params = this.getTeamFilterParams();

    // Fetch all employees matching filter
    const result = await this.rpc('/call/employee/click', {
        employee_type: 'total',
        ...params,
    });

    const employeeIds = result.employee_ids || [];
    console.log("Team click", employeeIds)
    if (!employeeIds.length) {
        this.notification.add(_t("No employees found."), { type: 'warning' });
        return;
    }

    const domain = [['id', 'in', employeeIds]];
    console.log("Team Domain:", domain);

    this.action.doAction({
        name: _t("Team Members"),
        type: 'ir.actions.act_window',
        res_model: 'hr.employee',
        domain: domain,
        views: [
            [false, 'list'],
            [false, 'form'],
            [false, 'kanban']
        ],
        target: 'current',
        context: {
            search_default_current_company: false,
            force_company: false,
        }
    });
}


//    async handleFreeClick(e) {
//        e.stopPropagation();
//        e.preventDefault();
//
//        if (!this.state.teamStats || this.state.teamStats.free_team === 0) {
//            return; // Do nothing if no free team
//        }
//
//        const params = this.getTeamFilterParams();
//        const domain = await this.TeambuildDomain(params, 'employee');
//
//        // Step 1: Get user_ids from tasks assigned to filtered employees (occupied ones)
//        const taskUserIds = await this.orm.searchRead('project.task', [
//            ['is_fsm', '=', true],
//            ['user_ids', '!=', false]
//        ], ['user_ids']);
//
//        const userIds = [...new Set(taskUserIds.map(t => t.user_ids[0]))]; // Unique user_ids
//
//        // Step 2: Get employee_ids linked to those user_ids (occupied employees)
//        const userRecords = await this.orm.searchRead('res.users', [
//            ['id', 'in', userIds],
//            ['employee_id', '!=', false]
//        ], ['employee_id']);
//
////        const occupiedEmployeeIds = [...new Set(userRecords.map(u => u.employee_id[0]))];
//	  const employeeIds = [...new Set(userRecords.map(u => u.employee_id?.[0]))].filter(id => typeof id === 'number');
//
//        if (employeeIds.length > 0) {
//            domain.push(['id', 'not in', employeeIds]); // Exclude occupied employees
//        }
//
//        console.log("Free team domain:", domain);
//
//        this.action.doAction({
//            name: _t("Free Team Employees"),
//            type: 'ir.actions.act_window',
//            res_model: 'hr.employee',
//            domain: domain,
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current'
//        });
//    }

async handleFreeClick(e) {
    e.stopPropagation();
    e.preventDefault();

    if (!this.state.teamStats || this.state.teamStats.free_team === 0) {
        return;
    }

    const params = this.getTeamFilterParams();

    // Fetch filtered free employee_ids from controller
    const result = await this.rpc('/call/employee/click', {
        employee_type: 'free',
        ...params,
    });

    const employeeIds = result.employee_ids || [];
    if (!employeeIds.length) {
        this.notification.add(_t("No free employees found."), { type: 'warning' });
        return;
    }

    const domain = [['id', 'in', employeeIds]];
    console.log("Free Employee Domain:", domain);

    this.action.doAction({
        name: _t("Free Team Employees"),
        type: 'ir.actions.act_window',
        res_model: 'hr.employee',
        domain: domain,
        views: [
            [false, 'list'],
            [false, 'form'],
            [false, 'kanban']
        ],
        target: 'current'
    });
}


//    async handleOverdueClick(e) {
//        e.stopPropagation();
//        e.preventDefault();
//        if (!this.state.teamStats || this.state.teamStats.running_overdue === 0) {
//            return; // Do nothing if no team
//        }
//        const params = this.getTeamFilterParams();
//        const domain = await this.TeambuildDomain(params, 'employee');
//        const today = new Date().toISOString().split('T')[0];
//
//        const taskUserIds = await this.orm.searchRead('project.task', [
//            ['date_deadline', '<', today],
//            ['stage_id.name', 'not in', ['Done', 'Cancelled']],
//            ['user_ids', '!=', false]
//        ], ['user_ids']);
//
//        const userIds = [...new Set(taskUserIds.map(t => t.user_ids[0]))]; // Unique user_ids
//        console.log("User Ids for Overdue Click", userIds)
//        // Step 2: Get employee_ids linked to those user_ids
//        const userRecords = await this.orm.searchRead('res.users', [
//            ['id', 'in', userIds],
//            ['employee_id', '!=', false]
//        ], ['employee_id']);
//        console.log("User Records". userRecords)
//        const employeeIds = [...new Set(userRecords.map(u => u.employee_id[0]))].filter(id => typeof id === 'number');
//
//        console.log("Employee Ids", employeeIds)
//
//        if (!employeeIds.length) {
//            this.doNotify('No employees found for overdue tasks');
//            return;
//        }
//        domain.push(['id', 'in', employeeIds]);
//        this.action.doAction({
//        name: _t("Employees with Overdue Tasks"),
//        type: 'ir.actions.act_window',
//        res_model: 'hr.employee',
//        domain: domain,
//        views: [
//            [false, 'list'],
//            [false, 'form'],
//            [false, 'kanban']
//        ],
//        target: 'current'
//    });
//}

    async handleOverdueClick(e) {
        e.stopPropagation();
        e.preventDefault();
        if (!this.state.teamStats || this.state.teamStats.running_overdue === 0) {
            return; // Do nothing if no overdue tasks
        }
        const params = this.getTeamFilterParams();

        const result = await this.rpc('/call/employee/click', {
            employee_type: 'running_overdue',
            ...params,
        });

        const employeeIds = result.employee_ids || [];
        const employees = await this.orm.read('hr.employee', employeeIds, ['user_id']);
        const userIds = employees
            .map(emp => emp.user_id?.[0])
            .filter(uid => !!uid);


        console.log("OVerdue", employeeIds)
        const today = new Date().toISOString().split('T')[0];
        const domain = [
            ['is_fsm', '=', true],
            ['date_deadline', '<', today],
            ['stage_id.name', 'not in', ['Done', 'Cancelled']],
            ['user_ids', 'in', userIds],
        ];

        this.action.doAction({
            name: _t("Overdue Tasks"),
            type: 'ir.actions.act_window',
            res_model: 'project.task',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'kanban'],
                [false, 'form']
            ],
            target: 'current',
            context: {
                group_by: 'user_ids',
            },
        });
    }
async handleOccupiedClick(e) {
    e.stopPropagation();
    e.preventDefault();
    console.log("inside the occupied");

    const params = this.getTeamFilterParams();
    console.log("my params", params);

    const result = await this.rpc('/call/employee/click', {
        employee_type: 'occupied',
        ...params,
    });
    const employeeIds = result.employee_ids || [];
    if (employeeIds.length === 0) {
        this.notification.add("No employees with running timers found.", { type: 'warning' });
        return;
    }
    // Get user_ids of those employees
    const employees = await this.orm.read('hr.employee', employeeIds, ['user_id']);
    const userIds = employees
        .map(emp => emp.user_id?.[0])
        .filter(uid => !!uid); // Remove nulls

    if (userIds.length === 0) {
        this.notification.add("No users found for employees with running timers.", { type: 'warning' });
        return;
    }

    // Domain to find timesheet entries with running timers
    const timesheetDomain = [
        ['user_id', 'in', userIds],
        ['is_fsm', '=', true],
        ['is_timer_running', '=', true], // Only timesheets with running timers
    ];

    const timesheetCount = await this.orm.searchCount('account.analytic.line', timesheetDomain);
    if (timesheetCount === 0) {
        this.notification.add("No running timers found for employees.", { type: 'info' });
        return;
    }

    // Get the timesheet entries to find related tasks
    const timesheetEntries = await this.orm.searchRead('account.analytic.line', timesheetDomain, ['task_id']);
    // Get view ID using searchRead instead of private method
    const modelDataRecords = await this.orm.searchRead('ir.model.data', [
        ['name', '=', 'view_task_tree_service_call_timer'],
        ['module', '=', 'service_call_dashboard_odoo']
    ], ['res_id']);

    const viewId = modelDataRecords.length > 0 ? modelDataRecords[0].res_id : false;

    const taskIds = timesheetEntries
        .map(entry => entry.task_id?.[0])
        .filter(taskId => !!taskId); // Remove nulls

    if (taskIds.length === 0) {
        this.notification.add("No tasks found for running timers.", { type: 'info' });
        return;
    }

    // Domain to find tasks with running timers
    const taskDomain = [
        ['id', 'in', taskIds],
        ['is_fsm', '=', true],
    ];

    // Open project.task list view grouped by user
    this.action.doAction({
        name: "Occupied Employees - Tasks (Timer Running)",
        type: 'ir.actions.act_window',
        res_model: 'project.task',
        domain: taskDomain,
        views: [
            [viewId, 'list'],
            [false, 'kanban'],
            [false, 'form']
        ],
        target: 'current',
        context: {
            group_by: 'user_ids',
        },
    });
}
// New method to stop and delete all running timers
async handleStopAndDeleteTimers(e) {
    e.stopPropagation();
    e.preventDefault();

    const params = this.getTeamFilterParams();

    const result = await this.rpc('/call/employee/click', {
        employee_type: 'stop_and_delete',
        ...params,
    });

    if (result.deleted_count > 0) {
        this.notification.add(result.message, { type: 'success' });
    } else {
        this.notification.add(result.message, { type: 'info' });
    }

    // Refresh the view to update the occupied count
    this.trigger('reload');
}
//async handleOccupiedClick(e) {
//    e.stopPropagation();
//    e.preventDefault();
//    console.log("inside the occupied");
//
//    const params = this.getTeamFilterParams();
//    console.log("my params", params);
//
//    const result = await this.rpc('/call/employee/click', {
//        employee_type: 'occupied',
//        ...params,
//    });
//    const employeeIds = result.employee_ids || [];
////    if (employeeIds.length === 0) {
////        this.notification.add(_t("No occupied employees found."), { type: 'warning' });
////        return;
////    }
//
//    // Step 1: Get user_ids of those employees
//    const employees = await this.orm.read('hr.employee', employeeIds, ['user_id']);
//    const userIds = employees
//        .map(emp => emp.user_id?.[0])
//        .filter(uid => !!uid); // Remove nulls
////    const domain = result.domain || [];
////    console.log("Domain occc", domain)
////    const taskCount = await this.orm.searchCount('project.task', domain);
////    if (taskCount === 0) return;
//    const domain = [
//        ['user_ids', 'in', userIds],
//        ['is_fsm', '=', true],
//        ['stage_id.name', 'not in', ['Done', 'Cancelled']],
//    ];
//
//    const taskCount = await this.orm.searchCount('project.task', domain);
//    if (taskCount === 0) return;
//
//    this.action.doAction({
//        name: _t("Occupied Employees"),
//        type: 'ir.actions.act_window',
//        res_model: 'project.task',
//        domain: domain,
//        views: [
//            [false, 'list'],
//            [false, 'kanban'],
//            [false, 'form']
//        ],
//        target: 'current',
//        context: {
//            group_by: 'user_ids',
//        },
//    });
//}

async handleOnLeaveClick(e) {
    e.stopPropagation();
    e.preventDefault();

    try {
        const params = this.getTeamFilterParams();

        const result = await this.rpc('/call/employee/click', {
            employee_type: 'on_leave',
            ...params,
        });

        const domain = (result.employee_ids && result.employee_ids.length > 0)
            ? [['id', 'in', result.employee_ids]]
            : [['id', '=', 0]];
        console.log("Leave Domain",domain)
        await this.action.doAction({
            name: _t("Team Members on Leave"),
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            domain: domain,
            views: [
                [false, 'list'],
                [false, 'form'],
                [false, 'kanban']
            ],
            target: 'current'
        });
    } catch (error) {
        console.error("Failed to load on-leave employees:", error);
        this.notification.add(_t("Could not fetch leave data."), { type: 'danger' });
    }
}


//    async handleOnLeaveClick(e) {
//        e.stopPropagation();
//        e.preventDefault();
//        if (!this.state.teamStats || this.state.teamStats.on_leave === 0) {
//            return; // Do nothing if no team
//        }
//        const params = this.getTeamFilterParams();
//        const domain = await this.TeambuildDomain(params, 'employee');
//        // Add condition for employees on leave
//        domain.push(['is_absent', '=', true]);
//        this.action.doAction({
//            name: _t("Team Members on Leave"),
//            type: 'ir.actions.act_window',
//            res_model: 'hr.employee',
//            domain: domain,
//            views: [
//                [false, 'list'],
//                [false, 'form'],
//                [false, 'kanban']
//            ],
//            target: 'current'
//        });
//    }

     //    new added code 22 apr
     // Helper method to get current filter parameters
    getTeamFilterParams() {
        const fromDate = document.querySelector('.from-date')?.value;
        const toDate = document.querySelector('.to-date')?.value;

        return {
            company_id: this.state.selectedCompany?.id || null,
            department_id: this.state.selectedDepartment?.id || null,
            subdepartment_id: this.state.selectedSubDepartment?.id || null,
            start_date: fromDate || null,
            end_date: toDate || null
        };
    }

    // Helper method to build domain from params
    buildDomain(params, modelType = 'employee') {
        const domain = [];
        if (params.company_id) {
            domain.push(['company_id', '=', parseInt(params.company_id)]);

            const serviceDept = this.state.departments.find(dep => dep.name === 'Service Division');
            if (serviceDept) {
                domain.push(['department_id', 'child_of', parseInt(serviceDept.id)]);
            }
        }
        if (modelType === 'employee') {
            // For employee model
            if (params.subdepartment_id) {
                domain.push(['department_id', '=', parseInt(params.subdepartment_id)]);
            }
            // If only department is selected (no subdepartment), include department + subdepartments
            else if (params.department_id) {
                domain.push(['department_id', 'child_of', parseInt(params.department_id)]);
            }

            if (params.state_id) {
                domain.push(['state_id', '=', parseInt(params.state_id)]);
            }
            if (params.city) {
                domain.push(['city', 'ilike', params.city]);
            }
        }
        else if (modelType === 'task') {
            // For task model
            domain.push(['is_fsm', '=', true]);
            if (params.subdepartment_id) {
                domain.push(['department_id', '=', parseInt(params.subdepartment_id)]);
            } else if (params.department_id) {
                domain.push(['department_id', 'child_of', parseInt(params.department_id)]);
            }
            if (params.state_id) {
                domain.push(['partner_id.state_id', '=', parseInt(params.state_id)]);
            }
            if (params.city) {
                domain.push(['partner_id.city', 'ilike', params.city]);
            }
        }
        return domain;
    }


    async TeambuildDomain(params, modelType = 'employee') {
        const domain = [];

        if (params.company_id) {
            domain.push(['company_id', '=', parseInt(params.company_id)]);
        }
        let serviceDeptId = null;
        try {
            const serviceDepts = await this.rpc('/web/dataset/call_kw', {
                model: 'hr.department',
                method: 'search_read',
                args: [[['name', '=', 'Service Division']]],
                kwargs: { fields: ['id'], limit: 1 },
            });
            console.log("Default Departments", serviceDepts)

            if (serviceDepts.length) {
                serviceDeptId = serviceDepts[0].id;
                console.log("Hioooo",serviceDeptId)
            }
            console.log("Model Type", serviceDeptId)
                // Core logic
            if (modelType === 'employee') {
                if (params.subdepartment_id) {
                    // Specific subdepartment selected â€” restrict strictly to it
                    domain.push(['department_id', '=', parseInt(params.subdepartment_id)]);
                } else if (params.department_id) {
                    // Department selected â€” include it and its subdepartments
                    domain.push(['department_id', 'child_of', parseInt(params.department_id)]);
                } else if (serviceDeptId) {
                    console.log("This is testing", serviceDeptId)
                    domain.push(['department_id', 'child_of', serviceDeptId]);
                    console.log("Domain", domain)
                }
            } else if (modelType === 'task') {
                domain.push(['is_fsm', '=', true]);

                if (params.subdepartment_id) {

                    domain.push(['department_id', '=', parseInt(params.subdepartment_id)]);
                } else if (params.department_id) {

                    domain.push(['department_id', 'child_of', parseInt(params.department_id)]);
                } else if (serviceDeptId) {
                    console.log("Hello I am hereeeee")
                    domain.push(['department_id', 'child_of', serviceDeptId]);
                }
            }
            console.log("I am Here", domain)
        } catch (error) {
            console.error("Failed to fetch Service Division:", error);
        }

        return domain;
    }

    async updateTeamStats() {
        try {
            const params = this.getFilterParams();
            // Get team stats
            const teamStats = await this.rpc('/get/team/stats', params);
            this.state.teamStats = teamStats;

            // Force component to re-render
            this.render();
        } catch (error) {
            console.error('Error updating team stats:', error);
        }
    }

    async applyDepartmentFilter() {
        try {
            this.state.isApplyingFilter = true;
            // Set filter active state
            this.state.filterActive = true;

            // Get all filter parameters
            const params = this.getFilterParams();

            // Update tiles data with all filters
            await this.updateCallsToday();
            await this.updateTeamStats();
            await this.updatePreviousTotal();
            this.notification.add("Filters Applied successfully", {
                type: 'success',
            });
            this.saveFiltersToStorage();

            // Update charts with new filter parameters
            await this.loadCharts();

            // Force a re-render to update the UI
//            this.render();
        } catch (error) {
            console.error("Error applying filters:", error);
            this.notification.add(_t("Error updating dashboard data"), {
                type: 'danger',
                sticky: true,
                title: _t("Error")
            });
        }
        finally {
            this.state.isApplyingFilter = false; // hide loader
    }
   }

    async updatePreviousTotal() {
        try {
            const params = this.getFilterParams();
            const previousTotalsData = await this.rpc("/previous/total", params);

            // Update all state properties
            Object.assign(this, {
                all_previous_tasks_total: previousTotalsData.all_previous_tasks_total || 0,
                all_assigned_tasks_total: previousTotalsData.all_assigned_tasks_total || 0,
                all_unassigned_tasks_total: previousTotalsData.all_unassigned_tasks_total || 0,
                all_on_hold_tasks_total: previousTotalsData.all_on_hold_tasks_total || 0,
                all_closed_tasks_total: previousTotalsData.all_closed_tasks_total || 0,
                in_progress_count: previousTotalsData.in_progress_count || 0,
                in_planned_count: previousTotalsData.in_planned_count || 0,
                in_resolved_count: previousTotalsData.in_resolved_count || 0
            });
        } catch (error) {
            console.error("Error updating previous totals:", error);
            throw error;
        }
    }

    async clearDepartmentFilter() {
        try {
            this.state.isClearingFilter = true; // show loader

            this.state.filterActive = false;
            this.state.selectedCompany = null;
            this.state.selectedDepartment = null;
            this.state.selectedSubDepartment = null;
            this.state.selectedState = null;
            this.state.selectedCity = null;
            this.state.selectedCities = [];
            this.state.startDate = null;
            this.state.endDate = null;

//            const fromDateInput = document.querySelector('.from-date');
//            const toDateInput = document.querySelector('.to-date');
//            if (fromDateInput) fromDateInput.value = '';
//            if (toDateInput) toDateInput.value = '';
                    // Calculate date range: fromDate = today - 1 month, toDate = today
            const today = new Date();
            const pastMonth = new Date();
            pastMonth.setMonth(today.getMonth() - 1);

            // Format to yyyy-mm-dd
            const formatDate = (date) => date.toISOString().split('T')[0];
            const fromDateStr = formatDate(pastMonth);
            const toDateStr = formatDate(today);

            // Set dates to state
            this.state.startDate = fromDateStr;
            this.state.endDate = toDateStr;

            // Set values in input fields
            const fromDateInput = document.querySelector('.from-date');
            const toDateInput = document.querySelector('.to-date');
            if (fromDateInput) fromDateInput.value = fromDateStr;
            if (toDateInput) toDateInput.value = toDateStr;
                localStorage.removeItem('serviceDashboardFilters');

            await this.updateCallsToday();
            await this.updateTeamStats();
            await this.updateTotals();
            await this.loadCharts();

            this.notification.add("Filters cleared successfully", { type: 'success' });

        } catch (error) {
            console.error("Error clearing department filter:", error);
            this.notification.add("Error updating dashboard data", { type: 'danger' });
        } finally {
            this.state.isClearingFilter = false; // hide loader
        }
    }


    async show_team_members(e) {
        e.stopPropagation();
        e.preventDefault();

        try {
            // Get employee data
            const employees = await this.rpc("/get/team_members", {
                company_id: this.state.selectedCompany?.id,
                department_id: this.state.selectedDepartment?.id,
                subdepartment_id: this.state.selectedSubDepartment?.id
            });
            console.log("Team members:", employees);
            if (employees && employees.length > 0) {
                // Open the employee list view
                this.action.doAction({
                    name: _t("Service Division Team Members"),
                    type: 'ir.actions.act_window',
                    res_model: 'hr.employee',
                    domain: [['id', 'in', employees.map(emp => emp.id)]],
                    views: [[false, 'kanban'], [false, 'list'], [false, 'form']],
                    target: 'current',
                    context: {
                        'default_company_id': this.state.selectedCompany?.id,
                        'default_department_id': this.state.selectedDepartment?.id
                    }
                });
            } else {
                this.notification.add(_t("No team members found"), {
                    type: 'warning'
                });
            }
        } catch (error) {
            console.error("Error showing team members:", error);
            this.notification.add(_t("Error loading team members"), {
                type: 'danger'
            });
        }
    }

    async updateCallsToday() {
        try {
            const params = this.getFilterParams();
            const result = await this.rpc('/call/today', params);


            // Update state with the received values
            this.state.total_stage_tasks_today = result.total_stage_tasks_today || 0;
            this.state.new_stage_tasks_today = result.new_stage_tasks_today || 0;
            this.state.calls_assigned_today = result.calls_assigned_today || 0;
            this.state.calls_unassigned_today = result.calls_unassigned_today || 0;
            this.state.calls_on_hold_today = result.calls_on_hold_today || 0;
            this.state.calls_closed_today = result.calls_closed_today || 0;

//            Satyam
            this.state.planned_today_tasks = result.planned_today_tasks || 0;
            this.state.resolved_today_tasks = result.resolved_today_tasks || 0;
        } catch (error) {
            console.error('Error updating calls today:', error);
        }
    }
}
ServiceProjectDashboard.template = "service_call_dashboard_odoo.ServiceProjectDashboard";
registry.category("actions").add("service_call_dashboard", ServiceProjectDashboard);



