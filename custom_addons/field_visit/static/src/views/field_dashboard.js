/** @odoo-module */
import { useService } from "@web/core/utils/hooks";

const { Component, onWillStart } = owl;

export class FieldVisitDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        onWillStart(async () => {
            const context = this.env.searchModel?.context || {};
            console.log(context);
            if (context.show_dashboard) {
                this.visitData = await this.orm.call(
                    "field.visit",
                    "retrieve_dashboard",
                );
                this.showDashboard = true;
            } else {
                this.showDashboard = false;
            }
        });
    }

    /**
     * This method clears the current search query and activates
     * the filters found in `filter_name` attibute from button pressed
     */
    setSearchContext(ev) {
        let filter_name = ev.currentTarget.getAttribute("filter_name");
        let filters = filter_name.split(',');
        let searchItems = this.env.searchModel.getSearchItems((item) => filters.includes(item.name));
        this.env.searchModel.query = [];
        for (const item of searchItems){
            this.env.searchModel.toggleSearchItem(item.id);
        }
    }
}

FieldVisitDashboard.template = 'field_visit.FieldVisitDashboard'
