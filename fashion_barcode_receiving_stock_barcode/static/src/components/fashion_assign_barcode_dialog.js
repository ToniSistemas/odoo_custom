import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class FashionAssignBarcodeDialog extends Component {
    static template = "fashion_barcode_receiving_stock_barcode.AssignBarcodeDialog";
    static components = { Dialog };
    static props = {
        barcode: String,
        candidates: Array,
        onAssign: Function,
        close: Function,
    };

    setup() {
        this.state = useState({ filter: "", busy: false });
    }

    get filteredCandidates() {
        const filter = this.state.filter.trim().toLowerCase();
        if (!filter) {
            return this.props.candidates;
        }
        return this.props.candidates.filter((c) =>
            `${c.display_name} ${c.default_code}`.toLowerCase().includes(filter)
        );
    }

    async assign(candidate) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.props.onAssign(candidate.id);
            this.props.close();
        } finally {
            this.state.busy = false;
        }
    }
}
