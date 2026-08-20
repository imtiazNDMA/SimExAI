/* ═══════════════════════════════════════════════
   SimexAI — Application Logic
   ═══════════════════════════════════════════════ */

// Origin-relative: the backend serves this page, so the API is always on the
// same host and port. Hardcoding a port breaks `start.bat -Port <n>`.
const API_BASE = '/api';

// ── State ──────────────────────────────────────
const state = {
  wings:       [],
  phases:      [],
  activeWing:  null,
  currentPhase: null,
  injects:     [],
  messages:    {},  // { wingId: [{ type, text, wingName, time }] }
};

// ── DOM ────────────────────────────────────────
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const wingList        = $('#wing-list');
const chatMessages    = $('#chat-messages');
const chatInput       = $('#chat-input');
const chatForm        = $('#chat-form');
const inputWrap       = $('#input-wrap');
const chatWingIcon    = $('#chat-wing-icon');
const chatWingName    = $('#chat-wing-name');
const chatPhaseLabel  = $('#chat-phase-label');
const timelineStrip   = $('#timeline-strip');
const injectCount     = $('#inject-count');
const btnAdvance      = $('#btn-advance-phase');
const btnBack         = $('#btn-back-phase');
const btnReset        = $('#btn-reset');
const btnUploadScenario = $('#btn-upload-scenario');
const fileInputScenario = $('#scenario-file-input');
const btnShowActions  = $('#btn-show-actions');
const actionsModal    = $('#actions-modal');
const actionsList     = $('#actions-list');
const actionsModalTitle = $('#actions-modal-title');
const btnCloseActions = $('#btn-close-actions');
const btnSend         = $('#btn-send');
const btnMic          = $('#btn-mic');
const sidebarToggle   = $('#sidebar-toggle');
const sidebar         = $('#sidebar');
const sidebarOverlay  = $('#sidebar-overlay');
const btnInjects      = $('#btn-injects');
const rightDrawer     = $('#right-drawer');
const drawerOverlay   = $('#drawer-overlay');
const drawerClose     = $('#drawer-close');
const drawerPhaseLabel = $('#drawer-phase-label');
const injectList      = $('#inject-list');
const wingCount       = $('#wing-count');
const themeToggle     = $('#theme-toggle');

const THEME_KEY = 'simexai-theme';

// ── API ────────────────────────────────────────
async function api(path, options = {}) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
  } catch (err) {
    console.error('API error:', err);
    return null;
  }
}

// ── Init ───────────────────────────────────────
async function init() {
  initTheme();

  const [wingsData, phasesData, scenarioData] = await Promise.all([
    api('/wings'),
    api('/phases'),
    api('/scenario'),
  ]);

  if (scenarioData) {
    state.scenario = scenarioData;
    updateHeader();
    if (!state.activeWing) chatMessages.innerHTML = buildWelcomeHTML();
  }

  if (wingsData) {
    state.wings = wingsData.wings;
    wingCount.textContent = state.wings.length;
    renderWings();
  }
  if (phasesData) {
    state.phases = phasesData.phases;
    state.currentPhase = phasesData.phases.find(p => p.is_active);
    renderTimeline();
    updateButtonStates();
  }
  await loadInjects();
}

function updateHeader() {
  const boxesContainer = document.getElementById('header-scenario-boxes');
  const boxName = document.getElementById('box-name');
  const boxType = document.getElementById('box-type');
  const boxLocation = document.getElementById('box-location');
  const boxImpact = document.getElementById('box-impact');

  if (!boxesContainer) return;

  if (!state.scenario?.is_uploaded) {
    boxesContainer.hidden = true;
    return;
  }

  const summary = buildScenarioSummary(state.scenario);
  boxesContainer.hidden = false;
  setScenarioBoxValue(boxName, summary.name, summary.fullName);
  setScenarioBoxValue(boxType, summary.type, summary.fullType);
  setScenarioBoxValue(boxLocation, summary.location, summary.fullLocation);
  setScenarioBoxValue(boxImpact, summary.impact, summary.fullImpact);
}

function setScenarioBoxValue(el, value, fullValue) {
  if (!el) return;
  const displayValue = value || 'N/A';
  el.textContent = displayValue;
  el.title = fullValue || displayValue;
}

const SUMMARY_STOPWORDS = new Set([
  'a', 'an', 'and', 'the', 'of', 'for', 'to', 'in', 'on', 'with', 'due', 'by', 'from',
  'event', 'scenario', 'simulation', 'exercise', 'season', 'summer', 'winter', 'spring',
  'autumn', 'fall', 'early', 'late'
]);

function buildScenarioSummary(scenario = {}) {
  const fullName = flattenScenarioValue(scenario.name);
  const fullType = flattenScenarioValue(scenario.type);
  const fullLocation = flattenScenarioValue(scenario.location);
  const fullImpact = flattenScenarioValue(scenario.impact);

  return {
    name: summarizeScenarioName(scenario.name),
    type: summarizeWords(scenario.type, 3, 'Disaster'),
    location: summarizeLocation(scenario.location),
    impact: summarizeImpact(scenario.impact),
    fullName,
    fullType,
    fullLocation,
    fullImpact,
  };
}

function summarizeScenarioName(value) {
  return summarizeWords(value, 4, 'Scenario');
}

