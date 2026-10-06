import { useEffect } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { x2ManyCommands } from "@web/core/orm_service";
import { registry } from "@web/core/registry";
import { useOwnedDialogs, useService } from "@web/core/utils/hooks";
import {
    Many2OneField,
    buildM2OFieldDescription,
} from "@web/views/fields/many2one/many2one_field";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

export class ValueSetSelectDialog extends SelectCreateDialog {
    static template = "textile_product_quick_create.ValueSetSelectDialog";
    static props = {
        ...SelectCreateDialog.props,
        valueSets: { type: Array, optional: true },
    };
    static defaultProps = {
        ...SelectCreateDialog.defaultProps,
        valueSets: [],
    };
}

export class AttributeQuickValuesField extends Many2OneField {
    setup() {
        super.setup();
        this.addDialog = useOwnedDialogs();
        this.orm = useService("orm");
        this.lastAttributeId = this.attributeId;
        useEffect(
            (attributeId) => {
                if (
                    attributeId &&
                    attributeId !== this.lastAttributeId &&
                    this.isPurchaseQuickCreate
                ) {
                    this.openValuesDialog();
                }
                this.lastAttributeId = attributeId;
            },
            () => [this.attributeId]
        );
    }

    get isPurchaseQuickCreate() {
        // El diálogo de producto abierto desde una línea de compra lleva esta clave en su contexto raíz.
        return Boolean(this.props.record.model.root.context?.textile_quick_create);
    }

    get attributeId() {
        return this.props.record.data[this.props.name]?.id || false;
    }

    async openValuesDialog() {
        const record = this.props.record;
        const attribute = record.data[this.props.name];
        const selectedIds = record.data.value_ids?.currentIds || [];
        const { records: valueSets } = await this.orm.webSearchRead(
            "textile.attribute.value.set",
            [["attribute_id", "=", attribute.id]],
            { specification: { name: {}, value_ids: { fields: { display_name: {} } } } }
        );
        this.addDialog(ValueSetSelectDialog, {
            title: _t("Valores de %s", attribute.display_name),
            resModel: "product.attribute.value",
            domain: [["attribute_id", "=", attribute.id]],
            context: { default_attribute_id: attribute.id, show_attribute: false },
            multiSelect: true,
            noCreate: false,
            valueSets: valueSets.map((valueSet) => ({
                id: valueSet.id,
                name: valueSet.name,
                value_ids: valueSet.value_ids.map((value) => value.id),
                value_names: valueSet.value_ids.map((value) => value.display_name).join(", "),
            })),
            onSelected: (resIds) =>
                record.update({
                    value_ids: [x2ManyCommands.set([...new Set([...selectedIds, ...resIds])])],
                }),
        });
    }
}

registry.category("fields").add("textile_attribute_quick_values", {
    ...buildM2OFieldDescription(AttributeQuickValuesField),
});
