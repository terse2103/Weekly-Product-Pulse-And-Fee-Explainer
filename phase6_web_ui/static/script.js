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
 * Post-processes the rendered note content.
 * Finds the "Top 3 Themes" / "Top 3 themes" section and enhances each
 * theme list item by:
 *   1. Showing the review count as a styled bracket-badge next to the theme name.
 *   2. Moving the description text to a separate <p> below the theme heading.
 *
 * Supported line formats (all produced by Phase 5):
 *   "ThemeName: N reviews. Description text"
 *   "ThemeName: N reviews. Description: Description text"
 *   "**ThemeName** (N reviews): Description text"  (older format)
 */
function enhanceThemeSection(container) {
  // Find the section heading that contains 'theme' (case-insensitive)
  const headings = container.querySelectorAll('h1, h2, h3, h4');
  let themeHeading = null;
  for (const h of headings) {
    if (/top.*theme/i.test(h.textContent)) {
      themeHeading = h;
      break;
    }
  }
  if (!themeHeading) return;

  // Remove leading digit (e.g. "Top 3 Themes" → "Top Themes")
  themeHeading.textContent = themeHeading.textContent
    .replace(/\bTop\s+\d+\s+/i, 'Top ')
    .trim();

  // The theme list is the first <ul> or <ol> after the heading
  let sibling = themeHeading.nextElementSibling;
  while (sibling && sibling.tagName !== 'UL' && sibling.tagName !== 'OL') {
    sibling = sibling.nextElementSibling;
  }
  if (!sibling) return;

  const listItems = sibling.querySelectorAll(':scope > li');
  listItems.forEach(li => {
    const raw = li.innerHTML; // may contain <strong> from markdown
    const text = li.textContent.trim();

    // ── Pattern A: "Theme Name: N reviews. [Description: ]Text here"
    // e.g. "User Experience: 173 reviews. Users comment on usability."
    const patA = /^([^:]+):\s*(\d+)\s+reviews\.\s*(?:Description:\s*)?(.*)$/i;

    // ── Pattern B: Older markdown style: "Theme Name (N reviews): Description"
    // (Note: textContent strips the <strong> tags, so we don't look for asterisks here)
    // e.g. "User Experience (129 reviews): Users provide feedback…"
    const patB = /^([^(]+)\s*\((\d+)\s+reviews?\):\s*(.*)$/i;

    let themeName = null, reviewCount = null, description = null;

    const mA = text.match(patA);
    const mB = text.match(patB);

    if (mA) {
      themeName   = mA[1].trim();
      reviewCount = mA[2].trim();
      description = mA[3].trim();
    } else if (mB) {
      themeName   = mB[1].trim();
      reviewCount = mB[2].trim();
      description = mB[3].trim();
    }

    if (!themeName) return; // unrecognised format — leave untouched

    // Build the enhanced inner HTML
    const descHtml = description
      ? `<p class="theme-desc">${description}</p>`
      : '';

    li.innerHTML = `
      <span class="theme-header">
        <span class="theme-name">${themeName}</span>
        <span class="theme-review-badge">[${reviewCount} reviews]</span>
      </span>
      ${descHtml}
    `;
    li.classList.add('theme-item');
  });
}

/**
 * Strips leading numbers from section headings that match patterns like
 * "3 User Quotes" → "User Quotes"  or  "3 Action Ideas" → "Action Ideas".
 * Also highlights key financial/action keywords in fee explanation bullets.
 */
function enhanceOtherSections(container) {
  // ── Strip "3" from headings like "3 User Quotes", "3 Action Ideas/Items" ──
  const headings = container.querySelectorAll('h1, h2, h3, h4');
  headings.forEach(h => {
    // Remove a leading digit followed by whitespace from the visible heading
    if (/^\d+\s+/i.test(h.textContent.trim())) {
      h.textContent = h.textContent.trim().replace(/^\d+\s+/, '');
    }
  });

  // ── Highlight key words in fee explanation bullet points ──────────────────
  // Locate the fee explanation section by its heading text
  let feeHeading = null;
  for (const h of headings) {
    if (/fee\s+explanation/i.test(h.textContent)) {
      feeHeading = h;
      break;
    }
  }
  if (!feeHeading) return;

  // Walk siblings until the next same-level heading or end
  const feeLevel = parseInt(feeHeading.tagName[1], 10);
  let el = feeHeading.nextElementSibling;
  const FEE_KEYWORDS = [
    'exit load', 'redemption', 'mutual fund', 'holding period',
    'nil exit load', 'equity', 'liquid fund', 'graded', 'SID',
    'Scheme Information Document', 'fund house', '1%', '1 year',
    'percentage', 'proceeds',
  ];

  while (el) {
    // Stop at the next heading of same or higher level
    if (/^H[1-4]$/.test(el.tagName)) {
      const lvl = parseInt(el.tagName[1], 10);
      if (lvl <= feeLevel) break;
    }
    // Process list items within this element
    const items = el.tagName === 'LI' ? [el] : [...el.querySelectorAll('li')];
    items.forEach(li => {
      let html = li.innerHTML;
      FEE_KEYWORDS.forEach(kw => {
        // Escape any regex special characters in the keyword
        const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const re = new RegExp(`(?<!<[^>]*)\\b(${escaped})\\b`, 'gi');
        html = html.replace(re, '<mark class="fee-kw">$1</mark>');
      });
      li.innerHTML = html;
    });
    el = el.nextElementSibling;
  }
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
    // Post-process the rendered HTML to enhance the themes section
    enhanceThemeSection($noteContent);
    // Strip leading numbers from other section headings; highlight fee keywords
    enhanceOtherSections($noteContent);
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