function summarizeWords(value, maxWords, fallback) {
  const text = normalizeSummaryText(flattenScenarioValue(value));
  if (!text) return fallback;

  const words = text
    .replace(/[|/]/g, ' ')
    .replace(/[^\w\s.+-]/g, ' ')
    .split(/\s+/)
    .map(word => word.trim())
    .filter(Boolean)
    .filter(word => !/^20\d{2}$/.test(word))
    .filter(word => !SUMMARY_STOPWORDS.has(word.toLowerCase()));

  const selected = words.length ? words.slice(0, maxWords).join(' ') : text;
  return toDisplayCase(limitWords(selected, maxWords));
}

function summarizeLocation(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const parts = [
      value.district,
      value.province,
      value.region,
      value.country && !value.province ? value.country : '',
    ].filter(Boolean).map(part => compactLocationName(flattenScenarioValue(part)));
    const uniqueParts = uniqueNonEmpty(parts).slice(0, 3);
    if (uniqueParts.length) return uniqueParts.join(', ');
  }

  const text = normalizeSummaryText(flattenScenarioValue(value));
  if (!text) return 'Location';

  const withoutDetails = text.replace(/\([^)]*\)/g, ' ');
  const parts = withoutDetails
    .split(/[,;]|\band\b/i)
    .map(part => compactLocationName(part))
    .filter(part => part && !/specifically/i.test(part));

  const uniqueParts = uniqueNonEmpty(parts).slice(0, 3);
  return uniqueParts.length ? uniqueParts.join(', ') : limitWords(toDisplayCase(withoutDetails), 4);
}

function summarizeImpact(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const priorityKeys = [
      'displaced_population',
      'estimated_fatalities',
      'estimated_injuries',
      'houses_damaged_destroyed',
      'affected_population',
    ];
    for (const key of priorityKeys) {
      if (value[key]) {
        const metric = extractMetricPhrase(flattenScenarioValue(value[key]), key);
        if (metric) return metric;
      }
    }
  }

  const text = normalizeSummaryText(flattenScenarioValue(value));
  if (!text) return 'Impact';

  const metric = extractMetricPhrase(text);
  if (metric) return metric;

  return limitWords(
    text
      .replace(/\b(widespread|significant|severe|heavy|major|due|to|because|of)\b/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim(),
    5
  );
}

function extractMetricPhrase(text, context = '') {
  const source = normalizeSummaryText(`${context} ${text}`);
  const metricMatch = source.match(/(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(million|billion|thousand|m|bn|k)?\s+(people|persons|population|residents|families|households|fatalities|injuries|injured|displaced)/i);
  if (!metricMatch) {
    const numberMatch = source.match(/(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?:\s*-\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?))?/);
    if (!numberMatch) return '';

    const amount = numberMatch[2]
      ? `${compactNumber(numberMatch[1])}-${compactNumber(numberMatch[2])}`
      : compactNumber(numberMatch[1]);

    if (/fatal/.test(source)) return `${amount} fatalities`;
    if (/injur/.test(source)) return `${amount} injured`;
    if (/displac|evacuat/.test(source)) return `${amount} displaced`;
    if (/house|home|damage/.test(source)) return `${amount} homes damaged`;
    if (/affect/.test(source)) return `${amount} people affected`;
    return '';
  }

  const amount = compactNumber(metricMatch[1], metricMatch[2]);
  const noun = metricMatch[3].toLowerCase();

  if (/fatal/.test(source)) return `${amount} fatalities`;
  if (/injur/.test(source)) return `${amount} injured`;
  if (/displac|evacuat/.test(source)) return `${amount} displaced`;
  if (/household|famil/.test(noun)) return `${amount} families affected`;
  return `${amount} people affected`;
}

function compactNumber(rawNumber, rawUnit = '') {
  const unit = String(rawUnit || '').toLowerCase();
  const normalized = String(rawNumber).replace(/,/g, '');
  const numeric = Number(normalized);

  if (unit.startsWith('b')) return `${trimTrailingZero(numeric)}B`;
  if (unit.startsWith('m')) return `${trimTrailingZero(numeric)}M`;
  if (unit.startsWith('k') || unit.startsWith('thousand')) return `${trimTrailingZero(numeric)}K`;

  if (!Number.isFinite(numeric)) return rawNumber;
  if (numeric >= 1000000) return `${trimTrailingZero(numeric / 1000000)}M`;
  if (numeric >= 1000) return `${trimTrailingZero(numeric / 1000)}K`;
  return String(numeric);
}

function trimTrailingZero(number) {
  return Number(number.toFixed(1)).toString();
}

function compactLocationName(value) {
  const clean = normalizeSummaryText(value)
    .replace(/\bKhyber\s+Pakhtunkhwa\b/ig, 'KP')
    .replace(/\bWestern\s+Punjab\b/ig, 'Punjab')
    .replace(/\bGilgit[-\s]+Baltistan\b/ig, 'GB')
    .replace(/\bAzad\s+Jammu\s+and\s+Kashmir\b/ig, 'AJK')
    .replace(/\bPakistan\b/ig, '')
    .replace(/\s+/g, ' ')
    .trim();
  return limitWords(toDisplayCase(clean), 3);
}

