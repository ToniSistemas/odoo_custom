import { useEffect } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { x2ManyCommands } from "@web/core/orm_service";
import { registry } from "@web/core/registry";
import { useOwnedDialogs } from "@web/core/utils/hooks";
import {
    Many2OneField,
    buildM2OFieldDescription,
} from "@web/views/fields/many2one/many2one_field";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

export class AttributeQuickValuesField extends Many2OneField {
    setup() {
        super.setup();
        this.addDialog = useOwnedDialogs();
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

    openValuesDialog() {
        const record = this.props.record;
        const attribute = record.data[this.props.name];
        const selectedIds = record.data.value_ids?.currentIds || [];
        this.addDialog(SelectCreateDialog, {
            title: _t("Valores de %s", attribute.display_name),
            resModel: "product.attribute.value",
            domain: [["attribute_id", "=", attribute.id]],
            context: { default_attribute_id: attribute.id, show_attribute: false },
            multiSelect: true,
            noCreate: false,
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
