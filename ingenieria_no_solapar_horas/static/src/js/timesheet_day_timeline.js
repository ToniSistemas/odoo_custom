/** @odoo-module **/

import { Component, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { getId } from "@web/model/relational_model/utils";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class TimesheetDayTimeline extends Component {
    static template = "ingenieria_no_solapar_horas.TimesheetDayTimeline";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.timelineRef = useRef("timeline");
        this.state = useState({
            working: [],
            occupied: [],
            anchor: null,
            cursor: null,
            dragging: false,
            loading: false,
        });
        this.onGlobalPointerUp = this.onGlobalPointerUp.bind(this);
        window.addEventListener("pointerup", this.onGlobalPointerUp);
        onWillUnmount(() => window.removeEventListener("pointerup", this.onGlobalPointerUp));
        useEffect(
            () => {
                this.loadTimeline();
            },
            () => [this.dateValue, this.employeeId, this.props.record.resId]
        );
    }

    get dateValue() {
        const value = this.props.record.data.date;
        if (!value) {
            return false;
        }
        return value.toFormat ? value.toFormat("yyyy-MM-dd") : String(value);
    }

    get employeeId() {
        return getId(this.props.record.data.employee_id) || false;
    }

    get slots() {
        const selectedStart = Number(this.props.record.data.start_slot || -1);
        const selectedEnd = Number(this.props.record.data.end_slot || -1);
        return Array.from({ length: 96 }, (_, index) => {
            const start = index * 15;
            const end = start + 15;
            const occupied = this.state.occupied.find(
                (interval) => interval.start < end && interval.end > start
            );
            const working = this.state.working.some(
                (interval) => interval.start <= start && interval.end >= end
            );
            const previewStart = this.state.dragging
                ? Math.min(this.state.anchor, this.state.cursor) * 15
                : selectedStart;
            const previewEnd = this.state.dragging
                ? (Math.max(this.state.anchor, this.state.cursor) + 1) * 15
                : selectedEnd;
            return {
                index,
                start,
                label: this.formatMinutes(start),
                hourLabel: index % 4 === 0 ? this.formatMinutes(start) : "",
                occupied,
                working,
                selected: previewStart <= start && previewEnd >= end,
            };
        });
    }

    async loadTimeline() {
        if (!this.dateValue || !this.employeeId) {
            this.state.working = [];
            this.state.occupied = [];
            return;
        }
        const requestToken = Symbol("timeline");
        this.requestToken = requestToken;
        this.state.loading = true;
        const result = await this.orm.call(
            "account.analytic.line",
            "get_day_timeline",
            [],
            {
                date_value: this.dateValue,
                employee_id: this.employeeId,
                exclude_id: this.props.record.resId || false,
            }
        );
        if (this.requestToken === requestToken) {
            this.state.working = result.working;
            this.state.occupied = result.occupied;
            this.state.loading = false;
        }
    }

    onPointerDown(event, slot) {
        if (this.props.readonly || !slot.working || slot.occupied) {
            return;
        }
        event.preventDefault();
        this.state.anchor = slot.index;
        this.state.cursor = slot.index;
        this.state.dragging = true;
    }

    onPointerMove(event) {
        if (!this.state.dragging || !this.timelineRef.el) {
            return;
        }
        const element = this.timelineRef.el;
        const rect = element.getBoundingClientRect();
        const position = event.clientX - rect.left + element.scrollLeft;
        const index = Math.max(0, Math.min(95, Math.floor(position / 18)));
        const start = Math.min(this.state.anchor, index);
        const end = Math.max(this.state.anchor, index);
        const selectable = this.slots
            .slice(start, end + 1)
            .every((slot) => slot.working && !slot.occupied);
        if (selectable) {
            this.state.cursor = index;
        }
    }

    async onGlobalPointerUp() {
        if (!this.state.dragging) {
            return;
        }
        const start = Math.min(this.state.anchor, this.state.cursor) * 15;
        const end = (Math.max(this.state.anchor, this.state.cursor) + 1) * 15;
        this.state.dragging = false;
        await this.props.record.update({
            start_slot: String(start).padStart(4, "0"),
            end_slot: String(end).padStart(4, "0"),
        });
    }

    slotClass(slot) {
        if (slot.occupied) {
            return "o_timesheet_timeline_slot--occupied";
        }
        if (!slot.working) {
            return "o_timesheet_timeline_slot--unavailable";
        }
        if (slot.selected) {
            return "o_timesheet_timeline_slot--selected";
        }
        return "o_timesheet_timeline_slot--available";
    }

    slotTitle(slot) {
        if (slot.occupied) {
            return `${slot.label} · ${slot.occupied.label}`;
        }
        if (!slot.working) {
            return `${slot.label} · No laborable`;
        }
        return slot.label;
    }

    formatMinutes(minutes) {
        const hours = Math.floor(minutes / 60);
        const remainder = minutes % 60;
        return `${String(hours).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
    }
}

registry.category("fields").add("timesheet_day_timeline", {
    component: TimesheetDayTimeline,
    supportedTypes: ["char"],
    listViewWidth: 640,
    fieldDependencies: [
        { name: "date", type: "date" },
        { name: "employee_id", type: "many2one", relation: "hr.employee" },
        { name: "start_slot", type: "selection" },
        { name: "end_slot", type: "selection" },
    ],
});