function flattenScenarioValue(value) {
  if (value == null) return '';
  if (Array.isArray(value)) return value.map(flattenScenarioValue).filter(Boolean).join(', ');
  if (typeof value === 'object') {
    return Object.entries(value)
      .map(([key, nestedValue]) => {
        const flatValue = flattenScenarioValue(nestedValue);
        return flatValue ? `${key.replace(/_/g, ' ')} ${flatValue}` : '';
      })
      .filter(Boolean)
      .join(', ');
  }
  return String(value);
}

function normalizeSummaryText(value) {
  return String(value || '')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\s+/g, ' ')
    .trim();
}

function limitWords(value, maxWords) {
  const text = String(value || '').trim();
  const words = text.split(/\s+/).filter(Boolean);
  return words.length > maxWords ? words.slice(0, maxWords).join(' ') : text;
}

function uniqueNonEmpty(values) {
  const seen = new Set();
  return values.filter(value => {
    const key = String(value || '').trim().toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function toDisplayCase(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/\b\w/g, char => char.toUpperCase())
    .replace(/\bKp\b/g, 'KP')
    .replace(/\bGb\b/g, 'GB')
    .replace(/\bAjk\b/g, 'AJK')
    .replace(/\bNdma\b/g, 'NDMA')
    .replace(/\bLa\b/g, 'La');
}

// ── Wings ──────────────────────────────────────
function renderWings() {
  wingList.innerHTML = state.wings.map(w => `
    <div class="wing-item" data-wing-id="${w.id}" tabindex="0" role="button"
         aria-label="${w.name}">
      <span class="wing-item-icon">${w.icon}</span>
      <span class="wing-item-name">${w.name}</span>
    </div>
  `).join('');

  wingList.querySelectorAll('.wing-item').forEach(el => {
    el.addEventListener('click', () => {
      selectWing(el.dataset.wingId);
      if (isMobile()) closeSidebar();
    });
    el.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        selectWing(el.dataset.wingId);
        if (isMobile()) closeSidebar();
      }
    });
  });
}

function selectWing(wingId) {
  state.activeWing = state.wings.find(w => w.id === wingId);
  if (!state.activeWing) return;

  wingList.querySelectorAll('.wing-item').forEach(el => {
    el.classList.toggle('active', el.dataset.wingId === wingId);
  });

  chatWingIcon.textContent = state.activeWing.icon;
  chatWingName.textContent = state.activeWing.name;
  chatPhaseLabel.textContent = state.currentPhase ? state.currentPhase.label : '—';

  chatInput.disabled = false;
  btnSend.disabled = false;
  if (btnMic) btnMic.disabled = false;
  btnShowActions.disabled = false;
  chatInput.focus();

  renderMessages();

  if (!state.messages[wingId] || state.messages[wingId].length === 0) {
    sendGreeting(wingId);
  }
}

async function sendGreeting(wingId, isPhaseChange = false) {
  const phaseId = state.currentPhase ? state.currentPhase.id : 'd_minus_90';
  showTypingIndicator();
  
  let msgText = isPhaseChange
    ? `Phase advancement notice: ${state.currentPhase?.label || phaseId}. Brief me on the new phase priorities based on the scenario records. Do not welcome me, do not acknowledge my presence or role again, and do not repeat the exercise title.`
    : 'hello';

  const data = await api('/chat', {
    method: 'POST',
    body: JSON.stringify({ wing_id: wingId, phase_id: phaseId, message: msgText }),
  });
  hideTypingIndicator();
  if (data) {
    addMessage(wingId, 'system', data.response, data.wing_name);
    ttsAutoPlay(data.response);
  }
}

// ── Chat ───────────────────────────────────────
function addMessage(wingId, type, text, wingName = '') {
  if (!state.messages[wingId]) state.messages[wingId] = [];
  const now = new Date();
  state.messages[wingId].push({
    type, text, wingName,
    time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
  });
  if (state.activeWing && state.activeWing.id === wingId) renderMessages();
}

function renderMessages() {
  if (!state.activeWing) return;
  const msgs = state.messages[state.activeWing.id] || [];

  if (msgs.length === 0) {
    chatMessages.innerHTML = buildWelcomeHTML();
    return;
  }

  chatMessages.innerHTML = msgs.map((m, idx) => {
    if (m.type === 'notification') {
      return `
        <div class="message notification">
          <div class="message-bubble">${formatText(m.text)}</div>
        </div>`;
    }
    const speakerBtn = m.type === 'system' ? `
      <div class="tts-controls">
        <button class="tts-speaker-btn" data-msg-idx="${idx}" title="Play / Stop TTS">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>
        </button>
        <span class="message-time">${m.time}</span>
      </div>` : `<span class="message-time">${m.time}</span>`;
    return `
      <div class="message ${m.type}" data-msg-idx="${idx}">
        ${m.type === 'system' ? `<span class="message-label">${m.wingName}</span>` : ''}
        <div class="message-bubble" id="msg-bubble-${idx}">${formatText(m.text)}</div>
        ${speakerBtn}
      </div>`;
  }).join('');

  // Attach click handlers to speaker buttons
  chatMessages.querySelectorAll('.tts-speaker-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = parseInt(btn.dataset.msgIdx);
      const wingId = state.activeWing?.id;
      if (wingId && state.messages[wingId] && state.messages[wingId][idx]) {
        ttsPlayForMessage(idx, state.messages[wingId][idx].text, btn);
      }
    });
  });

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function buildWelcomeHTML() {
  const summary = state.scenario?.is_uploaded ? buildScenarioSummary(state.scenario) : null;
  const scenarioGrid = summary ? `
        <div class="welcome-scenario-grid" aria-label="Scenario summary">
          ${buildWelcomeScenarioBox('Scenario', summary.name)}
          ${buildWelcomeScenarioBox('Disaster Type', summary.type)}
          ${buildWelcomeScenarioBox('Location', summary.location)}
          ${buildWelcomeScenarioBox('Impact', summary.impact)}
        </div>` : '';
  
  return `
    <div class="welcome-screen" id="welcome-message">
      <div class="welcome-glow"></div>
      <div class="welcome-content">
        <div class="welcome-logo">
          <div class="welcome-brand-mark">
            <img src="ndma_logo.png" alt="NDMA" class="brand-logo-img">
          </div>
        </div>
        <h1 class="welcome-title">SimexAI</h1>
        <p class="welcome-sub">AI-powered disaster simulation platform<br>for NDMA Pakistan</p>
        ${scenarioGrid}
        <p class="welcome-cta" style="margin-top: 30px;">← Select a wing from the sidebar to begin</p>
      </div>
    </div>`;
}

