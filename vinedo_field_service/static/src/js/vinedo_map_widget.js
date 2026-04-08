odoo.define('vinedo_field_service.vinedo_map_widget', function (require) {
    'use strict';

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');

    var MapWidget = AbstractField.extend({
        supportedFieldTypes: ['char', 'text'],
        init: function () {
            this._super.apply(this, arguments);
        },
        start: function () {
            var self = this;
            this._super();
            this.$el.css('min-height', '380px');
            this.$mapDiv = $('<div/>').css({height: '360px'});
            this.$el.empty().append(this.$mapDiv);

            // Load Leaflet if needed
            if (typeof L === 'undefined') {
                $('<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">').appendTo('head');
                $.getScript('https://unpkg.com/leaflet@1.9.4/dist/leaflet.js').done(function () {
                    self._loadDraw();
                });
            } else {
                this._loadDraw();
            }
        },
        _loadDraw: function () {
            var self = this;
            if (typeof L.Draw === 'undefined') {
                $('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.css">').appendTo('head');
                $.getScript('https://cdnjs.cloudflare.com/ajax/libs/leaflet.draw/1.0.4/leaflet.draw.js').done(function () {
                    self._initMap();
                });
            } else {
                this._initMap();
            }
        },
        _initMap: function () {
            var self = this;
            try {
                this.map = L.map(this.$mapDiv.get(0)).setView([40.0, -3.7], 6);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors'
                }).addTo(this.map);

                var drawnItems = L.featureGroup().addTo(this.map);

                if (this.value) {
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
