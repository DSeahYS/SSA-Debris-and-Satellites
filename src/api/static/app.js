/**
 * GOD'S EYE — C2 Interface Controller v5
 * Mission-critical SSA: Pc, CDM, advisories, decay alerts,
 * proper ECI→ECEF coordinates, and expanded weather.
 */

const S = { primary: null, conjunctions: [], predictions: [], weather: null, screening: false, logCount: 0, objects: [], liveMode: true, timeOffset: 0, advisories: [], decayAlerts: [], selectedConj: null, trackedSats: new Map(), showSwath: true };

// 8 distinct track colors for multi-satellite orbits
const TRACK_COLORS = [
    '#00ff88', '#ff6b6b', '#ffd93d', '#6bcbff', '#c56bff',
    '#ff8c42', '#00e5ff', '#ff4da6'
];
const $ = id => document.getElementById(id);

const D = {
    utcClock: $('utc-clock'), localClock: $('local-clock'), mjdClock: $('mjd-clock'),
    threatVal: $('threat-val'), apiDot: $('api-dot'), apiLabel: $('api-label'),
    searchInput: $('search-input'), btnSearch: $('btn-search'), searchResults: $('search-results'),
    satDetail: $('sat-detail'), priStatus: $('pri-status'),
    envKp: $('env-kp'), envF107: $('env-f107'), envStorm: $('env-storm'),
    envSwSpeed: $('env-sw-speed'), envSwDens: $('env-sw-dens'), envBtBz: $('env-bt-bz'),
    envXray: $('env-xray'), envProton: $('env-proton'), envTs: $('env-ts'),
    inThreshold: $('in-threshold'), inHours: $('in-hours'), inCatalog: $('in-catalog'),
    inGlobeGroup: $('in-globe-group'),
    btnScreen: $('btn-screen'), btnPropagate: $('btn-propagate'), btnLoadObjects: $('btn-load-objects'),
    screenStatus: $('screen-status'),
    globeSub: $('globe-sub'), globeContainer: $('globeViz'),
    satPopup: $('sat-popup'), popupContent: $('popup-content'),
    eventLog: $('event-log'), logCountEl: $('log-count'),
    conjCount: $('conj-count'), conjTbody: $('conj-tbody'),
    tsCrit: $('ts-crit'), tsWarn: $('ts-warn'), tsCaut: $('ts-caut'), tsNom: $('ts-nom'),
    maneuverDetail: $('maneuver-detail'),
    statScreened: $('stat-screened'), statApproaches: $('stat-approaches'),
    statOnGlobe: $('stat-on-globe'),
    btnLive: $('btn-live'), btnHist: $('btn-hist'),
    timeSliderWrap: $('time-slider-wrap'), timeOffset: $('time-offset'), timeOffsetVal: $('time-offset-val'),
    // New v5 elements
    advCount: $('adv-count'), advisoryList: $('advisory-list'),
    decayCount: $('decay-count'), decayList: $('decay-list'),
    btnCdmExport: $('btn-cdm-export'),
    quickPick: $('quick-pick'),
    trackedList: $('tracked-list'),
    btnSwathToggle: $('btn-swath-toggle'),
};

// Clocks
function updateClocks() {
    const now = new Date();
    D.utcClock.textContent = now.toISOString().substring(11, 19) + 'Z';
    D.localClock.textContent = now.toLocaleTimeString('en-GB');
    const jd = (now.getTime() / 86400000) + 2440587.5;
    D.mjdClock.textContent = (jd - 2400000.5).toFixed(3);
}
setInterval(updateClocks, 1000);
updateClocks();

// API
const API = {
    async get(u) { const r = await fetch(u); const j = await r.json(); if (!r.ok) throw new Error(j.error?.message || `HTTP ${r.status}`); return j; },
    search(q) { return this.get(`/api/v1/search?q=${encodeURIComponent(q)}`); },
    weather() { return this.get('/api/v1/space-weather'); },
    positions(g) { return this.get(`/api/v1/positions?group=${g}`); },
    conjunctions(id, t, h, g) { return this.get(`/api/v1/conjunctions?norad_id=${id}&threshold_km=${t}&hours=${h}&screen_groups=${encodeURIComponent(g)}`); },
    predict(id, d, s) { let u = `/api/v1/predict/baseline?days=${d}&steps_per_day=${s}`; if (id) u += `&norad_id=${id}`; return this.get(u); },
    advisories() { return this.get('/api/v1/advisories'); },
    decay(group, days) { return this.get(`/api/v1/decay?group=${encodeURIComponent(group)}&threshold_days=${days}`); },
    async cdmText(priId, secId) { const r = await fetch(`/api/v1/cdm?norad_id=${priId}&secondary_id=${secId}&format=kvn`); const j = await r.json(); return j.data; },
};

