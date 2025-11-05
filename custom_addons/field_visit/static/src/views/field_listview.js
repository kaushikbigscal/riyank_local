/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";
import { FieldVisitDashboard } from '@field_visit/views/field_dashboard';

export class FieldVisitDashboardRenderer extends ListRenderer {};

FieldVisitDashboardRenderer.template = 'field_visit.FieldVisitListView';
FieldVisitDashboardRenderer.components= Object.assign({}, ListRenderer.components, {FieldVisitDashboard})

export const FieldVisitListDashboard = {
    ...listView,
    Renderer: FieldVisitDashboardRenderer,
};

registry.category("views").add("field_dashboard_list", FieldVisitListDashboard);

