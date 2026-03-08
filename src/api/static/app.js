/**
 * GOD'S EYE — C2 Interface Controller v5
 * Mission-critical SSA: Pc, CDM, advisories, decay alerts,
 * proper ECI→ECEF coordinates, and expanded weather.
 */

const S = { primary: null, conjunctions: [], predictions: [], weather: null, screening: false, logCount: 0, objects: [], liveMode: true, timeOffset: 0, advisories: [], decayAlerts: [], selectedConj: null };
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
    init() {
        this.w = Globe()(D.globeContainer)
            .globeImageUrl('//unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
            .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
            .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
            .atmosphereColor('#00d4ff')
            .atmosphereAltitude(0.12)
            .pointOfView({ altitude: 2.0 });
        // Slow rotation
        this.w.controls().autoRotate = true;
        this.w.controls().autoRotateSpeed = 0.05;
        // Points click handler
        this.w.onPointClick(p => Act.clickObject(p));
    },
    showPoints(data) {
        this.w.pointsData(data)
            .pointLat(d => d.lat)
            .pointLng(d => d.lng)
            .pointAltitude(d => Math.min(d.alt_km / 40000, 0.15))
            .pointRadius(d => d.norad_id === S.primary?.norad_id ? 0.4 : 0.15)
            .pointColor(d => {
                if (d.norad_id === S.primary?.norad_id) return '#00ff88';
                if (d.name.includes('DEB')) return '#ff4466';
                if (d.name.includes('R/B')) return '#ff8800';
                return '#00d4ff';
            })
            .pointLabel(d => `${d.name} (${d.norad_id})`)
            .pointResolution(6);
    },
    showPath(data) {
        if (!data?.length) { this.w.pathsData([]); return; }
        this.w.pathsData([data.map(p => [p.lat, p.lng, p.alt])])
            .pathColor(() => 'rgba(0, 255, 136, 0.6)')
            .pathDashLength(0.01)
            .pathDashGap(0.005)
            .pathDashAnimateTime(200000)
            .pathStroke(1.5);
    },
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
            d.onclick = () => this.selectSat(s);
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
        D.satPopup.classList.remove('hidden');
        D.popupContent.innerHTML = `
            <div class="det-title" style="font-size:11px">${pt.name}</div>
            <div class="det-row"><div class="det-cell"><label>NORAD</label><div class="det-val">${pt.norad_id}</div></div><div class="det-cell"><label>ALT</label><div class="det-val">${pt.alt_km} km</div></div></div>
            <div class="det-row"><div class="det-cell"><label>LAT</label><div class="det-val">${pt.lat.toFixed(2)}°</div></div><div class="det-cell"><label>LNG</label><div class="det-val">${pt.lng.toFixed(2)}°</div></div></div>
            <div class="det-row"><div class="det-cell"><label>PERIAPSIS</label><div class="det-val">${pt.periapsis_km} km</div></div><div class="det-cell"><label>APOAPSIS</label><div class="det-val">${pt.apoapsis_km} km</div></div></div>
            <div class="det-row"><div class="det-cell"><label>INCL</label><div class="det-val">${pt.inclination}°</div></div><div class="det-cell"><label>PERIOD</label><div class="det-val">${pt.period_min} min</div></div></div>
            <div style="padding:4px;margin-top:4px"><button class="cmd-btn cmd-primary" onclick="Act.selectSat({norad_id:${pt.norad_id},name:'${pt.name.replace(/'/g, "\\'")}',group:'${D.inGlobeGroup.value}',periapsis_km:${pt.periapsis_km},apoapsis_km:${pt.apoapsis_km},inclination:${pt.inclination},period_min:${pt.period_min}});document.getElementById('sat-popup').classList.add('hidden')">SET AS PRIMARY</button></div>
        `;
        Log.data(`INSPECT: ${pt.name} [${pt.norad_id}] @ ${pt.alt_km} km`);
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
        Log.add(`SGP4: ${S.primary.name}`);
        try {
            const r = await API.predict(S.primary.norad_id, 1, 96);
            S.predictions = r.data;
            GlobeCtrl.showPath(r.data);
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
    GlobeCtrl.init();
    Log.add('C2 v5.0 INITIALIZED — MISSION-CRITICAL SSA');
    Log.add('Pc ENGINE | CDM GENERATION | DECAY PREDICTION | ADVISORIES');
    Log.add('QUERY SATELLITE OR LOAD OBJECTS TO BEGIN');
    await Promise.all([Act.loadWeather(), Act.loadAdvisories(), Act.loadDecayAlerts()]);
    setInterval(() => { Act.loadWeather(); Act.loadAdvisories(); }, 60000);
}
boot();