function buildWelcomeScenarioBox(label, value) {
  return `
          <div class="scenario-box">
            <span class="scenario-box-label">${escapeHtml(label)}</span>
            <span class="scenario-box-value">${escapeHtml(value || 'N/A')}</span>
          </div>`;
}

function formatText(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

// Typing indicator
let typingEl = null;
function showTypingIndicator() {
  if (typingEl) return;
  typingEl = document.createElement('div');
  typingEl.className = 'message system';
  typingEl.id = 'typing-indicator';
  typingEl.innerHTML = `
    <span class="message-label">AI</span>
    <div class="message-bubble" style="display:flex;align-items:center;gap:6px;padding:12px 16px">
      <span style="width:7px;height:7px;border-radius:50%;background:#8b5cf6;display:inline-block;animation:typing-bounce 1s ease-in-out infinite 0ms"></span>
      <span style="width:7px;height:7px;border-radius:50%;background:#8b5cf6;display:inline-block;animation:typing-bounce 1s ease-in-out infinite 160ms"></span>
      <span style="width:7px;height:7px;border-radius:50%;background:#8b5cf6;display:inline-block;animation:typing-bounce 1s ease-in-out infinite 320ms"></span>
    </div>`;
  if (!document.getElementById('typing-style')) {
    const s = document.createElement('style');
    s.id = 'typing-style';
    s.textContent = `@keyframes typing-bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-6px)}}`;
    document.head.appendChild(s);
  }
  chatMessages.appendChild(typingEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}
function hideTypingIndicator() {
  if (typingEl) { typingEl.remove(); typingEl = null; }
}

chatForm.addEventListener('submit', async e => {
  e.preventDefault();
  const message = chatInput.value.trim();
  if (!message || !state.activeWing) return;

  const wingId  = state.activeWing.id;
  const phaseId = state.currentPhase ? state.currentPhase.id : 'd_minus_90';

  addMessage(wingId, 'user', message);
  chatInput.value = '';

  showTypingIndicator();
  const data = await api('/chat', {
    method: 'POST',
    body: JSON.stringify({ wing_id: wingId, phase_id: phaseId, message }),
  });
  hideTypingIndicator();

  if (data) {
    addMessage(wingId, 'system', data.response, data.wing_name);
    ttsAutoPlay(data.response);
  } else {
    addMessage(wingId, 'system', 'Error: Could not get a response. Please try again.', 'System');
  }
});

// ── Timeline ───────────────────────────────────
function renderTimeline() {
  const items = state.phases.map((p, i) => {
    const isLast = i === state.phases.length - 1;
    const connClass = p.is_completed ? 'completed' : '';
    const stepClass = p.is_active ? 'active' : p.is_completed ? 'completed' : '';
    const checkmark = p.is_completed
      ? `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><polyline points="20 6 9 17 4 12"/></svg>`
      : `<div class="phase-dot-inner"></div>`;

    return `
      <div class="phase-step ${stepClass}">
        <div class="phase-node" title="${p.label} — ${p.days}">
          <div class="phase-dot-outer">${checkmark}</div>
          <div class="phase-step-label">${p.label}</div>
          <div class="phase-step-days">${p.days}</div>
        </div>
        ${!isLast ? `<div class="phase-connector ${connClass}"></div>` : ''}
      </div>`;
  }).join('');

  timelineStrip.innerHTML = items;

  // Scroll active phase into view
  const activeStep = timelineStrip.querySelector('.phase-step.active');
  if (activeStep) activeStep.scrollIntoView({ block: 'nearest', inline: 'center', behavior: 'smooth' });
}

// ── Phase Controls ─────────────────────────────
btnAdvance.addEventListener('click', async () => {
  const data = await api('/phase/advance', { method: 'POST' });
  if (data?.phases) applyPhaseUpdate(data, '⏩ Advanced to');
});

btnBack.addEventListener('click', async () => {
  const data = await api('/phase/back', { method: 'POST' });
  if (data?.phases) applyPhaseUpdate(data, '⏪ Returned to');
});

async function applyPhaseUpdate(data, verb) {
  state.phases = data.phases;
  state.currentPhase = data.phases.find(p => p.is_active);
  renderTimeline();

  if (state.currentPhase) {
    chatPhaseLabel.textContent = state.currentPhase.label;
    drawerPhaseLabel.textContent = state.currentPhase.label;
  }

  if (data.injects) { state.injects = data.injects; renderInjects(); }
  else await loadInjects();

  if (state.activeWing && state.currentPhase) {
    addMessage(state.activeWing.id, 'notification',
      `${verb} **${state.currentPhase.label}** (${state.currentPhase.days})`,
      'Exercise Control');
    sendGreeting(state.activeWing.id, true);
  }
  updateButtonStates();
  if (data.message) showToast(data.message);
}

function updateButtonStates() {
  const idx = state.phases.findIndex(p => p.is_active);
  btnBack.disabled    = idx === 0;
  btnAdvance.disabled = idx === state.phases.length - 1;
}

btnReset.addEventListener('click', async () => {
  if (!confirm('Reset exercise to D-90? Chat history and the uploaded scenario summary will be cleared.')) return;
  const data = await api('/phase/reset', { method: 'POST' });
  if (data?.phases) {
    state.phases      = data.phases;
    state.currentPhase = data.phases.find(p => p.is_active);
    state.scenario     = data.scenario || null;
    state.injects      = data.injects || [];
    state.messages    = {};
    state.activeWing  = null;

    renderTimeline();
    updateHeader();
    chatMessages.innerHTML = buildWelcomeHTML();
    chatWingName.textContent  = 'Select a Wing';
    chatWingIcon.textContent  = '🎯';
    chatPhaseLabel.textContent = '—';
    chatInput.disabled = true;
    btnSend.disabled   = true;
    btnShowActions.disabled = true;
    wingList.querySelectorAll('.wing-item').forEach(el => el.classList.remove('active'));
    if (data.injects) renderInjects();
    else await loadInjects();
    showToast('Exercise reset to D-90');
  }
});

// ── Injects ────────────────────────────────────
async function loadInjects() {
  const data = await api('/injects');
  if (data) { state.injects = data.injects; renderInjects(); }
}

function renderInjects() {
  injectCount.textContent = state.injects.length;
  drawerPhaseLabel.textContent = state.currentPhase ? state.currentPhase.label : 'Current Phase';

  if (state.injects.length === 0) {
    injectList.innerHTML = `
      <div class="inject-empty-state">
        <div class="inject-empty-icon">📭</div>
        <p>No injects for this phase yet.</p>
      </div>`;
    return;
  }

  injectList.innerHTML = state.injects.map((inj, i) => `
    <div class="inject-card ${inj.severity}" style="animation-delay:${i * 80}ms">
      <div class="inject-time">${inj.time_offset}</div>
      <div class="inject-title">${escapeHtml(inj.title)}</div>
      <div class="inject-desc">${escapeHtml(inj.description)}</div>
      <span class="inject-severity-tag ${inj.severity}">${inj.severity}</span>
    </div>
  `).join('');
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

// ── Actions Modal ──────────────────────────────
btnShowActions.addEventListener('click', async () => {
  if (!state.activeWing) return;
  const data = await api(`/wings/${state.activeWing.id}/actions`);
  if (data?.actions) {
    actionsModalTitle.textContent = `${state.activeWing.name} — ${data.phase.label}`;
    actionsList.innerHTML = data.actions.map(a => `<li>${escapeHtml(a)}</li>`).join('');
    actionsModal.hidden = false;
  }
});

btnCloseActions.addEventListener('click', () => { actionsModal.hidden = true; });
actionsModal.addEventListener('click', e => { if (e.target === actionsModal) actionsModal.hidden = true; });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    actionsModal.hidden = true;
    closeDrawer();
  }
});