// Globe
const GlobeCtrl = {
    w: null,
    entities: [],
    trackEntities: new Map(),  // norad_id → { path, swath, color }
    async init() {
        // Create viewer with default imagery (Bing Maps via Ion)
        this.w = new Cesium.Viewer(D.globeContainer, {
            animation: false,
            baseLayerPicker: false,
            fullscreenButton: false,
            geocoder: true,
            homeButton: true,
            infoBox: false,
            sceneModePicker: false,
            selectionIndicator: false,
            timeline: false,
            navigationHelpButton: true,
            navigationInstructionsInitiallyVisible: false,
            scene3DOnly: true,
        });

        // Set terrain asynchronously
        try {
            this.w.scene.terrainProvider = await Cesium.createWorldTerrainAsync();
        } catch (e) {
            console.warn('Terrain load failed, using ellipsoid:', e);
        }

        // Add 3D buildings asynchronously
        try {
            const buildings = await Cesium.createOsmBuildingsAsync();
            this.w.scene.primitives.add(buildings);
        } catch (e) {
            console.warn('OSM Buildings load failed:', e);
        }

        // Atmosphere styling
        this.w.scene.skyAtmosphere.hueShift = -0.1;
        this.w.scene.skyAtmosphere.saturationShift = 0.5;
        this.w.scene.globe.enableLighting = false;

        // Add higher-res imagery layer (Bing Maps Aerial with Labels)
        try {
            const bingProvider = await Cesium.IonImageryProvider.fromAssetId(3);
            this.w.scene.imageryLayers.addImageryProvider(bingProvider);
        } catch (e) {
            console.warn('Enhanced imagery failed, using default:', e);
        }

        // Click handler: satellites OR ground location
        const handler = new Cesium.ScreenSpaceEventHandler(this.w.scene.canvas);
        handler.setInputAction((click) => {
            const pickedObject = this.w.scene.pick(click.position);
            if (Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id.satelliteData) {
                // Satellite clicked
                Act.clickObject(pickedObject.id.satelliteData);
                this.hideLocationPopup();
            } else {
                D.satPopup.classList.add('hidden');
                // Check if ground was clicked
                const ray = this.w.camera.getPickRay(click.position);
                const cartesian = this.w.scene.globe.pick(ray, this.w.scene);
                if (cartesian) {
                    const carto = Cesium.Cartographic.fromCartesian(cartesian);
                    const lat = Cesium.Math.toDegrees(carto.latitude);
                    const lng = Cesium.Math.toDegrees(carto.longitude);
                    this.showLocationPopup(click.position, lat, lng);
                } else {
                    this.hideLocationPopup();
                }
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
        
        this.w.cesiumWidget.screenSpaceEventHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
    },

    // Location popup methods
    showLocationPopup(screenPos, lat, lng) {
        const popup = document.getElementById('location-popup');
        const coordsEl = document.getElementById('loc-coords');
        const nameEl = document.getElementById('loc-name');
        const infoEl = document.getElementById('loc-info');
        if (!popup) return;

        // Position popup near click
        const container = D.globeContainer.getBoundingClientRect();
        let px = container.left + screenPos.x + 15;
        let py = container.top + screenPos.y - 10;
        // Keep on screen
        if (px + 300 > window.innerWidth) px = px - 330;
        if (py + 200 > window.innerHeight) py = py - 150;

        popup.style.left = px + 'px';
        popup.style.top = py + 'px';
        popup.classList.add('visible');

        coordsEl.textContent = `${lat >= 0 ? lat.toFixed(4) + '°N' : (-lat).toFixed(4) + '°S'}, ${lng >= 0 ? lng.toFixed(4) + '°E' : (-lng).toFixed(4) + '°W'}`;
        nameEl.textContent = '';
        infoEl.innerHTML = '<span class="loc-loading">⏳ IDENTIFYING LOCATION...</span>';

        // Call AI to identify
        fetch(`/api/v1/location-info?lat=${lat.toFixed(4)}&lng=${lng.toFixed(4)}`)
            .then(r => r.json())
            .then(data => {
                if (data?.data) {
                    nameEl.textContent = data.data.name || '';
                    infoEl.textContent = data.data.info || '';
                }
            })
            .catch(e => {
                infoEl.textContent = `Lookup failed: ${e.message}`;
            });

        Log.data(`CLICK: ${lat.toFixed(4)}°, ${lng.toFixed(4)}°`);
    },

    hideLocationPopup() {
        const popup = document.getElementById('location-popup');
        if (popup) popup.classList.remove('visible');
    },
    showPoints(data) {
        // Remove non-track entities (satellite dots)
        const trackIds = new Set();
        this.trackEntities.forEach(te => {
            if (te.path) trackIds.add(te.path.id);
            if (te.swath) trackIds.add(te.swath.id);
        });
        const toRemove = [];
        this.w.entities.values.forEach(e => {
            if (!trackIds.has(e.id)) toRemove.push(e);
        });
        toRemove.forEach(e => this.w.entities.remove(e));
        
        data.forEach(d => {
            const isPrimary = d.norad_id === S.primary?.norad_id;
            const tracked = S.trackedSats.get(d.norad_id);
            let color = Cesium.Color.fromCssColorString('#00d4ff');
            if (tracked) color = Cesium.Color.fromCssColorString(tracked.color);
            else if (isPrimary) color = Cesium.Color.fromCssColorString('#00ff88');
            else if (d.name.includes('DEB')) color = Cesium.Color.fromCssColorString('#ff4466');
            else if (d.name.includes('R/B')) color = Cesium.Color.fromCssColorString('#ff8800');

            this.w.entities.add({
                position: Cesium.Cartesian3.fromDegrees(d.lng, d.lat, d.alt_km * 1000),
                point: {
                    pixelSize: (isPrimary || tracked) ? 8 : 4,
                    color: color,
                    outlineColor: Cesium.Color.BLACK,
                    outlineWidth: 1
                },
                satelliteData: d
            });
        });

        // Redraw all tracked paths
        this.redrawAllTracks();
    },

    // Add or update a single track (path + swath) for a satellite
    addTrack(noradId, predictions, colorHex) {
        this.removeTrack(noradId);
        if (!predictions?.length) return;

        const cssColor = Cesium.Color.fromCssColorString(colorHex);

        // Build positions array
        const positions = [];
        const groundPositions = [];
        predictions.forEach(p => {
            positions.push(p.lng, p.lat, p.alt * 1000);
            groundPositions.push(Cesium.Cartographic.fromDegrees(p.lng, p.lat));
        });

        // Orbital path polyline
        const pathEntity = this.w.entities.add({
            polyline: {
                positions: Cesium.Cartesian3.fromDegreesArrayHeights(positions),
                width: 2.5,
                material: new Cesium.PolylineDashMaterialProperty({
                    color: cssColor.withAlpha(0.8),
                    dashLength: 16.0
                })
            }
        });

        // Scan swath corridor — width based on altitude
        // Typical EO sensor ~45° FOV → swath ≈ 2 * alt * tan(22.5°)
        const avgAltKm = predictions.reduce((s, p) => s + p.alt, 0) / predictions.length * 6371;
        const swathWidthKm = Math.min(2 * avgAltKm * Math.tan(22.5 * Math.PI / 180), 3000);
        const swathHalfM = (swathWidthKm * 1000) / 2;

        // Only create swath for every Nth point to keep it efficient
        const step = Math.max(1, Math.floor(predictions.length / 300));
        const corridorDegrees = [];
        for (let i = 0; i < predictions.length; i += step) {
            corridorDegrees.push(predictions[i].lng, predictions[i].lat);
        }

        let swathEntity = null;
        if (S.showSwath && corridorDegrees.length >= 4) {
            swathEntity = this.w.entities.add({
                corridor: {
                    positions: Cesium.Cartesian3.fromDegreesArray(corridorDegrees),
                    width: swathHalfM * 2,
                    material: cssColor.withAlpha(0.12),
                    height: 0,
                    outline: true,
                    outlineColor: cssColor.withAlpha(0.3),
                    outlineWidth: 1,
                }
            });
        }

        this.trackEntities.set(noradId, { path: pathEntity, swath: swathEntity, color: colorHex, predictions });
    },

    removeTrack(noradId) {
        const existing = this.trackEntities.get(noradId);
        if (existing) {
            if (existing.path) this.w.entities.remove(existing.path);
            if (existing.swath) this.w.entities.remove(existing.swath);
            this.trackEntities.delete(noradId);
        }
    },

    // Redraw all tracked paths (used after showPoints clears entities)
    redrawAllTracks() {
        // Re-add tracks from stored predictions
        const entries = Array.from(S.trackedSats.entries());
        entries.forEach(([noradId, info]) => {
            if (info.predictions) {
                this.addTrack(noradId, info.predictions, info.color);
            }
        });
    },

    // Toggle swath visibility for all tracks
    toggleSwath(show) {
        S.showSwath = show;
        // Remove all swaths then re-add if showing
        this.trackEntities.forEach((te, noradId) => {
            if (te.swath) {
                this.w.entities.remove(te.swath);
                te.swath = null;
            }
        });
        if (show) {
            this.trackEntities.forEach((te, noradId) => {
                if (te.predictions) {
                    const info = S.trackedSats.get(noradId);
                    if (info) {
                        // Re-create swath
                        const cssColor = Cesium.Color.fromCssColorString(te.color);
                        const step = Math.max(1, Math.floor(te.predictions.length / 300));
                        const corridorDegrees = [];
                        for (let i = 0; i < te.predictions.length; i += step) {
                            corridorDegrees.push(te.predictions[i].lng, te.predictions[i].lat);
                        }
                        const avgAltKm = te.predictions.reduce((s, p) => s + p.alt, 0) / te.predictions.length * 6371;
                        const swathWidthKm = Math.min(2 * avgAltKm * Math.tan(22.5 * Math.PI / 180), 3000);
                        if (corridorDegrees.length >= 4) {
                            te.swath = this.w.entities.add({
                                corridor: {
                                    positions: Cesium.Cartesian3.fromDegreesArray(corridorDegrees),
                                    width: swathWidthKm * 1000,
                                    material: cssColor.withAlpha(0.12),
                                    height: 0,
                                    outline: true,
                                    outlineColor: cssColor.withAlpha(0.3),
                                    outlineWidth: 1,
                                }
                            });
                        }
                    }
                }
            });
        }
    },

    showPath(data, colorHex = '#00ff88') {
        // Legacy single-path method for primary satellite
        if (S.primary) {
            this.addTrack(S.primary.norad_id, data, colorHex);
        }
    }
};

// Log
const Log = {
    add(m, c = '') { S.logCount++; const d = document.createElement('div'); d.className = `ev ${c}`; d.innerHTML = `<span class="ev-ts">${new Date().toISOString().substring(11, 19)}Z</span><span class="ev-msg">${m}</span>`; D.eventLog.appendChild(d); D.eventLog.scrollTop = D.eventLog.scrollHeight; D.logCountEl.textContent = S.logCount; },
    ok(m) { this.add(m, 'ok'); }, err(m) { this.add(`ERR: ${m}`, 'err'); }, warn(m) { this.add(m, 'warn'); }, data(m) { this.add(m, 'data'); },
};

// Actions
const Act = {
    async search() {
        const q = D.searchInput.value.trim(); if (!q) return;
        Log.add(`QUERY: "${q}"`);
        try { const r = await API.search(q); this.renderSearch(r.data); Log.data(`${r.data.length} RESULT(S)`); } catch (e) { Log.err(e.message); }
    },
    renderSearch(results) {
        D.searchResults.innerHTML = '';
        if (!results.length) { D.searchResults.innerHTML = '<div class="sr-item null-state">NO RESULTS</div>'; D.searchResults.classList.remove('hidden'); return; }
        results.slice(0, 20).forEach(s => {
            const d = document.createElement('div'); d.className = 'sr-item';
            d.innerHTML = `<div class="sr-name">${s.name}</div><div class="sr-meta">${s.norad_id} · ${s.periapsis_km}×${s.apoapsis_km} km · ${s.inclination}° · ${s.group}</div>`;
            d.onmousedown = () => this.selectSat(s);
            D.searchResults.appendChild(d);
        });
        D.searchResults.classList.remove('hidden');
    },
    selectSat(sat) {
        S.primary = sat;
        D.searchResults.classList.add('hidden');
        D.searchInput.value = sat.name;
        D.priStatus.textContent = 'TRACKING'; D.priStatus.style.color = '#00ff88';
        D.satDetail.innerHTML = `
            <div class="det-title">${sat.name}</div>
            <div class="det-row"><div class="det-cell"><label>NORAD ID</label><div class="det-val">${sat.norad_id}</div></div><div class="det-cell"><label>GROUP</label><div class="det-val">${(sat.group || '').toUpperCase()}</div></div></div>
            <div class="det-row"><div class="det-cell"><label>PERIAPSIS</label><div class="det-val">${sat.periapsis_km} km</div></div><div class="det-cell"><label>APOAPSIS</label><div class="det-val">${sat.apoapsis_km} km</div></div></div>
            <div class="det-row"><div class="det-cell"><label>INCLINATION</label><div class="det-val">${sat.inclination}°</div></div><div class="det-cell"><label>PERIOD</label><div class="det-val">${sat.period_min} min</div></div></div>
            <div class="det-row"><div class="det-cell"><label>ORBIT TYPE</label><div class="det-val">${sat.periapsis_km < 2000 ? 'LEO' : sat.periapsis_km < 35786 ? 'MEO' : 'GEO'}</div></div><div class="det-cell"><label>ALT BAND</label><div class="det-val">${Math.round(sat.periapsis_km)}-${Math.round(sat.apoapsis_km)} km</div></div></div>
        `;
        D.btnScreen.disabled = false; D.btnPropagate.disabled = false;
        D.screenStatus.textContent = `TARGET: ${sat.name} (${sat.norad_id})`;
        D.globeSub.textContent = sat.name;
        Log.ok(`TARGET: ${sat.name} [${sat.norad_id}]`);
        this.propagate();
        // Re-render points to highlight primary
        if (S.objects.length) GlobeCtrl.showPoints(S.objects);
    },

    // Click a satellite object on the globe
    clickObject(pt) {
        const isTracked = S.trackedSats.has(pt.norad_id);
        const safeName = pt.name.replace(/'/g, "\\'");
        D.satPopup.classList.remove('hidden');
        D.popupContent.innerHTML = `
            <div class="det-title" style="font-size:11px">${pt.name}</div>
            <div class="det-row"><div class="det-cell"><label>NORAD</label><div class="det-val">${pt.norad_id}</div></div><div class="det-cell"><label>ALT</label><div class="det-val">${pt.alt_km} km</div></div></div>
            <div class="det-row"><div class="det-cell"><label>LAT</label><div class="det-val">${pt.lat.toFixed(2)}°</div></div><div class="det-cell"><label>LNG</label><div class="det-val">${pt.lng.toFixed(2)}°</div></div></div>
            <div class="det-row"><div class="det-cell"><label>PERIAPSIS</label><div class="det-val">${pt.periapsis_km} km</div></div><div class="det-cell"><label>APOAPSIS</label><div class="det-val">${pt.apoapsis_km} km</div></div></div>
            <div class="det-row"><div class="det-cell"><label>INCL</label><div class="det-val">${pt.inclination}°</div></div><div class="det-cell"><label>PERIOD</label><div class="det-val">${pt.period_min} min</div></div></div>
            <div style="padding:4px;margin-top:4px;display:flex;gap:4px">
                <button class="cmd-btn cmd-primary" onclick="Act.selectSat({norad_id:${pt.norad_id},name:'${safeName}',group:'${D.inGlobeGroup.value}',periapsis_km:${pt.periapsis_km},apoapsis_km:${pt.apoapsis_km},inclination:${pt.inclination},period_min:${pt.period_min}});document.getElementById('sat-popup').classList.add('hidden')">SET PRIMARY</button>
                <button class="cmd-btn ${isTracked ? 'cmd-danger' : 'cmd-track'}" onclick="Act.${isTracked ? 'untrackSat' : 'trackSat'}({norad_id:${pt.norad_id},name:'${safeName}',group:'${D.inGlobeGroup.value}',periapsis_km:${pt.periapsis_km},apoapsis_km:${pt.apoapsis_km},inclination:${pt.inclination},period_min:${pt.period_min}});document.getElementById('sat-popup').classList.add('hidden')">${isTracked ? '✕ UNTRACK' : '+ TRACK'}</button>
            </div>
        `;
        Log.data(`INSPECT: ${pt.name} [${pt.norad_id}] @ ${pt.alt_km} km`);
    },

    // Track a satellite (add to multi-track list)
    async trackSat(sat) {
        if (S.trackedSats.has(sat.norad_id)) return;
        const colorIdx = S.trackedSats.size % TRACK_COLORS.length;
        const color = TRACK_COLORS[colorIdx];
        S.trackedSats.set(sat.norad_id, { sat, color, predictions: null });
        Log.ok(`TRACKING: ${sat.name} [${sat.norad_id}] — ${color}`);

        // Fetch predictions for this satellite
        try {
            const r = await API.predict(sat.norad_id, 1, 1440);
            const info = S.trackedSats.get(sat.norad_id);
            if (info) {
                info.predictions = r.data;
                GlobeCtrl.addTrack(sat.norad_id, r.data, color);
            }
            Log.ok(`${r.data.length} ORBITAL PTS FOR ${sat.name}`);
        } catch (e) { Log.err(`TRACK ${sat.name}: ${e.message}`); }

        this.renderTrackedList();
        if (S.objects.length) GlobeCtrl.showPoints(S.objects);
    },

    untrackSat(sat) {
        S.trackedSats.delete(sat.norad_id);
        GlobeCtrl.removeTrack(sat.norad_id);
        Log.warn(`UNTRACKED: ${sat.name} [${sat.norad_id}]`);
        this.renderTrackedList();
        if (S.objects.length) GlobeCtrl.showPoints(S.objects);
    },

    renderTrackedList() {
        const el = D.trackedList;
        const countEl = document.getElementById('tracked-count');
        if (countEl) countEl.textContent = S.trackedSats.size;
        if (!el) return;
        if (!S.trackedSats.size) {
            el.innerHTML = '<p class="null-state">NO SATELLITES TRACKED</p>';
            return;
        }
        el.innerHTML = '';
        S.trackedSats.forEach((info, noradId) => {
            const item = document.createElement('div');
            item.className = 'tracked-item';
            item.innerHTML = `
                <span class="tracked-color" style="background:${info.color}"></span>
                <span class="tracked-name">${info.sat.name}</span>
                <span class="tracked-id">${noradId}</span>
                <button class="tracked-remove" onclick="Act.untrackSat({norad_id:${noradId},name:'${info.sat.name.replace(/'/g, "\\'")}'})" title="Remove track">✕</button>
            `;
            el.appendChild(item);
        });
    },

    async loadWeather() {
        try {
            const r = await API.weather(); const w = r.data; S.weather = w;
            D.envKp.textContent = w.kp_index?.toFixed(1) ?? '—';
            D.envF107.textContent = w.f107_flux?.toFixed(0) ?? '—';
            const st = (w.storm_level || '—').toUpperCase().replace('_', ' ');
            D.envStorm.textContent = st;
            const cls = w.storm_level === 'quiet' ? 'quiet' : w.storm_level === 'unsettled' ? 'unsettled' : w.storm_level === 'storm' ? 'storm' : 'severe';
            D.envKp.className = `env-val ${cls}`; D.envStorm.className = `env-val ${cls}`;
            // Solar wind
            D.envSwSpeed.textContent = w.solar_wind_speed ? `${Math.round(w.solar_wind_speed)}` : '—';
            D.envSwSpeed.className = `env-val ${w.solar_wind_speed > 600 ? 'storm' : w.solar_wind_speed > 400 ? 'unsettled' : 'quiet'}`;
            D.envSwDens.textContent = w.solar_wind_density ? `${w.solar_wind_density.toFixed(1)}` : '—';
            D.envBtBz.textContent = (w.solar_wind_bt != null && w.solar_wind_bz != null) ? `${w.solar_wind_bt.toFixed(1)}/${w.solar_wind_bz.toFixed(1)}` : '—';
            if (w.solar_wind_bz != null && w.solar_wind_bz < -10) D.envBtBz.className = 'env-val storm';
            // X-ray
            D.envXray.textContent = w.xray_class || '—';
            if (w.xray_class && w.xray_class.startsWith('M')) D.envXray.className = 'env-val unsettled';
            else if (w.xray_class && w.xray_class.startsWith('X')) D.envXray.className = 'env-val storm';
            else D.envXray.className = 'env-val quiet';
            // Proton
            D.envProton.textContent = w.proton_gt10mev != null ? w.proton_gt10mev.toFixed(1) : '—';
            if (w.proton_gt10mev > 10) D.envProton.className = 'env-val storm';
            D.envTs.textContent = `UPDATED: ${w.timestamp || '—'}`;
            D.apiDot.className = 'status-dot green'; D.apiLabel.textContent = 'NOMINAL';
        } catch (e) { D.apiDot.className = 'status-dot red'; D.apiLabel.textContent = 'FAULT'; Log.err(`SWPC: ${e.message}`); }
    },

    async loadObjects() {
        const group = D.inGlobeGroup.value;
        Log.add(`LOADING OBJECTS: ${group.toUpperCase()}`);
        try {
            const r = await API.positions(group);
            S.objects = r.data;
            GlobeCtrl.showPoints(r.data);
            D.statOnGlobe.textContent = r.data.length;
            D.globeSub.textContent = `${group.toUpperCase()} — ${r.data.length} OBJ`;
            Log.ok(`${r.data.length} OBJECTS RENDERED ON GLOBE`);
        } catch (e) { Log.err(e.message); }
    },

    async screen() {
        if (!S.primary || S.screening) return;
        S.screening = true; D.btnScreen.disabled = true; D.screenStatus.textContent = '⏳ SCREENING...';
        try {
            const r = await API.conjunctions(S.primary.norad_id, +D.inThreshold.value, +D.inHours.value, D.inCatalog.value);
            S.conjunctions = r.data;
            this.renderThreatBoard(r.data, r.meta);
            Log.ok(`SCREENED ${r.meta.total_screened} → ${r.data.length} CONJUNCTION(S)`);
            D.statScreened.textContent = r.meta.total_screened; D.statApproaches.textContent = r.data.length;
            const hasCrit = r.data.some(c => c.risk_level === 'critical'), hasWarn = r.data.some(c => c.risk_level === 'warning'), hasCaut = r.data.some(c => c.risk_level === 'caution');
            D.threatVal.textContent = hasCrit ? 'CRITICAL' : hasWarn ? 'ELEVATED' : hasCaut ? 'CAUTION' : 'NOMINAL';
            D.threatVal.className = hasCrit ? 'threat-critical' : hasWarn ? 'threat-warning' : hasCaut ? 'threat-caution' : 'threat-nominal';
        } catch (e) { Log.err(e.message); } finally { S.screening = false; D.btnScreen.disabled = false; D.screenStatus.textContent = `TARGET: ${S.primary.name}`; }
    },

    renderThreatBoard(evts, meta) {
        D.conjCount.textContent = evts.length;
        D.tsCrit.textContent = evts.filter(e => e.risk_level === 'critical').length;
        D.tsWarn.textContent = evts.filter(e => e.risk_level === 'warning').length;
        D.tsCaut.textContent = evts.filter(e => e.risk_level === 'caution').length;
        D.tsNom.textContent = evts.filter(e => e.risk_level === 'nominal').length;
        D.conjTbody.innerHTML = '';
        if (!evts.length) { D.conjTbody.innerHTML = `<tr><td colspan="9" class="null-state">CLEAR — ${meta.threshold_km}KM / ${meta.hours}H</td></tr>`; D.maneuverDetail.innerHTML = '<p class="null-state">NO CA REQUIRED</p>'; return; }
        evts.forEach((e, i) => {
            const tr = document.createElement('tr');
            const pcDisplay = e.collision_probability_display || (e.collision_probability != null ? e.collision_probability.toExponential(2) : '—');
            const pcClass = e.collision_probability >= 1e-4 ? 'pc-critical' : e.collision_probability >= 1e-5 ? 'pc-warning' : e.collision_probability >= 1e-7 ? 'pc-caution' : 'pc-nominal';
            tr.innerHTML = `<td><span class="lvl-dot lvl-${e.risk_level}"></span>${e.risk_level.substr(0, 4).toUpperCase()}</td><td title="${e.secondary_norad_id}">${e.secondary_name}</td><td><strong>${e.miss_distance_km.toFixed(2)}</strong></td><td class="pc-val ${pcClass}">${pcDisplay}</td><td>${e.radial_km.toFixed(2)}</td><td>${e.in_track_km.toFixed(2)}</td><td>${e.cross_track_km.toFixed(2)}</td><td>${e.relative_velocity_km_s.toFixed(2)}</td><td>${(e.tca || '').substring(5, 19).replace('T', ' ')}</td>`;
            tr.onclick = () => this.selectConj(e, i);
            D.conjTbody.appendChild(tr);
        });
        if (evts.length) this.selectConj(evts[0], 0);
    },
    selectConj(e, i) {
        S.selectedConj = e;
        if (D.btnCdmExport) D.btnCdmExport.disabled = false;
        D.conjTbody.querySelectorAll('tr').forEach((tr, j) => tr.classList.toggle('selected', j === i));
        if (e.maneuver) {
            const m = e.maneuver, fc = m.fuel_cost_estimate;
            D.maneuverDetail.innerHTML = `<div class="mv-grid"><div class="mv-cell"><label>Δv</label><div class="mv-val ${fc}">${m.delta_v_m_s} m/s</div></div><div class="mv-cell"><label>FUEL</label><div class="mv-val ${fc}">${fc.toUpperCase()}</div></div><div class="mv-cell"><label>EXECUTE</label><div class="mv-val">${m.execute_minutes_before_tca}m PRE-TCA</div></div><div class="mv-cell"><label>OFFSET</label><div class="mv-val">${m.target_offset_km} km</div></div><div class="mv-cell full"><label>DIRECTION</label><div class="mv-val" style="font-size:9px">${m.direction.toUpperCase()}</div></div></div><div class="mv-note">${m.note}</div>`;
        } else {
            D.maneuverDetail.innerHTML = `<div class="mv-grid"><div class="mv-cell"><label>STATUS</label><div class="mv-val" style="color:var(--green)">NO CA REQUIRED</div></div><div class="mv-cell"><label>MISS</label><div class="mv-val">${e.miss_distance_km.toFixed(2)} KM</div></div></div>`;
        }
    },

    async propagate() {
        if (!S.primary) return;
        Log.add(`SGP4: ${S.primary.name}`); // 3
        try { // 3
            const r = await API.predict(S.primary.norad_id, 1, 1440); // 3
            S.predictions = r.data; // 3
            GlobeCtrl.showPath(r.data); // 3
            Log.ok(`${r.data.length} ORBITAL PTS`);
        } catch (e) { Log.err(e.message); }
    },

    // Advisories
    async loadAdvisories() {
        try {
            const r = await API.advisories();
            S.advisories = r.data;
            this.renderAdvisories(r.data);
            if (D.advCount) D.advCount.textContent = r.data.length;
            if (r.data.length) Log.warn(`${r.data.length} ACTIVE ADVISORY(S)`);
        } catch (e) { if (D.advisoryList) D.advisoryList.innerHTML = '<p class="null-state">UNAVAILABLE</p>'; }
    },
    renderAdvisories(advs) {
        if (!D.advisoryList) return;
        if (!advs.length) { D.advisoryList.innerHTML = '<p class="null-state">ALL CLEAR — NO ADVISORIES</p>'; return; }
        D.advisoryList.innerHTML = '';
        advs.forEach(a => {
            const card = document.createElement('div');
            card.className = `adv-card sev-${a.severity}`;
            card.innerHTML = `<span class="adv-sev ${a.severity}">${a.severity.toUpperCase()}</span><div class="adv-title">${a.title}</div><div class="adv-msg">${a.message.substring(0, 150)}${a.message.length > 150 ? '...' : ''}</div><div class="adv-orbits">AFFECTS: ${a.affected_orbits}</div>`;
            D.advisoryList.appendChild(card);
        });
    },

    // Decay
    async loadDecayAlerts() {
        try {
            const group = D.inGlobeGroup ? D.inGlobeGroup.value : 'fengyun-1c-debris';
            const r = await API.decay(group, 365);
            S.decayAlerts = r.data;
            this.renderDecayAlerts(r.data.slice(0, 10));
            if (D.decayCount) D.decayCount.textContent = r.data.length;
            if (r.data.length) Log.data(`${r.data.length} DECAYING OBJECT(S) IN ${group.toUpperCase()}`);
        } catch (e) { if (D.decayList) D.decayList.innerHTML = '<p class="null-state">UNAVAILABLE</p>'; }
    },
    renderDecayAlerts(items) {
        if (!D.decayList) return;
        if (!items.length) { D.decayList.innerHTML = '<p class="null-state">NO IMMINENT DECAY</p>'; return; }
        D.decayList.innerHTML = '';
        items.forEach(d => {
            const div = document.createElement('div');
            div.className = `decay-item ${d.risk_level}`;
            const daysText = d.days_to_reentry < 365 ? `${Math.round(d.days_to_reentry)}d` : `${(d.days_to_reentry / 365).toFixed(1)}y`;
            div.innerHTML = `<span class="decay-name">${d.name}</span><span class="decay-days ${d.risk_level}">${daysText}</span><span class="decay-rate">${d.decay_rate_km_day} km/d</span>`;
            D.decayList.appendChild(div);
        });
    },

    // CDM Export
    async exportCDM() {
        if (!S.selectedConj || !S.primary) return;
        try {
            Log.add(`CDM: ${S.primary.norad_id} ↔ ${S.selectedConj.secondary_norad_id}`);
            const text = await API.cdmText(S.primary.norad_id, S.selectedConj.secondary_norad_id);
            const blob = new Blob([text], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `CDM_${S.primary.norad_id}_${S.selectedConj.secondary_norad_id}.txt`;
            a.click();
            URL.revokeObjectURL(url);
            Log.ok('CDM EXPORTED');
        } catch (e) { Log.err(`CDM: ${e.message}`); }
    },
};

// Bindings
D.searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') Act.search(); });
D.btnSearch.addEventListener('click', () => Act.search());
document.addEventListener('click', e => { if (!e.target.closest('#search-pane,#sat-popup')) { D.searchResults.classList.add('hidden'); } });
D.satPopup.addEventListener('click', e => { if (e.target === D.satPopup) D.satPopup.classList.add('hidden'); });
D.btnScreen.addEventListener('click', () => Act.screen());
D.btnPropagate.addEventListener('click', () => Act.propagate());
D.btnLoadObjects.addEventListener('click', () => { Act.loadObjects(); Act.loadDecayAlerts(); });
if (D.btnCdmExport) D.btnCdmExport.addEventListener('click', () => Act.exportCDM());
if (D.btnSwathToggle) D.btnSwathToggle.addEventListener('click', () => {
    const show = !S.showSwath;
    GlobeCtrl.toggleSwath(show);
    D.btnSwathToggle.textContent = show ? '◉ SWATH ON' : '○ SWATH OFF';
    D.btnSwathToggle.classList.toggle('active', show);
    Log.add(show ? 'SCAN SWATH ENABLED' : 'SCAN SWATH DISABLED');
});
if (D.quickPick) D.quickPick.addEventListener('change', () => {
    const val = D.quickPick.value;
    if (val) { D.searchInput.value = val; Act.search(); D.quickPick.value = ''; }
});
// Time control
D.btnLive.addEventListener('click', () => { S.liveMode = true; D.btnLive.classList.add('active'); D.btnHist.classList.remove('active'); D.timeSliderWrap.classList.add('hidden'); S.timeOffset = 0; });
D.btnHist.addEventListener('click', () => { S.liveMode = false; D.btnHist.classList.add('active'); D.btnLive.classList.remove('active'); D.timeSliderWrap.classList.remove('hidden'); });
D.timeOffset.addEventListener('input', e => { S.timeOffset = +e.target.value; D.timeOffsetVal.textContent = `${S.timeOffset > 0 ? '+' : ''}${S.timeOffset}h`; });

// Boot
async function boot() {
    try {
        const confRes = await fetch('/api/v1/config');
        const confData = await confRes.json();
        if (confData?.data?.CESIUM_ION_TOKEN) {
            Cesium.Ion.defaultAccessToken = confData.data.CESIUM_ION_TOKEN;
        }
    } catch (e) {
        console.warn("Failed to load config", e);
    }
    
    await GlobeCtrl.init();
    Log.add('C2 v5.0 INITIALIZED — MISSION-CRITICAL SSA');
    Log.add('Pc ENGINE | CDM GENERATION | DECAY PREDICTION | ADVISORIES');
    Log.add('QUERY SATELLITE OR LOAD OBJECTS TO BEGIN');
    await Promise.all([Act.loadWeather(), Act.loadAdvisories(), Act.loadDecayAlerts()]);
    setInterval(() => { Act.loadWeather(); Act.loadAdvisories(); }, 60000);
}
boot();
