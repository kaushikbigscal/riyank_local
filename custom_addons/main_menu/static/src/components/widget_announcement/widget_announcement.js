/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class WidgetAnnouncement extends Component {
    static props = {
        userIsAdmin: Boolean,
        announcement: String,
    };
    static template = "main_menu.WidgetAnnouncement";

    setup(){
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.company = useService("company").currentCompany.id
        this.state = useState({
            announcement: this.props.announcement,
        });
    }

    onInputAnnouncement(e) {
        this.state.announcement = e.target.value;
    }

    async onSaveAnnouncement(){
        try {
            await this.rpc("/main_menu/announcement/save", {
                company_id: this.company,
                data: { announcement: this.state.announcement }
            });
            this.notification.add(_t("Announcement saved."), { type: "success" });
        } catch (error){
            console.error("Error saving data:", error);
            this.notification.add(_t("The announcement could not be saved. Please try again."), { type: "danger" });
        }
    }
}
