/** @odoo-module */
import { registry } from '@web/core/registry';
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState } = owl;
import { jsonrpc } from "@web/core/network/rpc_service";

export class ServiceSummaryDashboard extends Component {
    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
        this.rpc = this.env.services.rpc;

        this.state = useState({
            companies: [],
            departmentsByCompany: {}, // Store departments by company ID
            expandedCompanyId: null,
            sidebarOpen: false  // Start with sidebar closed
        });

        onWillStart(this.onWillStart);
    }

    async onWillStart() {
        await this.loadCompanies();
    }

    async loadCompanies() {
        try {
            const companies = await jsonrpc("/get/companies");
            this.state.companies = companies;
        } catch (error) {
            console.error("Error loading companies:", error);
            this.state.companies = [];
        }
    }

    async toggleCompany(companyId) {
        // If already expanded, collapse it
        if (this.state.expandedCompanyId === companyId) {
            this.state.expandedCompanyId = null;
            return;
        }

        // Expand the company and load its departments
        this.state.expandedCompanyId = companyId;

        // Only load departments if we haven't loaded them before
        if (!this.state.departmentsByCompany[companyId]) {
            await this.loadDepartments(companyId);
        }
    }

    async loadDepartments(companyId) {
        try {
            const departments = await jsonrpc("/get/departments/by_company", {
                company_id: companyId
            });

            // Update the departments for this company
            this.state.departmentsByCompany[companyId] = departments;
        } catch (error) {
            console.error("Error loading departments:", error);
            this.state.departmentsByCompany[companyId] = [];
        }
    }

    async onDepartmentClick(deptId) {
        // Navigate to project dashboard with department filter
        this.action.doAction({
            type: 'ir.actions.client',
            tag: 'project_dashboard',
            params: {
                department_id: deptId
            }
        });
    }

    // Toggle sidebar
    toggleSidebar() {
        this.state.sidebarOpen = !this.state.sidebarOpen;
    }

    // Check if a company is expanded
    isCompanyExpanded(companyId) {
        return this.state.expandedCompanyId === companyId;
    }

    // Get departments for a company
    getDepartmentsForCompany(companyId) {
        return this.state.departmentsByCompany[companyId] || [];
    }
}

ServiceSummaryDashboard.template = "ServiceSummaryDashboard";
registry.category("actions").add("ServiceSummaryDashboard", ServiceSummaryDashboard);

//import { registry } from '@web/core/registry';
//import { useService } from "@web/core/utils/hooks";
//const { Component, onWillStart, useState } = owl;
//import { jsonrpc } from "@web/core/network/rpc_service";
//
//export class SummaryDashboard extends Component {
//    setup() {
//        super.setup();
//        this.action = useService("action");
//        this.orm = useService("orm");
//        this.rpc = this.env.services.rpc;
//
//        this.state = useState({
//            companies: [],
//            departments: [],
//            selectedCompany: null
//        });
//
//        onWillStart(this.onWillStart);
//    }
//
//    async onWillStart() {
//        await this.loadCompanies();
//    }
//
//    async loadCompanies() {
//        try {
//            const companies = await jsonrpc("/get/companies");
//            this.state.companies = companies;
//        } catch (error) {
//            console.error("Error loading companies:", error);
//            this.state.companies = [];
//        }
//    }
//
//    async onCompanyClick(companyId) {
//        this.state.selectedCompany = companyId;
//        await this.loadDepartments(companyId);
//    }
//
//    async loadDepartments(companyId) {
//        try {
//            const departments = await jsonrpc("/get/departments/by_company", {
//                company_id: companyId
//            });
//            this.state.departments = departments;
//        } catch (error) {
//            console.error("Error loading departments:", error);
//            this.state.departments = [];
//        }
//    }
//
//    async onDepartmentClick(deptId) {
//        // Navigate to project dashboard with department filter
//        this.action.doAction({
//            type: 'ir.actions.client',
//            tag: 'project_dashboard',
//            params: {
//                department_id: deptId
//            }
//        });
//    }
//}
//
//SummaryDashboard.template = "SummaryDashboard";
//registry.category("actions").add("summary_dashboard", SummaryDashboard);