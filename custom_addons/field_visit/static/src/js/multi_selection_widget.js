///** @odoo-module **/
//
//import { registry } from "@web/core/registry";
//import { Field } from "@web/views/fields/field";
//import { useState, xml } from "@odoo/owl";
//
//export class MultiSelectionField extends Field {
//    setup() {
//        super.setup();
//        const val = this.props.value || "";
//        this.state = useState({ selected: val ? val.split(",") : [] });
//    }
//
//    onChange(ev) {
//        const options = Array.from(ev.target.selectedOptions).map(opt => opt.value);
//        this.state.selected = options;
//        // correct way to update in Odoo 17:
//        this.props.record.update({ [this.props.name]: options.join(",") });
//    }
//
//    static template = xml/* xml */ `
//        <select class="o_field_widget o_field_multi_selection"
//                multiple="multiple"
//                t-on-change="onChange"
//                t-att-disabled="props.readonly">
//            <t t-foreach="props.selection" t-as="sel" t-key="sel[0]">
//                <option t-att-value="sel[0]"
//                        t-att-selected="state.selected.includes(sel[0])">
//                    <t t-esc="sel[1]"/>
//                </option>
//            </t>
//        </select>
//    `;
//}
//
//if (!registry.category("fields").contains("multi_selection_nensi")) {
//    registry.category("fields").add("multi_selection_nensi", {
//        component: MultiSelectionField,
//        extractProps: (fieldInfo, dynamicInfo) => ({
//            name: fieldInfo.name,
//            value: dynamicInfo.value,
//            readonly: dynamicInfo.readonly,
//            record: dynamicInfo.record,
//            selection: fieldInfo.options?.selection || [],
//        }),
//    });
//}
//
///** @odoo-module **/
//import { registry } from "@web/core/registry";
//import { Field } from "@web/views/fields/field";
//import { useState, xml } from "@odoo/owl";
//
//export class MultiSelectionField extends Field {
//    setup() {
//        super.setup();
//        const val = this.props.value || "";
//        this.state = useState({
//            selected: val ? val.split(",") : []
//        });
//    }
//
//    async onChange(ev) {
//        // Get all selected options from the multiple select
//        const options = Array.from(ev.target.selectedOptions).map(opt => opt.value);
//        this.state.selected = options;
//
//        // Store as comma-separated string in the Char field
//        await this.props.record.update({ [this.props.name]: options.join(",") });
//    }
//
//    static template = xml/* xml */ `
//        <select class="o_field_widget o_field_multi_selection"
//                t-att-disabled="props.readonly"
//                t-att-multiple="true"
//                t-on-change="onChange">
//            <t t-foreach="props.selection" t-as="sel" t-key="sel[0]">
//                <option t-att-value="sel[0]"
//                        t-att-selected="state.selected.includes(sel[0])"
//                        t-att-style="'background-color:' + (state.selected.includes(sel[0]) ? '#d3f9d8' : 'white')">
//                    <t t-esc="sel[1]"/>
//                </option>
//            </t>
//        </select>
//    `;
//}
//
//if (!registry.category("fields").contains("multi_selection_nensi")) {
//    registry.category("fields").add("multi_selection_nensi", {
//        component: MultiSelectionField,
//        extractProps: (fieldInfo, dynamicInfo) => ({
//            name: fieldInfo.name,
//            value: dynamicInfo.value,
//            readonly: dynamicInfo.readonly,
//            record: dynamicInfo.record,
//            selection: fieldInfo.options?.selection || []
//        })
//    });
//}

/** @odoo-module **/
import { Field } from "@web/views/fields/field";
import { useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

const template = xml/* xml */`
<div class="multi-day-picker">
    <table>
        <t t-foreach="Array(Math.ceil(31/7)).fill(0).map((_,r)=>r)" t-as="row">
            <tr>
                <t t-foreach="Array(7).fill(0).map((_,c)=>row*7+c+1)" t-as="day">
                    <td t-if="day &lt;= 31">
                        <button t-attf-class="day-btn #{state.selected.includes(day) ? 'selected' : ''}"
                                t-on-click="toggleDay(day)">
                            <t t-esc="day"/>
                        </button>
                    </td>
                </t>
            </tr>
        </t>
    </table>
</div>
`;

export class MultiDayPickerField extends Field {
    setup() {
        super.setup();
        // Initialize state.selected safely
        const val = this.props.value || []; // value = array of IDs (numbers)
        this.state = useState({ selected: val.slice() }); // clone array
    }

    toggleDay(day) {
        const idx = this.state.selected.indexOf(day);
        if (idx === -1) {
            this.state.selected.push(day);
        } else {
            this.state.selected.splice(idx, 1);
        }
        this.props.record.setValue(this.field.name, this.state.selected.slice());
    }
}

MultiDayPickerField.template = template;
registry.category("fields").add("multi_day_picker", MultiDayPickerField);





//
///** @odoo-module **/
//import { registry } from "@web/core/registry";
//import { CharField } from "@web/views/fields/char/char_field";
//import { useState } from "@odoo/owl";
//
//class MultiSelectField extends Field {
//    setup() {
//        super.setup();
//        const val = this.props.value || '';
//        this.state = useState({ selected: val ? val.split(',') : [] });
//    }
//
//    // Provide the options manually if needed
//    get selectionOptions() {
//        return [
//            ['option1', 'Option 1'],
//            ['option2', 'Option 2'],
//            ['option3', 'Option 3'],
//        ];
//    }
//
//    onChange(event) {
//        const selected = Array.from(event.target.selectedOptions)
//            .map(o => o.value)
//            .filter(Boolean);
//        this.state.selected = selected;
//        this._setValue(selected.join(','));
//    }
//
//    get template() {
//        return "MultiSelectFieldTemplate";
//    }
//}
//
//registry.category("fields").add("multi_selection", MultiSelectField);



///** @odoo-module **/
//import { registry } from "@web/core/registry";
//import { Field } from "@web/views/fields/field";
//import { h } from "@odoo/owl";
//import { useRef, onMounted } from "@odoo/owl";
//
//export class MultiSelectWidget extends Field {
//    setup() {
//        super.setup();
//        this.selectRef = useRef("select");
//
//        onMounted(() => {
//            const current = this.props.value || "";
//            const selectedList = current.split(",");
//            if (this.selectRef.el) {
//                for (const opt of this.selectRef.el.options) {
//                    opt.selected = selectedList.includes(opt.value);
//                }
//            }
//        });
//    }
//
//    onChange(ev) {
//        const options = ev.target.options;
//        const selected = [];
//        for (let i = 0; i < options.length; i++) {
//            if (options[i].selected) {
//                selected.push(options[i].value);
//            }
//        }
//        this.update(selected.join(","));
//    }
//
//    render() {
//        // Get the Selection field metadata safely
//        const selectionFieldName = this.props.attrs.selection_field; // pass original selection field name
//        let selection = [];
//        if (selectionFieldName && this.props.record?.fields?.[selectionFieldName]?.selection) {
//            selection = this.props.record.fields[selectionFieldName].selection;
//        } else {
//            selection = []; // fallback empty
//        }
//
//        return h(
//            "select",
//            {
//                ref: "select",
//                multiple: true,
//                class: "o_input o_field_widget",
//                onchange: (ev) => this.onChange(ev),
//            },
//            selection.map(([value, label]) => h("option", { key: value, value }, label))
//        );
//    }
//}
//
//registry.category("fields").add("multi_select_widget", MultiSelectWidget);
