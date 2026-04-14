/** @odoo-module **/

/**
 * SigpacIframeWidget — Custom OWL field widget for Odoo 19
 *
 * Root cause of the blank iframe problem:
 *   Odoo 19's HtmlField widget passes content through DOMPurify which
 *   strips ALL <iframe> elements by default, regardless of sanitize=False
 *   on the Python field or options="{'sanitize': false}" in XML.
 *
 * Solution:
 *   Create the <iframe> element via document.createElement() + appendChild()
 *   which goes through direct DOM manipulation — completely bypassing
 *   DOMPurify (DOMPurify sanitizes HTML *strings*, not DOM API calls).
 *
 * The widget ignores the field value entirely. It only needs record.resId
 * to build the URL: /vinedo/sigpac_viewer/<resId>
 * (served by SigpacController in controllers/main.py, same Odoo origin).
 */

import { Component, onMounted, onWillUnmount, useRef, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class SigpacIframeWidget extends Component {
    // Minimal OWL template — just a container div
    // The iframe is created programmatically in onMounted, NOT in the template
    // This is intentional: OWL's xml`` tagged templates go through the same
    // sanitization pipeline as t-out, so we must use DOM API instead.
    static template = xml`
        <div t-ref="sigpac_container" class="o_sigpac_iframe_container"/>
    `;

    static supportedTypes = ["html"];

    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.containerRef = useRef("sigpac_container");
        this.iframe = null;
        onMounted(() => this._mount());
        onWillUnmount(() => this._cleanup());
    }

    _mount() {
        const el = this.containerRef.el;
        if (!el) { return; }

        const recId = this.props.record.resId;

        if (!recId) {
            // Record not yet saved — show placeholder message
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

        // ── Create <iframe> via DOM API ───────────────────────────────────
        // document.createElement bypasses DOMPurify entirely.
        // Setting .src after appending prevents race conditions in some browsers.
        this.iframe = document.createElement("iframe");
        this.iframe.style.cssText = (
            "width:100%;height:620px;"
            + "border:1px solid #ccc;"
            + "border-radius:4px;"
            + "display:block;"
        );
        this.iframe.setAttribute("frameborder", "0");
        el.appendChild(this.iframe);
        // Set src AFTER appending so the browser starts loading immediately
        this.iframe.src = "/vinedo/sigpac_viewer/" + recId;
    }

    _cleanup() {
        if (this.iframe) {
            // Blank src first to stop any ongoing network requests
            this.iframe.src = "about:blank";
            this.iframe.remove();
            this.iframe = null;
        }
    }
}

// Register the widget under the "sigpac_iframe" name.
// Usage in XML: <field name="sigpac_visor_embed" widget="sigpac_iframe" readonly="1"/>
registry.category("fields").add("sigpac_iframe", SigpacIframeWidget);
