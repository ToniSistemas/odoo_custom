/** @odoo-module **/

/**
 * SigpacViewerWidget — OWL view widget for Odoo 19
 *
 * Registered in 'view_widgets' (not 'fields') to avoid the field-type
 * resolution system entirely. Used with <widget name="sigpac_viewer"/>
 * in the form view XML — no model field reference needed.
 *
 * The iframe is created via document.createElement() to bypass DOMPurify
 * (which strips <iframe> from HTML strings in Odoo 19's HtmlField).
 */

import { Component, onMounted, onWillUnmount, useEffect, useRef, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

class SigpacViewerWidget extends Component {
    static template = xml`
        <div t-ref="sigpac_container" class="o_sigpac_iframe_container"/>
    `;

    // OWL 2: accept any props without validation
    static props = ["*"];

    setup() {
        this.containerRef = useRef("sigpac_container");
        this.iframe = null;
        this._prevActivos = null;
        onMounted(() => this._mount());
        onWillUnmount(() => this._cleanup());

        /* Enviar postMessage al iframe cuando cambia el estado activo de los recintos */
        useEffect(() => {
            const recintos = this.props.record?.data?.recinto_ids;
            if (!recintos || !this.iframe?.contentWindow) { return; }
            const activos = (recintos.records || [])
                .filter(r => r.data.activo)
                .map(r => r.data.recinto_num);
            const activosStr = [...activos].sort().join(',');
            if (this._prevActivos === null) {
                this._prevActivos = activosStr;
                return;
            }
            if (this._prevActivos === activosStr) { return; }
            this._prevActivos = activosStr;
            this.iframe.contentWindow.postMessage(
                { type: 'recinto_update', activos },
                window.location.origin
            );
        }, () => {
            const recintos = this.props.record?.data?.recinto_ids;
            if (!recintos) { return [null]; }
            return [(recintos.records || [])
                .filter(r => r.data.activo)
                .map(r => r.data.recinto_num)
                .sort()
                .join(',')];
        });
    }

    _mount() {
        const el = this.containerRef.el;
        if (!el) { return; }

        const record = this.props.record;
        const recId = record && record.resId;

        if (!recId) {
            const msg = document.createElement("div");
            msg.style.cssText = (
                "padding:14px;background:#f8f9fa;"
                + "border:1px solid #dee2e6;border-radius:6px;"
                + "color:#6c757d;font-family:Arial,sans-serif;font-size:13px;"
            );
            msg.textContent = "Guarda la finca primero para activar el visor SIGPAC interactivo.";
            el.appendChild(msg);
            return;
        }

        this.iframe = document.createElement("iframe");
        this.iframe.style.cssText = (
            "width:100%;height:560px;"
            + "border:1px solid #ccc;"
            + "border-radius:4px;"
            + "display:block;"
        );
        this.iframe.setAttribute("frameborder", "0");
        el.appendChild(this.iframe);
        this.iframe.src = "/vinedo/sigpac_viewer/" + recId;
    }

    _cleanup() {
        if (this.iframe) {
            this.iframe.src = "about:blank";
            this.iframe.remove();
            this.iframe = null;
        }
    }
}

// Registered as 'view_widgets', NOT 'fields'.
// XML usage: <widget name="sigpac_viewer"/>
registry.category("view_widgets").add("sigpac_viewer", { component: SigpacViewerWidget });
