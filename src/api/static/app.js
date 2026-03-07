/**
 * God's Eye SSA Platform — Frontend App (v2)
 * Real satellite data from CelesTrak + NOAA SWPC space weather.
 * Architecture: State → Services → Actions → Events → Bootstrap.
 */

// --- 1. State Management ---
const state = {
    catalog: [],
    predictions: [],
    isLoading: false,
    selectedNoradId: null,
    selectedGroup: 'stations',
    weather: null,
    settings: { days: 1, steps: 24 },
};

// --- 2. DOM Elements ---
const El = {
    groupSelect: document.getElementById('group-select'),
    satSelect: document.getElementById('sat-select'),
    btnLoadCatalog: document.getElementById('btn-load-catalog'),
    daysInput: document.getElementById('prediction-days'),
    daysValue: document.getElementById('days-value'),
    stepsInput: document.getElementById('steps-per-day'),
    stepsValue: document.getElementById('steps-value'),
    btnBaseline: document.getElementById('btn-baseline'),
    btnClear: document.getElementById('btn-clear'),
    terminal: document.getElementById('terminal'),
    globeContainer: document.getElementById('globeViz'),
    kpValue: document.getElementById('kp-value'),
    f107Value: document.getElementById('f107-value'),
    stormValue: document.getElementById('storm-value'),
    kpCard: document.getElementById('kp-card'),
    stormCard: document.getElementById('storm-card'),
    sourceBadge: document.getElementById('data-source-badge'),
};

// --- 3. Services ---
const GlobeService = {
    world: null,
    init() {
        this.world = Globe()(El.globeContainer)
            .globeImageUrl('//unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
            .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
            .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
            .pointOfView({ altitude: 3.0 });
        this.world.controls().autoRotate = true;
        this.world.controls().autoRotateSpeed = 0.3;
    },
    updatePaths(predictions) {
        if (!predictions || predictions.length === 0) {
            this.world.pathsData([]);
            return;
        }
        const pathData = [predictions.map(p => [p.lat, p.lng, p.alt])];
        this.world.pathsData(pathData)
            .pathColor(() => 'rgba(56, 189, 248, 0.85)')
            .pathDashLength(0.01)
            .pathDashGap(0.004)
            .pathDashAnimateTime(80000)
            .pathStroke(2);
    },
    clear() { this.world.pathsData([]); }
};

const Logger = {
    log(msg, type = 'system') {
        const line = document.createElement('div');
        line.className = `log-line ${type}`;
        const ts = new Date().toLocaleTimeString();
        line.textContent = `[${ts}] ${msg}`;
        El.terminal.appendChild(line);
        El.terminal.scrollTop = El.terminal.scrollHeight;
    },
    error(msg) { this.log(`ERROR: ${msg}`, 'error'); },
    success(msg) { this.log(msg, 'success'); },
    data(msg) { this.log(msg, 'data'); },
};

const ApiService = {
    async get(url) {
        const res = await fetch(url);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error?.message || `HTTP ${res.status}`);
        }
        return (await res.json()).data;
    },
    fetchCatalog(group) { return this.get(`/api/v1/catalog?group=${group}`); },
    fetchWeather() { return this.get('/api/v1/space-weather'); },
    fetchPredictions(noradId, group, days, steps) {
        let url = `/api/v1/predict/baseline?days=${days}&steps_per_day=${steps}`;
        if (noradId) url += `&norad_id=${noradId}&group=${group}`;
        return this.get(url);
    },
};

// --- 4. Actions ---
const Actions = {
    updateSettings(key, value) {
        state.settings[key] = value;
        El.daysValue.textContent = `${state.settings.days} Day${state.settings.days > 1 ? 's' : ''}`;
        El.stepsValue.textContent = `${state.settings.steps} Steps`;
    },

    async loadCatalog() {
        const group = El.groupSelect.value;
        state.selectedGroup = group;
        Logger.log(`Loading catalog: ${group}...`);
        El.btnLoadCatalog.disabled = true;
        try {
            const catalog = await ApiService.fetchCatalog(group);
            state.catalog = catalog;
            // Populate dropdown
            El.satSelect.innerHTML = '';
            catalog.forEach(sat => {
                const opt = document.createElement('option');
                opt.value = sat.norad_id;
                opt.textContent = `${sat.name} (${sat.norad_id})`;
                El.satSelect.appendChild(opt);
            });
            if (catalog.length > 0) state.selectedNoradId = catalog[0].norad_id;
            Logger.success(`Loaded ${catalog.length} satellites in "${group}".`);
        } catch (e) {
            Logger.error(e.message);
        } finally {
            El.btnLoadCatalog.disabled = false;
        }
    },

    async loadWeather() {
        try {
            const w = await ApiService.fetchWeather();
            state.weather = w;
            El.kpValue.textContent = w.kp_index?.toFixed(1) ?? '—';
            El.f107Value.textContent = w.f107_flux?.toFixed(0) ?? '—';
            El.stormValue.textContent = (w.storm_level || '—').toUpperCase().replace('_', ' ');

            // Color-code
            El.kpCard.className = `weather-card ${w.storm_level}`;
            El.stormCard.className = `weather-card full-width ${w.storm_level}`;

            Logger.data(`Weather: Kp=${w.kp_index}, F10.7=${w.f107_flux} SFU → ${w.storm_level}`);
        } catch (e) {
            Logger.error(`Weather fetch failed: ${e.message}`);
        }
    },

    async runBaseline() {
        if (state.isLoading) return;
        state.isLoading = true;
        El.btnBaseline.disabled = true;

        const noradId = El.satSelect.value || null;
        const satName = El.satSelect.options[El.satSelect.selectedIndex]?.text || 'MOCK';
        Logger.log(`Propagating SGP4 for ${satName}, ${state.settings.days}d @ ${state.settings.steps} steps/day...`);

        try {
            const data = await ApiService.fetchPredictions(
                noradId, state.selectedGroup, state.settings.days, state.settings.steps
            );
            state.predictions = data;
            GlobeService.updatePaths(data);
            Logger.success(`Rendered ${data.length} points for ${satName}.`);
        } catch (e) {
            Logger.error(e.message);
        } finally {
            state.isLoading = false;
            El.btnBaseline.disabled = false;
        }
    },

    clearData() {
        state.predictions = [];
        GlobeService.clear();
        Logger.log('Cleared orbital paths.');
    },
};

// --- 5. Event Bindings ---
function bindEvents() {
    El.daysInput.addEventListener('input', e => Actions.updateSettings('days', +e.target.value));
    El.stepsInput.addEventListener('input', e => Actions.updateSettings('steps', +e.target.value));
    El.btnLoadCatalog.addEventListener('click', () => Actions.loadCatalog());
    El.btnBaseline.addEventListener('click', () => Actions.runBaseline());
    El.btnClear.addEventListener('click', () => Actions.clearData());
    El.satSelect.addEventListener('change', e => { state.selectedNoradId = +e.target.value; });
}

// --- 6. Bootstrap ---
async function bootstrap() {
    GlobeService.init();
    bindEvents();
    Logger.log('God\'s Eye v2 initialized. Loading live data...');

    // Load space weather and default catalog in parallel
    await Promise.all([
        Actions.loadWeather(),
        Actions.loadCatalog(),
    ]);

    // Auto-refresh weather every 60 seconds
    setInterval(() => Actions.loadWeather(), 60000);
}

bootstrap();