// ── Sidebar Toggle ─────────────────────────────
function isMobile() { return window.innerWidth <= 640; }

function openSidebar() {
  if (isMobile()) {
    sidebar.classList.add('mobile-open');
    sidebarOverlay.classList.add('visible');
    sidebarOverlay.style.display = 'block';
  } else {
    sidebar.classList.remove('collapsed');
  }
}

function closeSidebar() {
  if (isMobile()) {
    sidebar.classList.remove('mobile-open');
    sidebarOverlay.classList.remove('visible');
    setTimeout(() => { sidebarOverlay.style.display = ''; }, 280);
  } else {
    sidebar.classList.add('collapsed');
  }
}

sidebarToggle.addEventListener('click', () => {
  const isOpen = isMobile()
    ? sidebar.classList.contains('mobile-open')
    : !sidebar.classList.contains('collapsed');
  isOpen ? closeSidebar() : openSidebar();
});

sidebarOverlay.addEventListener('click', closeSidebar);

// ── Theme Toggle ───────────────────────────────
function getInitialTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'light' || saved === 'dark') return saved;
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  themeToggle.setAttribute('aria-label', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
  themeToggle.setAttribute('title', `Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`);
}

function initTheme() {
  applyTheme(getInitialTheme());
}

themeToggle.addEventListener('click', () => {
  const nextTheme = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light';
  localStorage.setItem(THEME_KEY, nextTheme);
  applyTheme(nextTheme);
});

