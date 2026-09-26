import { patch } from "@web/core/utils/patch";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";
import { FashionAssignBarcodeDialog } from "../components/fashion_assign_barcode_dialog";

patch(BarcodePickingModel.prototype, {
    async _processBarcode(barcode) {
        // Solo consulta al servidor si el código no está ya en la caché local de la app
        if (this.resModel === "stock.picking" && this.resId && !this.cache?.dbBarcodeCache?.[barcode]) {
            const { unknown, candidates } = await this.orm.call(
                "stock.picking",
                "fashion_get_barcode_candidates",
                [[this.resId], barcode]
            );
            if (unknown && candidates.length) {
                return this._fashionOpenAssignDialog(barcode, candidates);
            }
        }
        return super._processBarcode(...arguments);
    },

    _fashionOpenAssignDialog(barcode, candidates) {
        return new Promise((resolve) => {
            this.dialogService.add(
                FashionAssignBarcodeDialog,
                {
                    barcode,
                    candidates,
                    onAssign: async (productId) => {
                        // Solo asigna el EAN en servidor; el +1 lo hace el flujo nativo para
                        // no pisar el estado local (no guardado) de la app Barcode.
                        await this.orm.call(
                            "stock.picking",
                            "fashion_assign_barcode_and_receive",
                            [[this.resId], barcode, productId],
                            { receive: false }
                        );
                        this.cache?.missingBarcode?.delete?.(barcode);
                        await super._processBarcode(barcode);
                    },
                },
                { onClose: resolve }
            );
        });
    },
});
