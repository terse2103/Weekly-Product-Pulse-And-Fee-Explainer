/**
 * script.js — Weekly Product Pulse Web UI
 *
 * Responsibilities:
 *   1. On load: fetch /api/note  → render markdown → update header badges.
 *   2. On load: fetch /api/status → update the pipeline status card.
 *   3. Refresh button: re-fetch latest note.
 *   4. Send form: validate fields, POST /api/send, show toast.
 */

/* ── Constants ───────────────────────────────────────────────────── */
// BACKEND_URL is injected by index.html for Vercel deployment
// (window.__BACKEND_URL__ = "https://your-backend.streamlit.app")
// Falls back to relative paths for local development with FastAPI.
const _BASE = (typeof window.__BACKEND_URL__ !== 'undefined' && window.__BACKEND_URL__)
  ? window.__BACKEND_URL__.replace(/\/$/, '')  // strip trailing slash
  : '';

// Detect if we are loading statically (e.g., from GitHub Raw JSON)
const IS_STATIC_FILE = _BASE.endsWith('.json');

const API = {
  note:   IS_STATIC_FILE ? _BASE : `${_BASE}/api/note`,
  send:   `${_BASE}/api/send`,
  status: `${_BASE}/api/status`,
};

/* ── DOM refs ────────────────────────────────────────────────────── */
const $noteContent  = document.getElementById('note-content');
const $noteSkeleton = document.getElementById('note-skeleton');
const $noteError    = document.getElementById('note-error');
const $badgeDate    = document.getElementById('badge-date');

const $statusDot    = document.getElementById('status-dot');
const $statusLabel  = document.getElementById('status-label');
const $statusDetail = document.getElementById('status-detail');

const $form         = document.getElementById('send-form');
const $inputName    = document.getElementById('recipient-name');
const $inputEmail   = document.getElementById('recipient-email');
const $nameError    = document.getElementById('name-error');
const $emailError   = document.getElementById('email-error');
const $btnSend      = document.getElementById('btn-send');
const $btnText      = document.getElementById('btn-text');
const $btnSpinner   = document.getElementById('btn-spinner');

const $toast        = document.getElementById('toast');
const $toastIcon    = document.getElementById('toast-icon');
const $toastMsg     = document.getElementById('toast-message');
const $statsCard    = document.getElementById('stats-card');
const $statsList    = document.getElementById('stats-list');

/* ── State ──────────────────────────────────────────────────────── */
let _toastTimer = null;
let _currentNote = null;  // cached note response object

/* ── Helpers ────────────────────────────────────────────────────── */

/**
 * Renders the markdown note using marked.js.
 * Falls back to a <pre> block if marked isn't available.
 */
function renderMarkdown(md) {
  if (typeof marked !== 'undefined') {
    // Configure marked for safe, clean output
    marked.setOptions({
      gfm: true,
      breaks: true,
    });
    return marked.parse(md);
  }
  // Fallback: escape HTML and wrap in <pre>
  const escaped = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return `<pre style="white-space:pre-wrap">${escaped}</pre>`;
}

/**
 * Formats a date string like "2026-03-12" → "12 Mar 2026".
 */
function formatDate(dateStr) {
  if (!dateStr || dateStr === '—') return '—';
  try {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return dateStr;
  }
}

/**
 * Shows the status dot with the given class.
 * @param {'idle'|'running'|'completed'|'failed'|'has-note'} state
 */
function setStatusDot(state) {
  $statusDot.className = `status-dot ${state}`;
}

/**
 * Shows or hides a toast notification.
 * @param {'success'|'error'} type
 * @param {string} message
 * @param {number} duration  — ms before auto-hide (0 = permanent)
 */
function showToast(type, message, duration = 5000) {
  clearTimeout(_toastTimer);
  $toast.className = `toast ${type}`;
  $toastIcon.textContent  = type === 'success' ? '✅' : '❌';
  $toastMsg.textContent   = message;
  $toast.hidden = false;

  if (duration > 0) {
    _toastTimer = setTimeout(() => { $toast.hidden = true; }, duration);
  }
}

/**
 * Clears all form validation states.
 */
function clearValidation() {
  [$inputName, $inputEmail].forEach(el => el.classList.remove('invalid'));
  $nameError.textContent  = '';
  $emailError.textContent = '';
}

/**
 * Simple email regex.
 */
function isValidEmail(val) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
}

/**
 * Validates the form; returns true if valid, false otherwise.
 */
function validateForm() {
  let valid = true;
  clearValidation();

  if (!$inputName.value.trim()) {
    $inputName.classList.add('invalid');
    $nameError.textContent = 'Recipient name is required.';
    valid = false;
  }
  if (!$inputEmail.value.trim()) {
    $inputEmail.classList.add('invalid');
    $emailError.textContent = 'Email address is required.';
    valid = false;
  } else if (!isValidEmail($inputEmail.value)) {
    $inputEmail.classList.add('invalid');
    $emailError.textContent = 'Please enter a valid email address.';
    valid = false;
  }
  return valid;
}

/* ── Note loading ───────────────────────────────────────────────── */