// ── Right Drawer ───────────────────────────────
function openDrawer() {
  rightDrawer.classList.add('open');
  drawerOverlay.classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeDrawer() {
  rightDrawer.classList.remove('open');
  drawerOverlay.classList.remove('open');
  document.body.style.overflow = '';
}

btnInjects.addEventListener('click', openDrawer);
drawerClose.addEventListener('click', closeDrawer);
drawerOverlay.addEventListener('click', closeDrawer);

// ── Toast ──────────────────────────────────────
function showToast(message) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => {
    el.style.animation = 'toast-out 300ms ease forwards';
    setTimeout(() => el.remove(), 310);
  }, 3000);
}

// ══════════════════════════════════════════════════
//  VOICE FEATURES: Push-to-Talk STT + Kokoro TTS
// ══════════════════════════════════════════════════

// ── Push-to-Talk (Speech-to-Text) ──────────────
let sttRecognition = null;
let sttIsListening = false;

function initSTT() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn('Web Speech API not supported in this browser');
    if (btnMic) btnMic.style.display = 'none';
    return;
  }

  sttRecognition = new SpeechRecognition();
  sttRecognition.continuous = false;
  sttRecognition.interimResults = true;
  sttRecognition.lang = 'en-US';
  sttRecognition.maxAlternatives = 1;

  sttRecognition.onstart = () => {
    sttIsListening = true;
    btnMic.classList.add('recording');
    chatInput.placeholder = '🎤 Listening...';
  };

  sttRecognition.onresult = (event) => {
    let finalTranscript = '';
    let interimTranscript = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalTranscript += transcript;
      } else {
        interimTranscript += transcript;
      }
    }
    // Show interim results as they come
    chatInput.value = finalTranscript || interimTranscript;
  };

  sttRecognition.onend = () => {
    sttIsListening = false;
    btnMic.classList.remove('recording');
    chatInput.placeholder = 'Type your response or ask the wing AI...';

    // Auto-submit if we got text
    const text = chatInput.value.trim();
    if (text) {
      chatForm.dispatchEvent(new Event('submit', { cancelable: true }));
    }
  };

  sttRecognition.onerror = (event) => {
    console.error('STT error:', event.error);
    sttIsListening = false;
    btnMic.classList.remove('recording');
    chatInput.placeholder = 'Type your response or ask the wing AI...';
    if (event.error === 'not-allowed') {
      showToast('Microphone access denied. Please allow microphone permissions.');
    }
  };

  // Wire up the mic button
  if (btnMic) {
    btnMic.addEventListener('click', () => {
      if (!state.activeWing) return;
      if (sttIsListening) {
        sttRecognition.stop();
      } else {
        // Stop any playing TTS first
        ttsStop();
        chatInput.value = '';
        sttRecognition.start();
      }
    });
  }
}

// ── TTS (Text-to-Speech via Kokoro) ────────────
let ttsAudio = null;
let ttsAnimFrame = null;
let ttsActiveBtn = null;
let ttsActiveBubbleIdx = null;

async function ttsAutoPlay(text) {
  if (!text) return;
  // Find the last system message index
  const wingId = state.activeWing?.id;
  if (!wingId || !state.messages[wingId]) return;
  const msgs = state.messages[wingId];
  const lastIdx = msgs.length - 1;
  if (lastIdx < 0 || msgs[lastIdx].type !== 'system') return;

  // Small delay to let DOM render
  await new Promise(r => setTimeout(r, 200));

  const btn = chatMessages.querySelector(`.tts-speaker-btn[data-msg-idx="${lastIdx}"]`);
  ttsPlayForMessage(lastIdx, text, btn);
}

