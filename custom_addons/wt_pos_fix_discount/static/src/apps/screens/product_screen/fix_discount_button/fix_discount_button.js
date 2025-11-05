/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { useService } from "@web/core/utils/hooks";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class SetFixDiscountButton extends Component {
    static template = "wt_pos_fix_discount.SetFixDiscountButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
    }

    async click() {
        const order = this.pos.get_order();
        if (!order) {
            return;
        }
        const { confirmed, payload } = await this.popup.add(NumberPopup, {
            title: _t("Discount Fixed"),
            startingValue: 0,
            isInputSelected: true,
        });
        if (confirmed) {
            const val = parseFloat(payload);
            const orderlines = order.get_orderlines();
            const totalQuantity = orderlines.reduce((sum, line) => sum + line.get_quantity(), 0);
            const discountPerLine = (val / totalQuantity) || 0;

            orderlines.forEach(line => {
                if (line.set_fix_discount) {
                    line.set_fix_discount(discountPerLine * line.get_quantity());
                } else {
                    console.error("set_fix_discount is not a function on line:", line);
                }
            });
        }
    }
}
ProductScreen.addControlButton({
    component: SetFixDiscountButton,
});