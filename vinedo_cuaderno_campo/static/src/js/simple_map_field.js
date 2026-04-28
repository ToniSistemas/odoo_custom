/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class SimpleMapField extends Component {
    static template = "vinedo_field_service.SimpleMapField";
    static props = {
        ...standardFieldProps,
    };

    hasCoordinates() {
        if (!this.props.record || !this.props.record.data) {
            return false;
        }
        const data = this.props.record.data;
        return !!(data.latitude && data.longitude);
    }

    hasFincaName() {
        if (!this.props.record || !this.props.record.data) {
            return false;
        }
        return !!this.props.record.data.name;
    }

    get lat() {
        return (this.props.record && this.props.record.data && this.props.record.data.latitude) || 0;
    }

    get lon() {
        return (this.props.record && this.props.record.data && this.props.record.data.longitude) || 0;
    }

    get mapUrl() {
        if (!this.hasCoordinates()) return '';
        const lat = this.lat;
        const lon = this.lon;
        return `https://www.openstreetmap.org/export/embed.html?bbox=${lon-0.01},${lat-0.01},${lon+0.01},${lat+0.01}&layer=mapnik&marker=${lat},${lon}`;
    }

    get externalMapUrl() {
        if (!this.hasCoordinates()) return 'https://www.openstreetmap.org';
        const lat = this.lat;
        const lon = this.lon;
        return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=15/${lat}/${lon}`;
    }

    get googleMapsSearchUrl() {
        if (!this.props.record || !this.props.record.data) return 'https://www.google.com/maps';
        const name = this.props.record.data.name || '';
        const territorio = (this.props.record.data.territory_id && Array.isArray(this.props.record.data.territory_id) && this.props.record.data.territory_id.length > 1) ? this.props.record.data.territory_id[1] : '';
        const q = `${name} ${territorio} viñedo España`.trim();
        return `https://www.google.com/maps/search/${encodeURIComponent(q)}`;
    }
}

registry.category("fields").add("simple_map", SimpleMapField);
