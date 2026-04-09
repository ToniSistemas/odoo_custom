/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class SimpleMapField extends Component {
    static template = "vinedo_field_service.SimpleMapField";
    static props = {
        ...standardFieldProps,
    };

    get mapUrl() {
        const record = this.props.record.data;
        const lat = record.latitude || 42.5;
        const lon = record.longitude || -3.0;
        const zoom = 15;
        
        // OpenStreetMap embed URL
        return `https://www.openstreetmap.org/export/embed.html?bbox=${lon-0.01},${lat-0.01},${lon+0.01},${lat+0.01}&layer=mapnik&marker=${lat},${lon}`;
    }

    get externalMapUrl() {
        const record = this.props.record.data;
        const lat = record.latitude || 42.5;
        const lon = record.longitude || -3.0;
        
        return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=15/${lat}/${lon}`;
    }
}

registry.category("fields").add("simple_map", SimpleMapField);
