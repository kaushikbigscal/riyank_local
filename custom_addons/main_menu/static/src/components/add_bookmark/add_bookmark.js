/** @odoo-module **/

import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class addBookmark extends Component {
    static template = "main_menu.AddBookmark";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.rpc = useService("rpc");
    }

    async addBookmark() {
        await this.rpc("/main_menu/bookmark/add", {bookmark: {name: window.document.title, url: window.location.href}});
    }
}

registry.category("cogMenu").add("add-bookmark", { Component: addBookmark }, { sequence: 1 });
