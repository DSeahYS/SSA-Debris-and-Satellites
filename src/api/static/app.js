/**
 * GOD'S EYE — C2 Interface Controller
 * Manages satellite search, conjunction screening, threat board,
 * maneuver recommendations, and operational status.
 */

// ═══════════════════════════════════════
// STATE
// ═══════════════════════════════════════
const S = {
    primary: null,
    conjunctions: [],
    predictions: [],
    weather: null,
    screening: false,
    logCount: 0,
};

// ═══════════════════════════════════════
// DOM
// ═══════════════════════════════════════
const $ = id => document.getElementById(id);

const D = {
    // Clocks
    utcClock: $('utc-clock'), localClock: $('local-clock'), mjdClock: $('mjd-clock'),
    // Threat
    threatVal: $('threat-val'), threatLevel: $('threat-level'),
    apiDot: $('api-dot'), apiLabel: $('api-label'),
    // Search
    searchInput: $('search-input'), btnSearch: $('btn-search'), searchResults: $('search-results'),
    // Satellite
    satDetail: $('sat-detail'), priStatus: $('pri-status'),
    // Environment
    envKp: $('env-kp'), envF107: $('env-f107'), envStorm: $('env-storm'),
    envDrag: $('env-drag'), envTs: $('env-ts'),
    // Screening
    inThreshold: $('in-threshold'), inHours: $('in-hours'), inStep: $('in-step'),
    inCatalog: $('in-catalog'),
    btnScreen: $('btn-screen'), btnPropagate: $('btn-propagate'),
    screenStatus: $('screen-status'),
    // Globe
    globeSub: $('globe-sub'),
    // Event Log
    eventLog: $('event-log'), logCountEl: $('log-count'),
    // Threat Board
    conjCount: $('conj-count'), conjTbody: $('conj-tbody'),
    tsCrit: $('ts-crit'), tsWarn: $('ts-warn'), tsCaut: $('ts-caut'), tsNom: $('ts-nom'),
    // Maneuver
    maneuverDetail: $('maneuver-detail'),
    // Stats
    statScreened: $('stat-screened'), statApproaches: $('stat-approaches'),
    statSource: $('stat-source'), statEpoch: $('stat-epoch'),
    // Globe
    globeContainer: $('globeViz'),
};

// ═══════════════════════════════════════
// CLOCKS
// ═══════════════════════════════════════
function updateClocks() {
    const now = new Date();
    D.utcClock.textContent = now.toISOString().substring(11, 19) + 'Z';
    D.localClock.textContent = now.toLocaleTimeString('en-GB');
    // Modified Julian Date
    const jd = (now.getTime() / 86400000) + 2440587.5;
    const mjd = jd - 2400000.5;
    D.mjdClock.textContent = mjd.toFixed(3);
}
setInterval(updateClocks, 1000);
updateClocks();

// ═══════════════════════════════════════
// API
// ═══════════════════════════════════════
const API = {
    async get(url) {
        const r = await fetch(url);
        const j = await r.json();
        if (!r.ok) throw new Error(j.error?.message || `HTTP ${r.status}`);
        return j;
    },
    search(q) { return this.get(`/api/v1/search?q=${encodeURIComponent(q)}`); },
    weather() { return this.get('/api/v1/space-weather'); },
    conjunctions(id, thresh, hrs, groups) {
        return this.get(`/api/v1/conjunctions?norad_id=${id}&threshold_km=${thresh}&hours=${hrs}&screen_groups=${encodeURIComponent(groups)}`);
    },
    predict(id, days, steps) {
        let u = `/api/v1/predict/baseline?days=${days}&steps_per_day=${steps}`;
        if (id) u += `&norad_id=${id}`;
        return this.get(u);
    },
};