async function loadNote() {
  // Show skeleton, hide others
  $noteSkeleton.hidden = false;
  $noteContent.hidden  = true;
  $noteError.hidden    = true;
  $statsCard.hidden    = true;

  try {
    const res = await fetch(API.note);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _currentNote = data;

    // Render markdown
    $noteContent.innerHTML = renderMarkdown(data.markdown);
    $noteSkeleton.hidden   = true;
    $noteContent.hidden    = false;

    // Update header badges
    $badgeDate.textContent  = formatDate(data.date);

    // Populate stats card
    renderStats(data);

  } catch (err) {
    console.error('Failed to load note:', err);
    $noteSkeleton.hidden = true;
    $noteError.hidden    = false;
  }
}

/**
 * Populates the quick-stats card with data extracted from the API response.
 */
function renderStats(data) {
  $statsList.innerHTML = '';

  const items = [
    { key: 'Note date',   val: formatDate(data.date) },
    { key: 'File',        val: data.filename },
  ];

  items.forEach(({ key, val }) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <span class="stat-key">${key}</span>
      <span class="stat-val">${val}</span>
    `;
    $statsList.appendChild(li);
  });

  $statsCard.hidden = false;
}

/* ── Pipeline status ────────────────────────────────────────────── */

async function loadStatus() {
  if (typeof IS_STATIC_FILE !== 'undefined' && IS_STATIC_FILE) {
    setStatusDot('has-note');
    $statusLabel.textContent = 'Dashboard (Static View)';
    $statusDetail.textContent = 'Syncs via GitHub updates.';
    return;
  }

  try {
    const res = await fetch(API.status);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const stateMap = {
      idle:      { label: 'Pipeline idle',    dot: 'idle' },
      running:   { label: 'Pipeline running…', dot: 'running' },
      completed: { label: 'Pipeline complete', dot: 'completed' },
      failed:    { label: 'Pipeline failed',   dot: 'failed' },
    };

    // If a note exists, show as "Note ready" even when idle
    const noteExists = !!data.last_note_file;
    const statusKey  = noteExists && data.status === 'idle' ? 'completed' : (data.status || 'idle');
    const mapped     = stateMap[statusKey] || stateMap.idle;

    setStatusDot(noteExists ? 'has-note' : mapped.dot);
    $statusLabel.textContent = noteExists ? 'Note ready' : mapped.label;

    if (data.last_run) {
      const ago = timeSince(data.last_run);
      $statusDetail.textContent = `Last run: ${ago}`;
    } else if (data.last_note_file) {
      $statusDetail.textContent = `File: ${data.last_note_file}`;
    } else {
      $statusDetail.textContent = 'Run the pipeline to generate a note.';
    }
  } catch (err) {
    console.warn('Status fetch failed:', err);
    setStatusDot('idle');
    $statusLabel.textContent = 'Status unavailable';
  }
}

/**
 * Human-readable "X minutes ago" helper.
 */
function timeSince(isoString) {
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diff < 60)    return `${diff}s ago`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/* ── Send form ──────────────────────────────────────────────────── */

async function handleSend(e) {
  e.preventDefault();
  $toast.hidden = true;

  if (typeof IS_STATIC_FILE !== 'undefined' && IS_STATIC_FILE) {
    showToast('error', 'Sending disabled. Please use the Streamlit Admin Panel to dispatch emails.');
    return;
  }

  if (!validateForm()) return;

  // Lock UI
  $btnSend.disabled    = true;
  $btnText.textContent = 'Sending…';
  $btnSpinner.hidden   = false;

  try {
    const payload = {
      recipient_name:  $inputName.value.trim(),
      recipient_email: $inputEmail.value.trim(),
    };

    const res = await fetch(API.send, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });

    const data = await res.json();

    if (res.ok && data.status === 'sent') {
      showToast('success', data.message);
      $form.reset();
      clearValidation();
      // Refresh status after a successful send
      setTimeout(loadStatus, 600);
    } else {
      const errMsg = data.detail || data.message || 'Unknown error. Please try again.';
      showToast('error', errMsg);
    }
  } catch (err) {
    console.error('Send failed:', err);
    showToast('error', 'Network error — could not reach the server.');
  } finally {
    $btnSend.disabled    = false;
    $btnText.textContent = 'Send Weekly Pulse';
    $btnSpinner.hidden   = true;
  }
}

/* ── Clear validation on input ──────────────────────────────────── */
$inputName.addEventListener('input', () => {
  $inputName.classList.remove('invalid');
  $nameError.textContent = '';
});
$inputEmail.addEventListener('input', () => {
  $inputEmail.classList.remove('invalid');
  $emailError.textContent = '';
});

/* ── Event listeners ────────────────────────────────────────────── */
$form.addEventListener('submit', handleSend);

/* ── Init ───────────────────────────────────────────────────────── */
(async function init() {
  // Set footer links to point at the backend
  const $footerDocs     = document.getElementById('footer-docs');
  const $footerNoteJson = document.getElementById('footer-note-json');
  if ($footerDocs)     $footerDocs.href     = `${_BASE}/docs`;
  if ($footerNoteJson) $footerNoteJson.href = API.note;

  // Kick off both fetches in parallel
  await Promise.allSettled([loadNote(), loadStatus()]);
})();
