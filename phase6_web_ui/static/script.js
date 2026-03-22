/**
 * script.js — Weekly Product Pulse Web UI
 *
 * Responsibilities:
 *   1. On load: fetch /api/note  → render markdown → update header badges.
 *   2. On load: fetch /api/status → update the pipeline status card.
 *   3. "Run Pipeline" button: POST /api/run → poll /api/status until done, then reload note.
 *   4. Send form: validate fields, POST /api/send, show toast.
 */

/* ── Constants ───────────────────────────────────────────────────── */
// BACKEND_URL is injected by index.html for Vercel deployment.
// Set window.__BACKEND_URL__ to your deployed FastAPI URL, e.g.:
//   window.__BACKEND_URL__ = 'https://your-app.streamlit.app';
// Leave as '' to use relative paths when running locally with FastAPI.
const _BASE = (typeof window.__BACKEND_URL__ !== 'undefined' && window.__BACKEND_URL__)
  ? window.__BACKEND_URL__.replace(/\/$/, '')  // strip trailing slash
  : '';

const API = {
  note:   `${_BASE}/api/note`,
  send:   `${_BASE}/api/send`,
  status: `${_BASE}/api/status`,
  run:    `${_BASE}/api/run`,
};

/* ── DOM refs ────────────────────────────────────────────────────── */
const $noteContent  = document.getElementById('note-content');
const $noteSkeleton = document.getElementById('note-skeleton');
const $noteError    = document.getElementById('note-error');
const $badgeDate    = document.getElementById('badge-date');

const $statusDot    = document.getElementById('status-dot');
const $statusLabel  = document.getElementById('status-label');
const $statusDetail = document.getElementById('status-detail');

const $btnRun       = document.getElementById('btn-run');
const $btnRunText   = document.getElementById('btn-run-text');
const $btnRunSpinner= document.getElementById('btn-run-spinner');
const $runResult    = document.getElementById('run-result');

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
let _toastTimer  = null;
let _currentNote = null;   // cached note response object
let _pollTimer   = null;   // pipeline polling interval

/* ── Helpers ────────────────────────────────────────────────────── */

/**
 * Renders the markdown note using marked.js.
 * Falls back to a <pre> block if marked isn't available.
 */
function renderMarkdown(md) {
  if (typeof marked !== 'undefined') {
    marked.setOptions({ gfm: true, breaks: true });
    return marked.parse(md);
  }
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
 * Sets the status dot visual state.
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
  $toastIcon.textContent = type === 'success' ? '✅' : '❌';
  $toastMsg.textContent  = message;
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
 * Validates the form; returns true if valid.
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

/* ── Note loading ───────────────────────────────────────────────── */

async function loadNote() {
  $noteSkeleton.hidden = false;
  $noteContent.hidden  = true;
  $noteError.hidden    = true;
  $statsCard.hidden    = true;

  try {
    const res = await fetch(API.note);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    _currentNote = data;

    $noteContent.innerHTML = renderMarkdown(data.markdown);
    $noteSkeleton.hidden   = true;
    $noteContent.hidden    = false;

    $badgeDate.textContent = formatDate(data.date);

    renderStats(data);
  } catch (err) {
    console.error('Failed to load note:', err);
    $noteSkeleton.hidden = true;
    $noteError.hidden    = false;
  }
}

/**
 * Populates the quick-stats card.
 */
function renderStats(data) {
  $statsList.innerHTML = '';

  const items = [
    { key: 'Note date', val: formatDate(data.date) },
    { key: 'File',      val: data.filename },
    { key: 'Words',     val: data.word_count },
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

    const noteExists = !!data.last_note_file;
    const isRunning  = typeof data.status === 'string' && data.status.startsWith('running');
    const statusKey  = noteExists && !isRunning ? 'completed' : (data.status || 'idle');
    const mapped     = stateMap[statusKey] || stateMap.idle;

    setStatusDot(noteExists && !isRunning ? 'has-note' : mapped.dot);
    $statusLabel.textContent = noteExists && !isRunning ? 'Note ready' : mapped.label;

    if (data.last_run) {
      $statusDetail.textContent = `Last run: ${timeSince(data.last_run)}`;
    } else if (data.last_note_file) {
      $statusDetail.textContent = `File: ${data.last_note_file}`;
    } else {
      $statusDetail.textContent = 'Click "Run Pipeline" to generate a note.';
    }

    return data.status;  // return raw status for polling
  } catch (err) {
    console.warn('Status fetch failed:', err);
    setStatusDot('idle');
    $statusLabel.textContent  = 'Status unavailable';
    $statusDetail.textContent = '';
    return 'idle';
  }
}

/* ── Run Pipeline ───────────────────────────────────────────────── */

async function runPipeline() {
  // Lock button
  $btnRun.disabled       = true;
  $btnRunText.textContent = 'Running…';
  $btnRunSpinner.hidden  = false;
  $runResult.hidden      = true;

  try {
    const res = await fetch(API.run, { method: 'POST' });
    const data = await res.json();

    if (res.status === 409) {
      // Already running
      $runResult.textContent = '⚠️ Pipeline is already running.';
      $runResult.className   = 'run-result error';
      $runResult.hidden      = false;
      return;
    }

    if (!res.ok) {
      throw new Error(data.detail || 'Failed to start pipeline.');
    }

    // Show "started" feedback
    $runResult.textContent = '⏳ Pipeline started — this may take a few minutes.';
    $runResult.className   = 'run-result info';
    $runResult.hidden      = false;

    // Poll /api/status every 5 seconds until done
    clearInterval(_pollTimer);
    setStatusDot('running');
    $statusLabel.textContent  = 'Pipeline running…';
    $statusDetail.textContent = 'Fetching reviews, generating themes…';

    _pollTimer = setInterval(async () => {
      const status = await loadStatus();
      if (status && !status.startsWith('running') && status !== 'idle' || status === 'idle') {
        // pipeline finished (back to idle means completed successfully)
        clearInterval(_pollTimer);
        $btnRun.disabled        = false;
        $btnRunText.textContent = '🚀 Run Pipeline';
        $btnRunSpinner.hidden   = true;

        if (status.startsWith('error')) {
          $runResult.textContent = `❌ Pipeline error: ${status}`;
          $runResult.className   = 'run-result error';
        } else {
          $runResult.textContent = '✅ Pipeline completed! Refreshing note…';
          $runResult.className   = 'run-result success';
          setTimeout(() => { loadNote(); }, 800);
        }
        setTimeout(() => { $runResult.hidden = true; }, 7000);
      }
    }, 5000);

  } catch (err) {
    console.error('Run pipeline failed:', err);
    $runResult.textContent = `❌ ${err.message}`;
    $runResult.className   = 'run-result error';
    $runResult.hidden      = false;
    $btnRun.disabled        = false;
    $btnRunText.textContent = '🚀 Run Pipeline';
    $btnRunSpinner.hidden   = true;
  }
}

/* ── Send form ──────────────────────────────────────────────────── */

async function handleSend(e) {
  e.preventDefault();
  $toast.hidden = true;

  if (!validateForm()) return;

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
$btnRun.addEventListener('click', runPipeline);

/* ── Init ───────────────────────────────────────────────────────── */
(async function init() {
  const $footerDocs     = document.getElementById('footer-docs');
  const $footerNoteJson = document.getElementById('footer-note-json');
  if ($footerDocs)     $footerDocs.href     = `${_BASE}/docs`;
  if ($footerNoteJson) $footerNoteJson.href  = API.note;

  await Promise.allSettled([loadNote(), loadStatus()]);
})();
