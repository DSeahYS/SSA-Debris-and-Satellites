/**
 * God's Eye SSA Platform - Frontend App
 * Implements architectural patterns from everything-claude-code: 
 *  - State Management
 *  - Error Handling
 *  - Service encapsulation
 */

// --- 1. State Management ---
const state = {
    predictions: [],
    isLoading: false,
    error: null,
    settings: {
        days: 1,
        steps: 24
    }
};

// --- 2. DOM Elements & Initialization ---
const Elements = {
    daysInput: document.getElementById('prediction-days'),
    daysValue: document.getElementById('days-value'),
    stepsInput: document.getElementById('steps-per-day'),
    stepsValue: document.getElementById('steps-value'),
    btnBaseline: document.getElementById('btn-baseline'),
    btnPinn: document.getElementById('btn-pinn'),
    btnClear: document.getElementById('btn-clear'),
    terminal: document.getElementById('terminal'),
    globeContainer: document.getElementById('globeViz')
};

// --- 3. View/Globe Service ---
const GlobeService = {
    world: null,

    init() {
        this.world = Globe()(Elements.globeContainer)
            .globeImageUrl('//unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
            .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
            .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
            .pointOfView({ altitude: 3.5 });

        this.world.controls().autoRotate = true;
        this.world.controls().autoRotateSpeed = 0.5;
    },

    updatePaths(predictions) {
        if (!predictions || predictions.length === 0) {
            this.world.pathsData([]);
            return;
        }

        // Map predictions directly to Globe.gl format [[lat, lng, alt]]
        const pathData = [predictions.map(p => ([p.lat, p.lng, p.alt]))];

        this.world.pathsData(pathData)
            .pathColor(() => 'rgba(56, 189, 248, 0.8)') // Tailwind sky-400
            .pathDashLength(0.01)
            .pathDashGap(0.004)
            .pathDashAnimateTime(100000)
            .pathStroke(1.5);
    },

    clear() {
        this.world.pathsData([]);
    }
};

// --- 4. Sub-systems ---
const Logger = {
    log(message, type = 'system') {
        const line = document.createElement('div');
        line.className = `log-line ${type}`;
        const timestamp = new Date().toLocaleTimeString();
        line.textContent = `[${timestamp}] ${message}`;
        Elements.terminal.appendChild(line);
        Elements.terminal.scrollTop = Elements.terminal.scrollHeight;
    },
    error(message) {
        this.log(`Error: ${message}`, 'error');
    },
    success(message) {
        this.log(message, 'success');
    }
};

const ApiService = {
    async fetchPredictions(days, stepsPerDay) {
        try {
            const response = await fetch(`/api/v1/predict/baseline?days=${days}&steps_per_day=${stepsPerDay}`);

            // Handle HTTP Errors
            if (!response.ok) {
                const errorData = await response.json();
                const errorMsg = errorData.error?.message || 'Unknown Server Error';
                throw new Error(`${response.status}: ${errorMsg}`);
            }

            const result = await response.json();
            return result.data; // Return the standardized 'data' envelope list

        } catch (error) {
            Logger.error(error.message);
            throw error; // Re-throw to be handled by the action
        }
    }
};

// --- 5. Actions (Mutations) ---
const Actions = {
    updateSettings(key, value) {
        state.settings[key] = value;
        // Trigger generic UI updates
        Elements.daysValue.textContent = `${state.settings.days} Day${state.settings.days > 1 ? 's' : ''}`;
        Elements.stepsValue.textContent = `${state.settings.steps} Steps`;
    },

    async runBaseline() {
        if (state.isLoading) return;

        state.isLoading = true;
        Elements.btnBaseline.disabled = true;
        Logger.log(`Requesting SGP4 Baseline for ${state.settings.days} days...`, 'system');

        try {
            const data = await ApiService.fetchPredictions(
                state.settings.days,
                state.settings.steps
            );

            state.predictions = data;
            state.error = null;

            GlobeService.updatePaths(state.predictions);
            Logger.success(`Rendered ${data.length} coordinate points on globe.`);

        } catch (error) {
            state.error = error;
            state.predictions = [];
        } finally {
            state.isLoading = false;
            Elements.btnBaseline.disabled = false;
        }
    },

    clearData() {
        state.predictions = [];
        GlobeService.clear();
        Logger.log('Cleared orbital rendered data.', 'system');
    }
};

// --- 6. Event Listeners ---
function bindEvents() {
    Elements.daysInput.addEventListener('input', (e) => {
        Actions.updateSettings('days', parseInt(e.target.value, 10));
    });

    Elements.stepsInput.addEventListener('input', (e) => {
        Actions.updateSettings('steps', parseInt(e.target.value, 10));
    });

    Elements.btnBaseline.addEventListener('click', () => {
        Actions.runBaseline();
    });

    Elements.btnClear.addEventListener('click', () => {
        Actions.clearData();
    });
}

// --- 7. App Bootstrap ---
function bootstrap() {
    GlobeService.init();
    bindEvents();
    Logger.log('UI App Ready. Connect to telemetry.', 'system');
}

// Start app
bootstrap();
