/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class VinedoMapWidget extends Component {
    static template = "vinedo_field_service.VinedoMapWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.mapDiv = useRef("mapDiv");
        this.map = null;
        this.drawnItems = null;

        onMounted(() => {
            this.loadLeaflet();
        });

        onWillUnmount(() => {
            if (this.map) {
                this.map.remove();
            }
        });
    }

    async loadLeaflet() {
        if (typeof L === 'undefined') {
            await this.loadScript('https://unpkg.com/leaflet@1.9.4/dist/leaflet.css', 'css');
            await this.loadScript('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js', 'js');
        }
        await this.loadDraw();
    }

    async loadDraw() {
        if (typeof L !== 'undefined' && typeof L.Draw === 'undefined') {
            await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css', 'css');
            await this.loadScript('https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js', 'js');
        }
        this.initMap();
    }

    loadScript(url, type) {
        return new Promise((resolve, reject) => {
            if (type === 'css') {
                const link = document.createElement('link');
                link.rel = 'stylesheet';
                link.href = url;
                link.onload = resolve;
                link.onerror = reject;
                document.head.appendChild(link);
            } else {
                const script = document.createElement('script');
                script.src = url;
                script.onload = resolve;
                script.onerror = reject;
                document.head.appendChild(script);
            }
        });
    }

    initMap() {
        if (!this.mapDiv.el || this.map) return;

        try {
            this.map = L.map(this.mapDiv.el).setView([42.5, -3.0], 8);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(this.map);

            this.drawnItems = L.featureGroup().addTo(this.map);

            // Load existing polygon
            if (this.props.record.data[this.props.name]) {
                try {
                    const parsed = JSON.parse(this.props.record.data[this.props.name]);
                    const feature = (parsed && parsed.type === 'Feature') ? parsed : {
                        type: 'Feature',
                        geometry: parsed,
                        properties: {}
                    };
                    L.geoJSON(feature).eachLayer((layer) => {
                        this.drawnItems.addLayer(layer);
                        if (layer.getBounds) {
                            this.map.fitBounds(layer.getBounds());
                        }
                    });
                } catch (e) {
                    console.warn('Invalid GeoJSON in polygon field');
                }
            }

            // Drawing controls
            const drawControl = new L.Control.Draw({
                edit: { featureGroup: this.drawnItems },
                draw: {
                    polygon: true,
                    polyline: false,
                    rectangle: false,
                    circle: false,
                    marker: false,
                    circlemarker: false
                }
            });
            this.map.addControl(drawControl);

            // Event handlers
            this.map.on(L.Draw.Event.CREATED, (e) => {
                const layer = e.layer;
                this.drawnItems.clearLayers();
                this.drawnItems.addLayer(layer);
                const geojson = layer.toGeoJSON();
                const feature = {
                    type: 'Feature',
                    geometry: geojson.geometry,
                    properties: {}
                };
                this.updateValue(JSON.stringify(feature));
            });

            this.map.on(L.Draw.Event.EDITED, (e) => {
                e.layers.eachLayer((layer) => {
                    const geojson = layer.toGeoJSON();
                    const feature = {
                        type: 'Feature',
                        geometry: geojson.geometry,
                        properties: {}
                    };
                    this.updateValue(JSON.stringify(feature));
                });
            });

            // Fullscreen button
            this.addFullscreenButton();

        } catch (err) {
            console.error('Error initializing map widget', err);
        }
    }

    addFullscreenButton() {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn btn-sm btn-secondary vmap-fullscreen';
        button.textContent = 'Pantalla completa';
        button.style.position = 'absolute';
        button.style.top = '10px';
        button.style.right = '10px';
        button.style.zIndex = '1000';
        
        button.onclick = () => {
            this.mapDiv.el.classList.toggle('vinedo-map-fullscreen');
            setTimeout(() => {
                if (this.map) {
                    this.map.invalidateSize();
                }
            }, 200);
        };

        this.mapDiv.el.style.position = 'relative';
        this.mapDiv.el.appendChild(button);
    }

    updateValue(value) {
        this.props.record.update({ [this.props.name]: value });
    }
}

registry.category("fields").add("vinedo_map", VinedoMapWidget);
                    try {
                        var parsed = JSON.parse(this.value);
                        // Accept Feature or geometry; normalize to Feature
                        var feature = (parsed && parsed.type === 'Feature') ? parsed : {type: 'Feature', geometry: parsed, properties: {}};
                        L.geoJSON(feature).eachLayer(function (layer) {
                            drawnItems.addLayer(layer);
                            if (layer.getBounds) {
                                self.map.fitBounds(layer.getBounds());
                            }
                        });
                    } catch (e) {
                        console.warn('Invalid GeoJSON in field polygon');
                    }
                }

                // Fullscreen edit button
                var $btn = $('<button type="button" class="btn btn-sm btn-default vmap-fullscreen">Editar pantalla completa</button>');
                this.$el.prepend($btn);
                $btn.on('click', function () {
                    self.$mapDiv.toggleClass('vinedo-map-fullscreen');
                    setTimeout(function () { self.map.invalidateSize(); }, 200);
                });

                var drawControl = new L.Control.Draw({
                    edit: { featureGroup: drawnItems },
                    draw: { polygon: true, polyline: false, rectangle: false, circle: false, marker: false, circlemarker: false }
                });
                this.map.addControl(drawControl);

                this.map.on(L.Draw.Event.CREATED, function (e) {
                    var layer = e.layer;
                    drawnItems.clearLayers();
                    drawnItems.addLayer(layer);
                    var geojson = layer.toGeoJSON();
                    var feature = { type: 'Feature', geometry: geojson.geometry, properties: {} };
                    self._setValue(JSON.stringify(feature));
                });

                this.map.on(L.Draw.Event.EDITED, function (e) {
                    var layers = e.layers;
                    layers.eachLayer(function (layer) {
                        var geojson = layer.toGeoJSON();
                        var feature = { type: 'Feature', geometry: geojson.geometry, properties: {} };
                        self._setValue(JSON.stringify(feature));
                    });
                });

            } catch (err) {
                console.error('Error initializing map widget', err);
            }
        }
    });

    fieldRegistry.add('vinedo_map', MapWidget);
    return MapWidget;
});
