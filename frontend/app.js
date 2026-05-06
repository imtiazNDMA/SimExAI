/* ═══════════════════════════════════════════════
   SimexAI — Application Logic
   ═══════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000/api';

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
const btnShowActions  = $('#btn-show-actions');
const actionsModal    = $('#actions-modal');
const actionsList     = $('#actions-list');
const actionsModalTitle = $('#actions-modal-title');
const btnCloseActions = $('#btn-close-actions');
const btnSend         = $('#btn-send');
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

  const [wingsData, phasesData] = await Promise.all([
    api('/wings'),
    api('/phases'),
  ]);

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
  btnShowActions.disabled = false;
  chatInput.focus();

  renderMessages();

  if (!state.messages[wingId] || state.messages[wingId].length === 0) {
    sendGreeting(wingId);
  }
}

async function sendGreeting(wingId) {
  const phaseId = state.currentPhase ? state.currentPhase.id : 'd_day';
  showTypingIndicator();
  const data = await api('/chat', {
    method: 'POST',
    body: JSON.stringify({ wing_id: wingId, phase_id: phaseId, message: 'hello' }),
  });
  hideTypingIndicator();
  if (data) addMessage(wingId, 'system', data.response, data.wing_name);
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

  chatMessages.innerHTML = msgs.map(m => {
    if (m.type === 'notification') {
      return `
        <div class="message notification">
          <div class="message-bubble">${formatText(m.text)}</div>
        </div>`;
    }
    return `
      <div class="message ${m.type}">
        ${m.type === 'system' ? `<span class="message-label">${m.wingName}</span>` : ''}
        <div class="message-bubble">${formatText(m.text)}</div>
        <span class="message-time">${m.time}</span>
      </div>`;
  }).join('');

  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function buildWelcomeHTML() {
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
        <p class="welcome-cta">← Select a wing from the sidebar to begin</p>
      </div>
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
  const phaseId = state.currentPhase ? state.currentPhase.id : 'd_day';

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
    sendGreeting(state.activeWing.id);
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
  if (!confirm('Reset exercise to D Day? All chat history will be cleared.')) return;
  const data = await api('/phase/reset', { method: 'POST' });
  if (data?.phases) {
    state.phases      = data.phases;
    state.currentPhase = data.phases.find(p => p.is_active);
    state.messages    = {};
    state.activeWing  = null;

    renderTimeline();
    chatMessages.innerHTML = buildWelcomeHTML();
    chatWingName.textContent  = 'Select a Wing';
    chatWingIcon.textContent  = '🎯';
    chatPhaseLabel.textContent = '—';
    chatInput.disabled = true;
    btnSend.disabled   = true;
    btnShowActions.disabled = true;
    wingList.querySelectorAll('.wing-item').forEach(el => el.classList.remove('active'));
    await loadInjects();
    showToast('Exercise reset to D Day');
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

// ── Start ──────────────────────────────────────
init();
