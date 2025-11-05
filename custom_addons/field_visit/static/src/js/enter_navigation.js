///** @odoo-module **/
//import { patch } from "@web/core/utils/patch";
//import { FormRenderer } from "@web/views/form/form_renderer";
//
//patch(FormRenderer.prototype, {
//
//    setup() {
//        this._super && this._super(...arguments);
//        this._focusFirstRequiredField();
//    },
//
//    _focusFirstRequiredField() {
//        this.el && setTimeout(() => {
//            const firstRequired = this.el.querySelector(
//                'input[required]:not([disabled]):not([readonly]), ' +
//                'select[required]:not([disabled]):not([readonly]), ' +
//                'textarea[required]:not([disabled]):not([readonly])'
//            );
//            if (firstRequired) {
//                firstRequired.focus();
//            }
//        }, 50);
//    },
//
//    _onKeyDown(event) {
//        if (event.key === 'Enter') {
//            const requiredFields = Array.from(
//                this.el.querySelectorAll(
//                    'input[required]:not([disabled]):not([readonly]), ' +
//                    'select[required]:not([disabled]):not([readonly]), ' +
//                    'textarea[required]:not([disabled]):not([readonly])'
//                )
//            ).filter(f => f.offsetParent !== null);
//
//            const index = requiredFields.indexOf(event.target);
//            if (index >= 0 && index < requiredFields.length - 1) {
//                requiredFields[index + 1].focus();
//                event.preventDefault();
//            }
//        }
//    },
//
//    on_attach_callback() {
//        this.el && this.el.addEventListener('keydown', this._onKeyDown.bind(this));
//        this._super && this._super(...arguments);
//    },
//});
/** @odoo-module **/
import { registry } from "@web/core/registry";
import { onMounted } from "@odoo/owl";

registry.category("view_listeners").add("field_visit_enter_navigation", {
    async start(env) {
        // Wait for the form view to render
        onMounted(() => {
            const forms = document.querySelectorAll('form.o_form_sheet');
            forms.forEach(form => {
                // Focus first required field
                const firstRequired = form.querySelector(
                    'input[required]:not([disabled]):not([readonly]), ' +
                    'select[required]:not([disabled]):not([readonly]), ' +
                    'textarea[required]:not([disabled]):not([readonly])'
                );
                firstRequired && firstRequired.focus();

                // Keydown listener for Enter navigation
                form.addEventListener('keydown', function(event) {
                    if (event.key === 'Enter') {
                        const requiredFields = Array.from(
                            form.querySelectorAll(
                                'input[required]:not([disabled]):not([readonly]), ' +
                                'select[required]:not([disabled]):not([readonly]), ' +
                                'textarea[required]:not([disabled]):not([readonly])'
                            )
                        ).filter(f => f.offsetParent !== null);

                        const index = requiredFields.indexOf(event.target);
                        if (index >= 0 && index < requiredFields.length - 1) {
                            requiredFields[index + 1].focus();
                            event.preventDefault();
                        }
                    }
                });
            });
        });
    },
});
