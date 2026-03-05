/* ═══════════════════════════════════════════
   SimEx AI — Application Logic
   ═══════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000/api';

// ── State ─────────────────────────────────
const state = {
    wings: [],
    phases: [],
    activeWing: null,
    currentPhase: null,
    injects: [],
    messages: {},  // { wingId: [messages] }
};

// ── DOM References ────────────────────────
const $ = (sel) => document.querySelector(sel);
const wingList = $('#wing-list');
const chatMessages = $('#chat-messages');
const chatInput = $('#chat-input');
const chatForm = $('#chat-form');
const chatWingIcon = $('#chat-wing-icon');
const chatWingName = $('#chat-wing-name');
const chatPhaseLabel = $('#chat-phase-label');
const phaseTimeline = $('#phase-timeline');
const injectList = $('#inject-list');
const injectCount = $('#inject-count');
const welcomeMessage = $('#welcome-message');
const btnAdvance = $('#btn-advance-phase');
const btnBack = $('#btn-back-phase');
const btnReset = $('#btn-reset');
const btnShowActions = $('#btn-show-actions');
const actionsModal = $('#actions-modal');
const actionsList = $('#actions-list');
const actionsModalTitle = $('#actions-modal-title');
const btnCloseActions = $('#btn-close-actions');
const btnSend = $('#btn-send');

// ── API Helpers ───────────────────────────
async function api(path, options = {}) {
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options,
        });
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
    } catch (err) {
        console.error('API call failed:', err);
        return null;
    }
}

// ── Initialize ────────────────────────────
async function init() {
    const [wingsData, phasesData, scenarioData] = await Promise.all([
        api('/wings'),
        api('/phases'),
        api('/scenario'),
    ]);

    if (wingsData) {
        state.wings = wingsData.wings;
        renderWings();
    }
    if (phasesData) {
        state.phases = phasesData.phases;
        state.currentPhase = phasesData.phases.find(p => p.is_active);
        renderTimeline();
        updateButtonStates();
    }
    if (scenarioData) {
        $('#scenario-badge .badge-text').textContent =
            `${scenarioData.name}`;
    }

    await loadInjects();
}

// ── Wings ─────────────────────────────────
function renderWings() {
    wingList.innerHTML = state.wings.map(w => `
        <div class="wing-item" data-wing-id="${w.id}" tabindex="0" role="button" 
             aria-label="${w.name}">
            <span class="wing-item-icon">${w.icon}</span>
            <span class="wing-item-name">${w.name}</span>
        </div>
    `).join('');

    wingList.querySelectorAll('.wing-item').forEach(el => {
        el.addEventListener('click', () => selectWing(el.dataset.wingId));
        el.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectWing(el.dataset.wingId);
            }
        });
    });
}

function selectWing(wingId) {
    state.activeWing = state.wings.find(w => w.id === wingId);
    if (!state.activeWing) return;

    // Update active state
    wingList.querySelectorAll('.wing-item').forEach(el => {
        el.classList.toggle('active', el.dataset.wingId === wingId);
    });

    // Update chat header
    chatWingIcon.textContent = state.activeWing.icon;
    chatWingName.textContent = state.activeWing.name;
    chatPhaseLabel.textContent = state.currentPhase ? state.currentPhase.label : '—';

    // Enable input
    chatInput.disabled = false;
    btnSend.disabled = false;
    chatInput.focus();

    // Show messages for this wing or send greeting
    renderMessages();

    if (!state.messages[wingId] || state.messages[wingId].length === 0) {
        sendGreeting(wingId);
    }
}

async function sendGreeting(wingId) {
    const phaseId = state.currentPhase ? state.currentPhase.id : 'd_day';
    const data = await api('/chat', {
        method: 'POST',
        body: JSON.stringify({
            wing_id: wingId,
            phase_id: phaseId,
            message: 'hello',
        }),
    });
    if (data) {
        addMessage(wingId, 'system', data.response, data.wing_name);
    }
}

// ── Chat ──────────────────────────────────
function addMessage(wingId, type, text, wingName = '') {
    if (!state.messages[wingId]) state.messages[wingId] = [];

    const now = new Date();
    state.messages[wingId].push({
        type,
        text,
        wingName,
        time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
    });

    if (state.activeWing && state.activeWing.id === wingId) {
        renderMessages();
    }
}

function renderMessages() {
    if (!state.activeWing) return;

    const msgs = state.messages[state.activeWing.id] || [];

    if (msgs.length === 0) {
        chatMessages.innerHTML = welcomeMessage.outerHTML;
        return;
    }

    chatMessages.innerHTML = msgs.map(m => `
        <div class="message ${m.type}">
            ${m.type === 'system' ? `<span class="message-wing-label">${m.wingName}</span>` : ''}
            <div class="message-bubble">${formatText(m.text)}</div>
            <span class="message-meta">${m.time}</span>
        </div>
    `).join('');

    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatText(text) {
    // Convert numbered lists and basic formatting
    return text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message || !state.activeWing) return;

    const wingId = state.activeWing.id;
    const phaseId = state.currentPhase ? state.currentPhase.id : 'd_day';

    // Add user message
    addMessage(wingId, 'user', message);
    chatInput.value = '';

    // Get response
    const data = await api('/chat', {
        method: 'POST',
        body: JSON.stringify({
            wing_id: wingId,
            phase_id: phaseId,
            message: message,
        }),
    });

    if (data) {
        addMessage(wingId, 'system', data.response, data.wing_name);
    } else {
        addMessage(wingId, 'system', 'Error: Could not get a response. Please try again.', 'System');
    }
});

// ── Timeline ──────────────────────────────
function renderTimeline() {
    phaseTimeline.innerHTML = state.phases.map(p => `
        <div class="phase-item ${p.is_active ? 'active' : ''} ${p.is_completed ? 'completed' : ''}">
            <div class="phase-dot">
                ${p.is_completed ? '✓' : p.is_active ? '●' : ''}
            </div>
            <div class="phase-info">
                <div class="phase-label">${p.label}</div>
                <div class="phase-days">${p.days}</div>
            </div>
        </div>
    `).join('');
}

btnAdvance.addEventListener('click', async () => {
    const data = await api('/phase/advance', { method: 'POST' });
    if (data && data.phases) {
        state.phases = data.phases;
        state.currentPhase = data.phases.find(p => p.is_active);
        renderTimeline();

        // Update chat phase label
        if (state.currentPhase) {
            chatPhaseLabel.textContent = state.currentPhase.label;
        }

        // Load new injects
        if (data.injects) {
            state.injects = data.injects;
            renderInjects();
        } else {
            await loadInjects();
        }

        // Notify in chat
        if (state.activeWing && state.currentPhase) {
            addMessage(
                state.activeWing.id,
                'system',
                `⏩ Exercise advanced to ${state.currentPhase.label} (${state.currentPhase.days})`,
                'Exercise Control'
            );
            // Get new greeting for current wing in new phase
            sendGreeting(state.activeWing.id);
        }

        updateButtonStates();

        // Show notification
        if (data.message) {
            showPhaseNotification(data.message);
        }
    }
});

btnBack.addEventListener('click', async () => {
    const data = await api('/phase/back', { method: 'POST' });
    if (data && data.phases) {
        state.phases = data.phases;
        state.currentPhase = data.phases.find(p => p.is_active);
        renderTimeline();

        // Update chat phase label
        if (state.currentPhase) {
            chatPhaseLabel.textContent = state.currentPhase.label;
        }

        // Load new injects
        await loadInjects();

        // Notify in chat
        if (state.activeWing && state.currentPhase) {
            addMessage(
                state.activeWing.id,
                'system',
                `⏪ Exercise returned to ${state.currentPhase.label} (${state.currentPhase.days})`,
                'Exercise Control'
            );
            // Get greeting for current wing in the previous phase
            sendGreeting(state.activeWing.id);
        }

        updateButtonStates();

        if (data.message) {
            showPhaseNotification(data.message);
        }
    }
});

function updateButtonStates() {
    const currentIndex = state.phases.findIndex(p => p.is_active);
    btnBack.disabled = currentIndex === 0;
    btnAdvance.disabled = currentIndex === state.phases.length - 1;
}

btnReset.addEventListener('click', async () => {
    if (!confirm('Reset exercise to D Day? All chat history will be cleared.')) return;

    const data = await api('/phase/reset', { method: 'POST' });
    if (data && data.phases) {
        state.phases = data.phases;
        state.currentPhase = data.phases.find(p => p.is_active);
        state.messages = {};
        state.activeWing = null;
        renderTimeline();
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">🌍</div>
                <h3>SimEx AI — Exercise Control</h3>
                <p>Select a wing from the left panel to begin the simulation exercise.</p>
                <p class="welcome-hint">Exercise reset to D Day</p>
            </div>
        `;
        chatWingName.textContent = 'Select a Wing';
        chatWingIcon.textContent = '🎯';
        chatPhaseLabel.textContent = '—';
        chatInput.disabled = true;
        btnSend.disabled = true;
        wingList.querySelectorAll('.wing-item').forEach(el => el.classList.remove('active'));
        await loadInjects();
    }
});

function showPhaseNotification(message) {
    const el = document.createElement('div');
    el.style.cssText = `
        position: fixed; top: 80px; right: 20px; padding: 12px 20px;
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        color: white; border-radius: 10px; font-size: 14px; font-weight: 500;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5); z-index: 999;
        animation: inject-in 0.4s cubic-bezier(0.4,0,0.2,1);
    `;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

// ── Injects ───────────────────────────────
async function loadInjects() {
    const data = await api('/injects');
    if (data) {
        state.injects = data.injects;
        renderInjects();
    }
}

function renderInjects() {
    injectCount.textContent = state.injects.length;

    if (state.injects.length === 0) {
        injectList.innerHTML = '<div class="inject-empty">No injects for this phase.</div>';
        return;
    }

    injectList.innerHTML = state.injects.map((inj, i) => `
        <div class="inject-card ${inj.severity}" style="animation-delay: ${i * 100}ms">
            <div class="inject-time">${inj.time_offset}</div>
            <div class="inject-title">${inj.title}</div>
            <div class="inject-desc">${inj.description}</div>
            <span class="inject-severity ${inj.severity}">${inj.severity}</span>
        </div>
    `).join('');
}

// ── Actions Modal ─────────────────────────
btnShowActions.addEventListener('click', async () => {
    if (!state.activeWing) return;

    const data = await api(`/wings/${state.activeWing.id}/actions`);
    if (data && data.actions) {
        actionsModalTitle.textContent = `${state.activeWing.name} — ${data.phase.label}`;
        actionsList.innerHTML = data.actions.map(a => `<li>${a}</li>`).join('');
        actionsModal.hidden = false;
    }
});

btnCloseActions.addEventListener('click', () => { actionsModal.hidden = true; });
actionsModal.addEventListener('click', (e) => {
    if (e.target === actionsModal) actionsModal.hidden = true;
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !actionsModal.hidden) actionsModal.hidden = true;
});

// ── Start ─────────────────────────────────
init();
