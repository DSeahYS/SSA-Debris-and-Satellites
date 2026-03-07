/**
 * God's Eye SSA — Operational Frontend (v3)
 * Satellite search → Conjunction screening → Risk alerts → Maneuver recommendations
 */

// --- State ---
const state = {
    primarySat: null,       // { norad_id, name, group, ... }
    searchResults: [],
    conjunctions: [],
    predictions: [],
    weather: null,
    isScreening: false,
    settings: { days: 1, steps: 48, threshold: 50, hours: 24 },
};

// --- DOM ---
const $ = id => document.getElementById(id);
const El = {
    searchInput: $('search-input'),
    btnSearch: $('btn-search'),
    searchResults: $('search-results'),
    primaryInfo: $('primary-info'),
    kpValue: $('kp-value'),
    f107Value: $('f107-value'),
    stormValue: $('storm-value'),
    kpCard: $('kp-card'),
    stormCard: $('storm-card'),
    weatherBadge: $('weather-badge'),
    thresholdInput: $('threshold-input'),
    hoursInput: $('hours-input'),
    screenGroups: $('screen-groups'),
    btnScreen: $('btn-screen'),
    screenHint: $('screen-hint'),
    btnPredict: $('btn-predict'),
    predDays: $('pred-days'),
    predSteps: $('pred-steps'),
    daysVal: $('days-val'),
    stepsVal: $('steps-val'),
    conjTbody: $('conjunction-tbody'),
    eventCount: $('event-count'),
    maneuverInfo: $('maneuver-info'),
    alertBanner: $('alert-banner'),
    alertText: $('alert-text'),
    terminal: $('terminal'),
    globeContainer: $('globeViz'),
};

// --- Services ---
const Api = {
    async get(url) {
        const r = await fetch(url);
        const j = await r.json();
        if (!r.ok) throw new Error(j.error?.message || `HTTP ${r.status}`);
        return j;
    },
    search(q) { return this.get(`/api/v1/search?q=${encodeURIComponent(q)}`); },
    weather() { return this.get('/api/v1/space-weather'); },
    conjunctions(noradId, threshold, hours, groups) {
        return this.get(`/api/v1/conjunctions?norad_id=${noradId}&threshold_km=${threshold}&hours=${hours}&screen_groups=${encodeURIComponent(groups)}`);
    },
    predict(noradId, days, steps) {
        let url = `/api/v1/predict/baseline?days=${days}&steps_per_day=${steps}`;
        if (noradId) url += `&norad_id=${noradId}`;
        return this.get(url);
    },
};

