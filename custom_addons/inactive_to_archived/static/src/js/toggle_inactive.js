//odoo.define('inactive_to_archived.toggle_inactive', function (require) {
//    "use strict";
//
//    var core = require('web.core');
//    var FormView = require('web.FormView');
//    var _t = core._t;
//
//    FormView.include({
//        events: _.extend({}, FormView.prototype.events, {
//            'click .o_form_button_toggle_active': '_onToggleInactive',
//        }),
//
//        _onToggleInactive: function (event) {
//            var $target = $(event.currentTarget);
//            var recordId = this.model.get(this.handle).data.id;  // Get employee ID
//            var active = this.model.get(this.handle).data.active;  // Get current active state
//
//            // Make an RPC call to toggle the active state
//            this._rpc({
//                model: 'hr.employee',
//                method: 'write',
//                args: [[recordId], { 'active': !active }],
//            }).then(function () {
//                // Update the button label dynamically
//                if (active) {
//                    $target.text(_t('Restore'));
//                    $target.removeClass('btn-danger').addClass('btn-success');  // Change to green for active
//                } else {
//                    $target.text(_t('Inactive'));
//                    $target.removeClass('btn-success').addClass('btn-danger');  // Change to red for inactive
//                }
//            });
//        }
//    });
//});