// ═══════════════════════════════════════
// GLOBE
// ═══════════════════════════════════════
const GlobeCtrl = {
    w: null,
    init() {
        this.w = Globe()(D.globeContainer)
            .globeImageUrl('//unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
            .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
            .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
            .atmosphereColor('#00d4ff')
            .atmosphereAltitude(0.15)
            .pointOfView({ altitude: 2.2 });
        this.w.controls().autoRotate = true;
        this.w.controls().autoRotateSpeed = 0.15;
    },
    showPath(data) {
        if (!data?.length) { this.w.pathsData([]); return; }
        this.w.pathsData([data.map(p => [p.lat, p.lng, p.alt])])
            .pathColor(() => 'rgba(0, 212, 255, 0.7)')
            .pathDashLength(0.006)
            .pathDashGap(0.002)
            .pathDashAnimateTime(80000)
            .pathStroke(2);
    },
    clear() { this.w.pathsData([]); },
};

// ═══════════════════════════════════════
// LOG
// ═══════════════════════════════════════
const Log = {
    add(msg, cls = '') {
        S.logCount++;
        const d = document.createElement('div');
        d.className = `ev ${cls}`;
        const ts = new Date().toISOString().substring(11, 19);
        d.innerHTML = `<span class="ev-ts">${ts}Z</span><span class="ev-msg">${msg}</span>`;
        D.eventLog.appendChild(d);
        D.eventLog.scrollTop = D.eventLog.scrollHeight;
        D.logCountEl.textContent = `${S.logCount} ENTRIES`;
    },
    ok(m) { this.add(m, 'ok'); },
    err(m) { this.add(`ERR: ${m}`, 'err'); },
    warn(m) { this.add(m, 'warn'); },
    data(m) { this.add(m, 'data'); },
};

// ═══════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════
const Act = {
    // --- Search ---
    async search() {
        const q = D.searchInput.value.trim();
        if (!q) return;
        Log.add(`QUERY: "${q}"`);
        try {
            const res = await API.search(q);
            this.renderSearch(res.data);
            Log.data(`${res.data.length} RESULT(S)`);
        } catch (e) { Log.err(e.message); }
    },

    renderSearch(results) {
        D.searchResults.innerHTML = '';
        if (!results.length) {
            D.searchResults.innerHTML = '<div class="sr-item null-state">NO RESULTS</div>';
            D.searchResults.classList.remove('hidden');
            return;
        }
        results.slice(0, 20).forEach(s => {
            const d = document.createElement('div');
            d.className = 'sr-item';
            d.innerHTML = `<div class="sr-name">${s.name}</div>
                <div class="sr-meta">${s.norad_id} · ${s.periapsis_km}×${s.apoapsis_km} km · ${s.inclination}° · ${s.group}</div>`;
            d.onclick = () => this.selectSat(s);
            D.searchResults.appendChild(d);
        });
        D.searchResults.classList.remove('hidden');
    },

    // --- Select Satellite ---
    selectSat(sat) {
        S.primary = sat;
        D.searchResults.classList.add('hidden');
        D.searchInput.value = sat.name;
        D.priStatus.textContent = 'TRACKING';
        D.priStatus.style.color = '#00ff88';

        // Detail panel
        D.satDetail.innerHTML = `
            <div class="det-title">${sat.name}</div>
            <div class="det-row">
                <div class="det-cell"><label>NORAD CAT ID</label><div class="det-val">${sat.norad_id}</div></div>
                <div class="det-cell"><label>CATALOG GROUP</label><div class="det-val">${sat.group.toUpperCase()}</div></div>
            </div>
            <div class="det-row">
                <div class="det-cell"><label>PERIAPSIS</label><div class="det-val">${sat.periapsis_km} km</div></div>
                <div class="det-cell"><label>APOAPSIS</label><div class="det-val">${sat.apoapsis_km} km</div></div>
            </div>
            <div class="det-row">
                <div class="det-cell"><label>INCLINATION</label><div class="det-val">${sat.inclination}°</div></div>
                <div class="det-cell"><label>PERIOD</label><div class="det-val">${sat.period_min} min</div></div>
            </div>
            <div class="det-row">
                <div class="det-cell full"><label>EPOCH</label><div class="det-val">${sat.epoch}</div></div>
            </div>
            <div class="det-row">
                <div class="det-cell"><label>ORBIT TYPE</label><div class="det-val">${sat.periapsis_km < 2000 ? 'LEO' : sat.periapsis_km < 35786 ? 'MEO' : 'GEO'}</div></div>
                <div class="det-cell"><label>ALTITUDE BAND</label><div class="det-val">${Math.round(sat.periapsis_km)}-${Math.round(sat.apoapsis_km)} km</div></div>
            </div>
        `;

        D.btnScreen.disabled = false;
        D.btnPropagate.disabled = false;
        D.screenStatus.textContent = `TARGET: ${sat.name} (${sat.norad_id})`;
        D.globeSub.textContent = sat.name;
        D.statEpoch.textContent = sat.epoch.substring(0, 10);

        Log.ok(`TARGET ACQUIRED: ${sat.name} [${sat.norad_id}]`);
        this.propagate();
    },

    // --- Space Weather ---
    async loadWeather() {
        try {
            const res = await API.weather();
            const w = res.data;
            S.weather = w;
            D.envKp.textContent = w.kp_index?.toFixed(1) ?? '—';
            D.envF107.textContent = w.f107_flux?.toFixed(0) ?? '—';
            const st = (w.storm_level || '—').toUpperCase().replace('_', ' ');
            D.envStorm.textContent = st;
            D.envTs.textContent = `LAST UPDATE: ${w.timestamp || '—'}`;

            // Color
            const cls = w.storm_level === 'quiet' ? 'quiet' : w.storm_level === 'unsettled' ? 'unsettled' : w.storm_level === 'storm' ? 'storm' : 'severe';
            D.envKp.className = `env-val ${cls}`;
            D.envStorm.className = `env-val ${cls}`;

            // Drag estimate based on Kp
            const dragPct = w.kp_index < 3 ? '<5%' : w.kp_index < 5 ? '5-20%' : w.kp_index < 7 ? '20-100%' : '>100%';
            D.envDrag.textContent = dragPct;
            D.envDrag.className = `env-val ${cls}`;

            D.apiDot.className = 'status-dot green';
            D.apiLabel.textContent = 'NOMINAL';
        } catch (e) {
            D.apiDot.className = 'status-dot red';
            D.apiLabel.textContent = 'FAULT';
            Log.err(`SWPC: ${e.message}`);
        }
    },

    // --- Conjunction Screening ---
    async screen() {
        if (!S.primary || S.screening) return;
        S.screening = true;
        D.btnScreen.disabled = true;
        D.screenStatus.textContent = '⏳ SCREENING IN PROGRESS...';

        const thresh = +D.inThreshold.value;
        const hrs = +D.inHours.value;
        const groups = D.inCatalog.value;

        Log.warn(`SCREENING: ${S.primary.name} · ${thresh}km · ${hrs}h`);

        try {
            const res = await API.conjunctions(S.primary.norad_id, thresh, hrs, groups);
            S.conjunctions = res.data;
            this.renderThreatBoard(res.data, res.meta);
            Log.ok(`COMPLETE: ${res.meta.total_screened} OBJECTS SCREENED → ${res.data.length} CONJUNCTION(S)`);

            D.statScreened.textContent = res.meta.total_screened;
            D.statApproaches.textContent = res.data.length;

            // Update threat posture
            const hasCrit = res.data.some(c => c.risk_level === 'critical');
            const hasWarn = res.data.some(c => c.risk_level === 'warning');
            const hasCaut = res.data.some(c => c.risk_level === 'caution');
            if (hasCrit) {
                D.threatVal.textContent = 'CRITICAL'; D.threatVal.className = 'threat-critical';
            } else if (hasWarn) {
                D.threatVal.textContent = 'ELEVATED'; D.threatVal.className = 'threat-warning';
            } else if (hasCaut) {
                D.threatVal.textContent = 'CAUTION'; D.threatVal.className = 'threat-caution';
            } else {
                D.threatVal.textContent = 'NOMINAL'; D.threatVal.className = 'threat-nominal';
            }
        } catch (e) {
            Log.err(e.message);
        } finally {
            S.screening = false;
            D.btnScreen.disabled = false;
            D.screenStatus.textContent = `TARGET: ${S.primary.name} (${S.primary.norad_id})`;
        }
    },

    renderThreatBoard(events, meta) {
        D.conjCount.textContent = events.length;

        // Summary counts
        D.tsCrit.textContent = events.filter(e => e.risk_level === 'critical').length;
        D.tsWarn.textContent = events.filter(e => e.risk_level === 'warning').length;
        D.tsCaut.textContent = events.filter(e => e.risk_level === 'caution').length;
        D.tsNom.textContent = events.filter(e => e.risk_level === 'nominal').length;

        D.conjTbody.innerHTML = '';
        if (!events.length) {
            D.conjTbody.innerHTML = `<tr><td colspan="8" class="null-state">ALL CLEAR — NO CONJUNCTIONS WITHIN ${meta.threshold_km} KM / ${meta.hours}H</td></tr>`;
            D.maneuverDetail.innerHTML = '<p class="null-state">NO CONJUNCTION EVENTS — NO CA REQUIRED</p>';
            return;
        }

        events.forEach((e, i) => {
            const tr = document.createElement('tr');
            const tcaShort = e.tca ? e.tca.substring(5, 19).replace('T', ' ') : '—';
            tr.innerHTML = `
                <td><span class="lvl-dot lvl-${e.risk_level}"></span>${e.risk_level.substr(0, 4).toUpperCase()}</td>
                <td title="NORAD ${e.secondary_norad_id}">${e.secondary_name}</td>
                <td><strong>${e.miss_distance_km.toFixed(2)}</strong></td>
                <td>${e.radial_km.toFixed(2)}</td>
                <td>${e.in_track_km.toFixed(2)}</td>
                <td>${e.cross_track_km.toFixed(2)}</td>
                <td>${e.relative_velocity_km_s.toFixed(2)}</td>
                <td>${tcaShort}</td>
            `;
            tr.onclick = () => this.selectConjunction(e, i);
            D.conjTbody.appendChild(tr);
        });

        if (events.length > 0) this.selectConjunction(events[0], 0);
    },

    selectConjunction(evt, idx) {
        D.conjTbody.querySelectorAll('tr').forEach((tr, i) => tr.classList.toggle('selected', i === idx));

        if (evt.maneuver) {
            const m = evt.maneuver;
            const fc = m.fuel_cost_estimate;
            D.maneuverDetail.innerHTML = `
                <div class="mv-grid">
                    <div class="mv-cell"><label>DELTA-V REQUIRED</label><div class="mv-val ${fc}">${m.delta_v_m_s} m/s</div></div>
                    <div class="mv-cell"><label>FUEL COST</label><div class="mv-val ${fc}">${fc.toUpperCase()}</div></div>
                    <div class="mv-cell"><label>EXECUTE AT</label><div class="mv-val">${m.execute_minutes_before_tca} MIN BEFORE TCA</div></div>
                    <div class="mv-cell"><label>TARGET OFFSET</label><div class="mv-val">${m.target_offset_km} KM</div></div>
                    <div class="mv-cell full"><label>BURN DIRECTION</label><div class="mv-val" style="font-size:10px">${m.direction.toUpperCase()}</div></div>
                </div>
                <div class="mv-note">${m.note}</div>
            `;
        } else {
            D.maneuverDetail.innerHTML = `
                <div class="mv-grid">
                    <div class="mv-cell"><label>ASSESSMENT</label><div class="mv-val" style="color:var(--green)">NO MANEUVER REQUIRED</div></div>
                    <div class="mv-cell"><label>MISS DISTANCE</label><div class="mv-val">${evt.miss_distance_km.toFixed(2)} KM</div></div>
                    <div class="mv-cell"><label>RISK LEVEL</label><div class="mv-val">${evt.risk_level.toUpperCase()}</div></div>
                    <div class="mv-cell"><label>REL. VELOCITY</label><div class="mv-val">${evt.relative_velocity_km_s.toFixed(2)} KM/S</div></div>
                </div>
            `;
        }
    },

    // --- Propagate Orbit ---
    async propagate() {
        if (!S.primary) return;
        Log.add(`PROPAGATING: ${S.primary.name}`);
        try {
            const res = await API.predict(S.primary.norad_id, 1, 96);
            S.predictions = res.data;
            GlobeCtrl.showPath(res.data);
            D.globeSub.textContent = `${S.primary.name} — ${res.data.length} PTS`;
            Log.ok(`${res.data.length} ORBITAL POINTS RENDERED`);
        } catch (e) { Log.err(e.message); }
    },
};

// ═══════════════════════════════════════
// BINDINGS
// ═══════════════════════════════════════
D.searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') Act.search(); });
D.btnSearch.addEventListener('click', () => Act.search());
document.addEventListener('click', e => {
    if (!e.target.closest('#search-pane')) D.searchResults.classList.add('hidden');
});
D.btnScreen.addEventListener('click', () => Act.screen());
D.btnPropagate.addEventListener('click', () => Act.propagate());

// ═══════════════════════════════════════
// BOOT
// ═══════════════════════════════════════
async function boot() {
    GlobeCtrl.init();
    Log.add('SYSTEM INITIALIZED — GOD\'S EYE C2 v3.1');
    Log.add('ENTER SATELLITE NAME OR NORAD ID TO BEGIN');
    await Act.loadWeather();
    D.apiDot.className = 'status-dot green';
    D.apiLabel.textContent = 'NOMINAL';
    setInterval(() => Act.loadWeather(), 60000);
}
boot();