async function ttsPlayForMessage(msgIdx, text, btn) {
  // If already playing this message, handle pause/resume
  if (ttsAudio && ttsActiveBubbleIdx === msgIdx) {
    if (ttsAudio.paused) {
      if (btn) btn.classList.add('playing');
      ttsAudio.play().catch(err => console.warn(err));
    } else {
      ttsAudio.pause();
      if (btn) btn.classList.remove('playing');
    }
    return;
  }
  // Stop any existing playback
  ttsStop();

  ttsActiveBubbleIdx = msgIdx;
  ttsActiveBtn = btn;
  if (btn) btn.classList.add('playing');

  try {
    const res = await fetch(`${API_BASE}/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();

    if (!data.audio || data.error) {
      console.warn('TTS not available:', data.error || 'no audio');
      ttsStop();
      return;
    }

    // Prepare the bubble for word highlighting
    const bubble = document.getElementById(`msg-bubble-${msgIdx}`);
    if (bubble && data.timestamps && data.timestamps.length > 0) {
      wrapWordsForHighlight(bubble, data.timestamps);
    }

    // Decode base64 WAV and play
    const audioBytes = Uint8Array.from(atob(data.audio), c => c.charCodeAt(0));
    const blob = new Blob([audioBytes], { type: 'audio/wav' });
    const url = URL.createObjectURL(blob);

    ttsAudio = new Audio(url);
    ttsAudio.playbackRate = 1.0;

    // Sync highlighting with audio playback
    const timestamps = data.timestamps || [];
    if (timestamps.length > 0 && bubble) {
      const wordSpans = bubble.querySelectorAll('.tts-word');
      let lastHighlighted = -1;

      const syncHighlight = () => {
        if (!ttsAudio || ttsAudio.paused) return;
        const t = ttsAudio.currentTime;
        let currentIdx = -1;
        for (let i = 0; i < wordSpans.length; i++) {
          const start = parseFloat(wordSpans[i].dataset.start || 0);
          const end = parseFloat(wordSpans[i].dataset.end || 0);
          if (t >= start && t <= end + 0.05) {
            currentIdx = i;
          }
        }
        if (currentIdx !== lastHighlighted) {
          // Remove previous highlight
          if (lastHighlighted >= 0 && lastHighlighted < wordSpans.length) {
            wordSpans[lastHighlighted].classList.remove('tts-highlight');
          }
          // Add new highlight
          if (currentIdx >= 0 && currentIdx < wordSpans.length) {
            wordSpans[currentIdx].classList.add('tts-highlight');
            // Scroll into view if needed
            wordSpans[currentIdx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
          }
          lastHighlighted = currentIdx;
        }
        ttsAnimFrame = requestAnimationFrame(syncHighlight);
      };

      ttsAudio.addEventListener('play', () => {
        ttsAnimFrame = requestAnimationFrame(syncHighlight);
      });
    }

    ttsAudio.addEventListener('ended', () => {
      ttsStop();
    });

    ttsAudio.play().catch(err => {
      console.warn('Audio autoplay blocked:', err);
      ttsStop();
    });

  } catch (err) {
    console.error('TTS fetch error:', err);
    ttsStop();
  }
}

function ttsStop() {
  if (ttsAnimFrame) {
    cancelAnimationFrame(ttsAnimFrame);
    ttsAnimFrame = null;
  }
  if (ttsAudio) {
    ttsAudio.pause();
    ttsAudio.currentTime = 0;
    if (ttsAudio.src) URL.revokeObjectURL(ttsAudio.src);
    ttsAudio = null;
  }
  if (ttsActiveBtn) {
    ttsActiveBtn.classList.remove('playing');
    ttsActiveBtn = null;
  }
  // Remove all highlights
  document.querySelectorAll('.tts-highlight').forEach(el => el.classList.remove('tts-highlight'));
  ttsActiveBubbleIdx = null;
}

function wrapWordsForHighlight(bubble, timestamps) {
  if (!timestamps || timestamps.length === 0) return;

  // 1. Safely wrap all text nodes in the bubble with <span class="tts-word">
  function wrapTextNodes(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      if (!node.nodeValue.trim()) return;
      const words = node.nodeValue.split(/(\s+)/);
      const fragment = document.createDocumentFragment();
      let hasWord = false;
      words.forEach(w => {
        if (w.trim()) {
          const span = document.createElement('span');
          span.className = 'tts-word';
          span.textContent = w;
          fragment.appendChild(span);
          hasWord = true;
        } else {
          fragment.appendChild(document.createTextNode(w));
        }
      });
      if (hasWord) {
        node.parentNode.replaceChild(fragment, node);
      }
    } else if (node.nodeType === Node.ELEMENT_NODE && !node.classList.contains('tts-word')) {
      // Traverse children backwards so replacements don't mess up indices
      const children = Array.from(node.childNodes);
      for (let i = children.length - 1; i >= 0; i--) {
        wrapTextNodes(children[i]);
      }
    }
  }

  // Preserve the bubble's original structure but wrap words
  wrapTextNodes(bubble);

  // 2. Assign start/end times to the newly created spans
  const wordSpans = bubble.querySelectorAll('.tts-word');
  
  // To avoid desync caused by TTS tokenizers splitting words differently 
  // than the DOM (e.g. "1.1" -> "one point one"), we use a proportional 
  // percentage mapping. This is extremely robust and never drifts.
  let totalChars = 0;
  wordSpans.forEach(span => totalChars += span.textContent.length);

  let charOffset = 0;
  for (let i = 0; i < wordSpans.length; i++) {
    const span = wordSpans[i];
    const spanLen = span.textContent.length;
    
    if (timestamps.length > 0 && totalChars > 0) {
      const startPct = charOffset / totalChars;
      const endPct = (charOffset + spanLen) / totalChars;
      
      let startTsIdx = Math.floor(startPct * timestamps.length);
      let endTsIdx = Math.max(0, Math.ceil(endPct * timestamps.length) - 1);
      
      if (startTsIdx >= timestamps.length) startTsIdx = timestamps.length - 1;
      if (endTsIdx >= timestamps.length) endTsIdx = timestamps.length - 1;
      
      span.dataset.start = timestamps[startTsIdx].start;
      span.dataset.end = timestamps[endTsIdx].end;
    } else {
      span.dataset.start = 0;
      span.dataset.end = 0;
    }
    charOffset += spanLen;
  }
}

// Initialize STT on page load
initSTT();

// ── Start ──────────────────────────────────────
init();


btnUploadScenario.addEventListener('click', () => { fileInputScenario.click(); });

// ── Scenario ingestion ─────────────────────────
// Extraction runs N sequential LLM calls over the document, so it routinely
// takes minutes. The server returns a job id immediately and we poll it.

const ulOverlay  = $('#upload-overlay');
const ulStages   = $('#ul-stages');
const ulMessage  = $('#ul-message');
const ulFilename = $('#ul-filename');
const ulPages    = $('#ul-pages');
const ulKind     = $('#ul-kind');
const ulElapsed  = $('#ul-elapsed');
const ulDismiss  = $('#ul-dismiss');
const ulHint     = $('#ul-hint');
const ulTitle    = $('#ul-title');
const ulRingFill = document.querySelector('#upload-overlay .ring-fill');

const UL_ORDER = ['parsing', 'rendering', 'analysing', 'indexing'];
const UL_CIRCUMFERENCE = 377;
let ulTimer = null;
let ulStart = 0;

function ulSetRing(fraction) {
  if (!ulRingFill) return;
  const clamped = Math.max(0, Math.min(1, fraction));
  ulRingFill.style.strokeDashoffset = String(UL_CIRCUMFERENCE * (1 - clamped));
}

// Stage weights reflect where the time actually goes: analysis dominates.
function ulFraction(stage, current, total) {
  switch (stage) {
    case 'queued':    return 0;
    case 'parsing':   return 0.04;
    case 'rendering': return 0.12;
    case 'analysing': return total > 0 ? 0.15 + (current / total) * 0.72 : 0.15;
    case 'indexing':  return 0.92;
    case 'done':      return 1;
    default:          return 0;
  }
}

function ulRenderStages(stage) {
  const activeIdx = UL_ORDER.indexOf(stage);
  [...ulStages.children].forEach((li, i) => {
    if (stage === 'done') li.dataset.state = 'done';
    else if (activeIdx === -1) li.removeAttribute('data-state');
    else if (i < activeIdx) li.dataset.state = 'done';
    else if (i === activeIdx) li.dataset.state = 'active';
    else li.removeAttribute('data-state');
  });
}

function ulTick() {
  const secs = Math.floor((Date.now() - ulStart) / 1000);
  ulElapsed.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
}

function ulOpen(file) {
  const ext = (file.name.split('.').pop() || '').toUpperCase();
  ulKind.textContent = ext.slice(0, 4) || 'FILE';
  ulFilename.textContent = file.name;
  ulPages.textContent = '';
  ulTitle.textContent = 'Ingesting scenario';
  ulMessage.textContent = 'Uploading document';
  ulHint.hidden = false;
  ulDismiss.hidden = true;
  ulOverlay.dataset.active = 'true';
  ulOverlay.dataset.indeterminate = 'true';
  delete ulOverlay.dataset.state;
  ulRenderStages('parsing');
  ulSetRing(0);
  ulOverlay.hidden = false;
  ulStart = Date.now();
  ulTick();
  ulTimer = setInterval(ulTick, 1000);
}

function ulFinish({ state, title, message, showReload }) {
  clearInterval(ulTimer);
  ulOverlay.dataset.state = state;
  ulOverlay.dataset.active = 'false';
  ulOverlay.dataset.indeterminate = 'false';
  ulTitle.textContent = title;
  ulMessage.textContent = message;
  ulHint.hidden = true;
  ulDismiss.hidden = false;
  ulDismiss.textContent = showReload ? 'Start exercise' : 'Close';
  ulSetRing(state === 'done' ? 1 : 0.999);
  if (state === 'done') ulRenderStages('done');
  // Nothing is in progress any more — don't leave a stage looking active.
  else [...ulStages.children].forEach(li => li.removeAttribute('data-state'));
  ulDismiss.onclick = () => {
    ulOverlay.hidden = true;
    if (showReload) window.location.reload();
  };
  ulDismiss.focus();
}

async function ulPoll(jobId) {
  while (true) {
    await new Promise(r => setTimeout(r, 1200));
    let job;
    try {
      const res = await fetch(`/api/scenario/upload/${jobId}`);
      if (res.status === 404) {
        ulFinish({ state: 'error', title: 'Upload lost',
          message: 'The server restarted before extraction finished. Upload the document again.' });
        return;
      }
      job = await res.json();
    } catch (err) {
      continue; // transient network blip — keep polling
    }

    if (job.stage === 'analysing' && job.total > 0) ulOverlay.dataset.indeterminate = 'false';
    if (job.page_count) {
      ulPages.textContent = `${job.page_count} page${job.page_count === 1 ? '' : 's'}`;
    }
    ulMessage.textContent = job.message || '';
    ulRenderStages(job.stage);
    ulSetRing(ulFraction(job.stage, job.current, job.total));

    if (job.done) {
      if (job.error) {
        ulFinish({ state: 'error', title: 'Extraction failed', message: job.error });
      } else {
        const n = job.result?.inject_count ?? 0;
        ulFinish({
          state: 'done', title: 'Scenario ready', showReload: true,
          message: `Extracted ${n} inject${n === 1 ? '' : 's'} from ${job.filename}.`,
        });
      }
      return;
    }
  }
}

fileInputScenario.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;

  if (/\.doc$/i.test(file.name)) {
    ulOpen(file);
    ulFinish({
      state: 'error', title: 'Save as .docx first',
      message: 'Legacy .doc files cannot be read. Open it in Word, choose File > Save As, pick Word Document (.docx), then upload again.',
    });
    return;
  }

  ulOpen(file);
  btnUploadScenario.disabled = true;
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/scenario/upload', { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok || !data.job_id) {
      ulFinish({ state: 'error', title: 'Upload rejected',
        message: data.message || 'The server would not accept this document.' });
      return;
    }
    await ulPoll(data.job_id);
  } catch (err) {
    console.error(err);
    ulFinish({ state: 'error', title: 'Upload failed',
      message: 'Could not reach the server. Check that it is running, then try again.' });
  } finally {
    btnUploadScenario.disabled = false;
  }
});