const Globe = {
    world: null,
    init() {
        this.world = window.Globe()(El.globeContainer)
            .globeImageUrl('//unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
            .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
            .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
            .pointOfView({ altitude: 2.5 });
        this.world.controls().autoRotate = true;
        this.world.controls().autoRotateSpeed = 0.2;
    },
    showPath(data, color = 'rgba(56, 189, 248, 0.8)') {
        if (!data || !data.length) { this.world.pathsData([]); return; }
        const paths = [data.map(p => [p.lat, p.lng, p.alt])];
        this.world.pathsData(paths)
            .pathColor(() => color)
            .pathDashLength(0.008)
            .pathDashGap(0.003)
            .pathDashAnimateTime(80000)
            .pathStroke(2.5);
    },
    clear() { this.world.pathsData([]); },
};

const Log = {
    add(msg, cls = '') {
        const d = document.createElement('div');
        d.className = `log-line ${cls}`;
        d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        El.terminal.appendChild(d);
        El.terminal.scrollTop = El.terminal.scrollHeight;
    },
    ok(m) { this.add(m, 'success'); },
    err(m) { this.add(`ERROR: ${m}`, 'error'); },
    warn(m) { this.add(m, 'warn'); },
    data(m) { this.add(m, 'data'); },
};

// --- Actions ---
const Actions = {
    async search() {
        const q = El.searchInput.value.trim();
        if (!q) return;
        Log.add(`Searching: "${q}"...`);
        try {
            const res = await Api.search(q);
            state.searchResults = res.data;
            this.renderSearchResults(res.data);
            Log.ok(`Found ${res.data.length} result(s).`);
        } catch (e) { Log.err(e.message); }
    },

    renderSearchResults(results) {
        El.searchResults.innerHTML = '';
        if (!results.length) {
            El.searchResults.innerHTML = '<div class="search-item muted">No satellites found.</div>';
            El.searchResults.classList.remove('hidden');
            return;
        }
        results.forEach(sat => {
            const div = document.createElement('div');
            div.className = 'search-item';
            div.innerHTML = `
                <div class="sat-name">${sat.name}</div>
                <div class="sat-meta">NORAD ${sat.norad_id} · ${sat.periapsis_km}×${sat.apoapsis_km} km · ${sat.inclination}° · ${sat.group}</div>
            `;
            div.addEventListener('click', () => this.selectSatellite(sat));
            El.searchResults.appendChild(div);
        });
        El.searchResults.classList.remove('hidden');
    },

    selectSatellite(sat) {
        state.primarySat = sat;
        El.searchResults.classList.add('hidden');
        El.searchInput.value = sat.name;

        // Update primary info panel
        El.primaryInfo.innerHTML = `
            <div class="sat-title">${sat.name}</div>
            <div class="stat-grid">
                <div class="stat-item"><label>NORAD ID</label><span class="stat-val">${sat.norad_id}</span></div>
                <div class="stat-item"><label>GROUP</label><span class="stat-val">${sat.group.toUpperCase()}</span></div>
                <div class="stat-item"><label>PERIAPSIS</label><span class="stat-val">${sat.periapsis_km} km</span></div>
                <div class="stat-item"><label>APOAPSIS</label><span class="stat-val">${sat.apoapsis_km} km</span></div>
                <div class="stat-item"><label>INCLINATION</label><span class="stat-val">${sat.inclination}°</span></div>
                <div class="stat-item"><label>PERIOD</label><span class="stat-val">${sat.period_min} min</span></div>
            </div>
        `;
        El.btnScreen.disabled = false;
        El.btnPredict.disabled = false;
        El.screenHint.textContent = `Ready to screen ${sat.name}.`;
        Log.ok(`Selected: ${sat.name} (NORAD ${sat.norad_id})`);

        // Auto-predict the orbit
        this.predict();
    },

    async loadWeather() {
        try {
            const res = await Api.weather();
            const w = res.data;
            state.weather = w;
            El.kpValue.textContent = w.kp_index?.toFixed(1) ?? '—';
            El.f107Value.textContent = w.f107_flux?.toFixed(0) ?? '—';
            El.stormValue.textContent = (w.storm_level || '—').toUpperCase().replace('_', ' ');
            El.kpCard.className = `weather-card ${w.storm_level}`;
            El.stormCard.className = `weather-card full-width ${w.storm_level}`;
            El.weatherBadge.textContent = `Kp ${w.kp_index?.toFixed(1)}`;
        } catch (e) { Log.err(`Weather: ${e.message}`); }
    },

    async runScreening() {
        if (!state.primarySat || state.isScreening) return;
        state.isScreening = true;
        El.btnScreen.disabled = true;
        El.btnScreen.textContent = '⏳ SCREENING...';

        const threshold = +El.thresholdInput.value;
        const hours = +El.hoursInput.value;
        const groups = El.screenGroups.value;

        Log.warn(`Screening ${state.primarySat.name} · ${threshold}km · ${hours}h · groups: ${groups}`);

        try {
            const res = await Api.conjunctions(state.primarySat.norad_id, threshold, hours, groups);
            state.conjunctions = res.data;
            this.renderConjunctions(res.data, res.meta);
            Log.ok(`Screened ${res.meta.total_screened} objects. Found ${res.data.length} close approach(es).`);

            // Show alert if any critical/warning
            const worst = res.data.find(c => c.risk_level === 'critical' || c.risk_level === 'warning');
            if (worst) {
                El.alertBanner.classList.remove('hidden');
                El.alertText.textContent = `⚠ CONJUNCTION ALERT: ${worst.secondary_name} — ${worst.miss_distance_km} km miss at ${worst.tca}`;
            } else {
                El.alertBanner.classList.add('hidden');
            }
        } catch (e) {
            Log.err(e.message);
        } finally {
            state.isScreening = false;
            El.btnScreen.disabled = false;
            El.btnScreen.textContent = '▶ RUN SCREENING';
        }
    },

    renderConjunctions(events, meta) {
        El.eventCount.textContent = events.length;
        El.conjTbody.innerHTML = '';

        if (!events.length) {
            El.conjTbody.innerHTML = `<tr><td colspan="6" class="muted">No close approaches within ${meta.threshold_km} km over ${meta.hours}h. ✓ Clear.</td></tr>`;
            El.maneuverInfo.innerHTML = '<p class="muted">No conjunction events — no maneuver needed.</p>';
            return;
        }

        events.forEach((evt, i) => {
            const tr = document.createElement('tr');
            const riskClass = `risk-${evt.risk_level}`;
            const tcaShort = evt.tca ? evt.tca.substring(5, 16).replace('T', ' ') : '—';
            tr.innerHTML = `
                <td><span class="risk-dot ${riskClass}"></span>${evt.risk_level.toUpperCase()}</td>
                <td title="NORAD ${evt.secondary_norad_id}">${evt.secondary_name}</td>
                <td><strong>${evt.miss_distance_km.toFixed(1)}</strong></td>
                <td class="ric-values">R:${evt.radial_km.toFixed(1)} I:${evt.in_track_km.toFixed(1)} C:${evt.cross_track_km.toFixed(1)}</td>
                <td>${evt.relative_velocity_km_s.toFixed(1)} km/s</td>
                <td>${tcaShort}</td>
            `;
            tr.addEventListener('click', () => this.selectConjunction(evt, i));
            El.conjTbody.appendChild(tr);
        });

        // Auto-select the most critical one
        if (events.length > 0) this.selectConjunction(events[0], 0);
    },

    selectConjunction(evt, idx) {
        // Highlight row
        El.conjTbody.querySelectorAll('tr').forEach((tr, i) => tr.classList.toggle('selected', i === idx));

        if (evt.maneuver) {
            const m = evt.maneuver;
            const fuelClass = m.fuel_cost_estimate === 'minimal' ? 'fuel-minimal' : m.fuel_cost_estimate === 'moderate' ? 'fuel-moderate' : 'fuel-significant';
            El.maneuverInfo.innerHTML = `
                <div class="maneuver-data">
                    <div class="mv-grid">
                        <div class="mv-item"><label>Δv REQUIRED</label><span class="mv-val ${fuelClass}">${m.delta_v_m_s} m/s</span></div>
                        <div class="mv-item"><label>DIRECTION</label><span class="mv-val" style="font-size:0.6rem">${m.direction}</span></div>
                        <div class="mv-item"><label>EXECUTE</label><span class="mv-val">${m.execute_minutes_before_tca} min before TCA</span></div>
                        <div class="mv-item"><label>FUEL COST</label><span class="mv-val ${fuelClass}">${m.fuel_cost_estimate.toUpperCase()}</span></div>
                        <div class="mv-item"><label>TARGET OFFSET</label><span class="mv-val">${m.target_offset_km} km</span></div>
                    </div>
                    <p class="mv-note">${m.note}</p>
                </div>
            `;
        } else {
            El.maneuverInfo.innerHTML = `
                <p class="muted">Risk: ${evt.risk_level.toUpperCase()} — miss ${evt.miss_distance_km.toFixed(1)} km.<br>No maneuver recommended at this risk level.</p>
            `;
        }
    },

    async predict() {
        if (!state.primarySat) return;
        const days = +El.predDays.value;
        const steps = +El.predSteps.value;
        Log.add(`Propagating ${state.primarySat.name} — ${days}d @ ${steps} steps/day...`);
        try {
            const res = await Api.predict(state.primarySat.norad_id, days, steps);
            state.predictions = res.data;
            Globe.showPath(res.data);
            Log.ok(`Rendered ${res.data.length} orbital points.`);
        } catch (e) { Log.err(e.message); }
    },
};

// --- Event Bindings ---
function bind() {
    El.searchInput.addEventListener('keydown', e => { if (e.key === 'Enter') Actions.search(); });
    El.btnSearch.addEventListener('click', () => Actions.search());
    document.addEventListener('click', e => {
        if (!e.target.closest('.search-container')) El.searchResults.classList.add('hidden');
    });
    El.btnScreen.addEventListener('click', () => Actions.runScreening());
    El.btnPredict.addEventListener('click', () => Actions.predict());
    El.predDays.addEventListener('input', e => { El.daysVal.textContent = e.target.value; });
    El.predSteps.addEventListener('input', e => { El.stepsVal.textContent = e.target.value; });
}

// --- Bootstrap ---
async function boot() {
    Globe.init();
    bind();
    Log.add('God\'s Eye v3 — Operational SSA initialized.');
    Log.add('Search for a satellite to begin conjunction assessment.');
    await Actions.loadWeather();
    setInterval(() => Actions.loadWeather(), 60000);
}

boot();
