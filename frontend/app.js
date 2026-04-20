/* SCI-EXP CRITIQUE v2.1 — Frontend App Logic */

const API = '/api/v1';

// ── DOM refs ──────────────────────────────────────────────────────────────────
const dropZone     = document.getElementById('dropZone');
const fileInput    = document.getElementById('fileInput');
const fileInfo     = document.getElementById('fileInfo');
const fileName     = document.getElementById('fileName');
const clearFile    = document.getElementById('clearFile');
const submitBtn    = document.getElementById('submitBtn');
const templateSel  = document.getElementById('templateSelect');
const roundInput   = document.getElementById('roundInput');
const outputFormat = document.getElementById('outputFormat');

const uploadPanel   = document.getElementById('uploadPanel');
const progressPanel = document.getElementById('progressPanel');
const resultPanel   = document.getElementById('resultPanel');
const errorPanel    = document.getElementById('errorPanel');

const progressLabel  = document.getElementById('progressLabel');
const progressBar    = document.getElementById('progressBar');
const resultMeta     = document.getElementById('resultMeta');
const downloadGroup  = document.getElementById('downloadGroup');
const precheckRow    = document.getElementById('precheckRow');
const stepsContainer = document.getElementById('stepsContainer');
const priorityBox    = document.getElementById('priorityBox');
const errorMsg       = document.getElementById('errorMsg');

let selectedFile = null;
let lastReport   = null;

// ── File selection ────────────────────────────────────────────────────────────
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});
fileInput.addEventListener('change', () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });
clearFile.addEventListener('click', clearSelection);

function setFile(f) {
  selectedFile = f;
  fileName.textContent = f.name;
  fileInfo.classList.remove('hidden');
  dropZone.classList.add('hidden');
  submitBtn.disabled = false;
}

function clearSelection() {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.classList.add('hidden');
  dropZone.classList.remove('hidden');
  submitBtn.disabled = true;
}

// ── Submit ────────────────────────────────────────────────────────────────────
submitBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  const format   = outputFormat.value;
  const template = templateSel.value;
  const round    = parseInt(roundInput.value) || 1;

  showProgress('Running PRECHECK...', 10);

  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('template', template);
  fd.append('round_number', round);

  try {
    if (format === 'preview') {
      await runPreview(fd);
    } else {
      fd.append('format', format);
      await runDownload(fd, format);
    }
  } catch (err) {
    showError(err.message || 'Unexpected error. Check server logs.');
  }
});

async function runPreview(fd) {
  setProgress('Uploading & extracting text...', 30);
  const res = await fetch(`${API}/critique/upload`, { method: 'POST', body: fd });
  setProgress('Running STEP 0-5 pipeline...', 70);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  const report = await res.json();
  lastReport = report;
  setProgress('Rendering report...', 95);
  await new Promise(r => setTimeout(r, 300));
  renderReport(report);
}

async function runDownload(fd, format) {
  setProgress(`Generating ${format.toUpperCase()} report...`, 40);
  const res = await fetch(`${API}/critique/download`, { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  setProgress('Download ready!', 100);
  const blob = await res.blob();
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href     = url;
  a.download = `sciexp_critique.${format}`;
  a.click();
  URL.revokeObjectURL(url);
  showUpload();
}

// ── Render report (preview mode) ─────────────────────────────────────────────
function renderReport(r) {
  hideAll();
  resultPanel.classList.remove('hidden');

  // Meta line
  resultMeta.innerHTML = `
    <strong>Template:</strong> ${r.experiment_class || '—'} &nbsp;|&nbsp;
    <strong>Omega:</strong> ${r.omega_score.toFixed(4)} &nbsp;|&nbsp;
    <strong>Round:</strong> ${r.round_number} &nbsp;|&nbsp;
    <strong>Not-Traceable:</strong> ${r.not_traceable_count} &nbsp;
    <strong>Partial:</strong> ${r.partially_traceable_count}
  `;

  // Download buttons
  downloadGroup.innerHTML = ['md','docx','pdf'].map(fmt =>
    `<button class="btn-download" data-format="${fmt}">↓ ${fmt.toUpperCase()}</button>`
  ).join('');
  downloadGroup.querySelectorAll('.btn-download').forEach(btn => {
    btn.addEventListener('click', () => reDownload(btn.dataset.format));
  });

  // PRECHECK badge
  const mode = r.precheck.mode;
  const badgeClass = { FULL:'badge-full', PARTIAL:'badge-partial', LIMITED:'badge-limited', BLOCKED:'badge-blocked' }[mode] || 'badge-partial';
  const missing = r.precheck.missing_artifacts.length ? ` — Missing: ${r.precheck.missing_artifacts.join(', ')}` : '';
  precheckRow.innerHTML = `<span class="precheck-badge ${badgeClass}">${r.precheck.line1}${missing}</span>`;

  // Steps
  stepsContainer.innerHTML = '';
  const stepNames = { '0':'Experiment Class', '1':'Claim Integrity (40%)', '2':'Traceability Audit (30%)',
                      '3':'Series Continuity (20%)', '4':'Publication Readiness (10%)', '5':'Priority Fix' };
  r.steps.forEach(step => {
    const card  = document.createElement('div');
    card.className = 'step-card';
    card.innerHTML = `
      <div class="step-header" onclick="this.nextElementSibling.classList.toggle('hidden')">
        <span class="step-title">STEP ${step.step_id} — ${stepNames[step.step_id] || ''}</span>
        <span class="step-weight">${step.weight > 0 ? (step.weight*100)+'%' : ''}</span>
      </div>
      <div class="step-body ${step.step_id !== '1' ? 'hidden' : ''}">
        <p class="step-prose">${escHtml(step.prose)}</p>
        ${step.findings.length ? `
          <ul class="findings-list">
            ${step.findings.map(f => `
              <li class="finding-item tc-${f.traceability.replace(/ /g,'-')}">
                <b>[${f.code}]</b> ${escHtml(f.description)}
                ${f.verbatim_quote ? `<em> — "${escHtml(f.verbatim_quote)}"</em>` : ''}
              </li>
            `).join('')}
          </ul>
        ` : ''}
      </div>
    `;
    stepsContainer.appendChild(card);
  });

  // Priority Fix
  priorityBox.innerHTML = `
    <div class="priority-label">[!] PRIORITY FIX</div>
    <div>${escHtml(r.priority_fix)}</div>
    ${r.next_liability ? `<div class="next-liability">Next Liability: ${escHtml(r.next_liability)}</div>` : ''}
  `;
}

async function reDownload(format) {
  if (!selectedFile) return;
  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('template', templateSel.value);
  fd.append('round_number', parseInt(roundInput.value) || 1);
  fd.append('format', format);
  try {
    const res = await fetch(`${API}/critique/download`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `sciexp_critique.${format}`; a.click();
    URL.revokeObjectURL(url);
  } catch (e) { alert('Download failed: ' + e.message); }
}

// ── UI helpers ────────────────────────────────────────────────────────────────
document.getElementById('newAnalysisBtn').addEventListener('click', showUpload);
document.getElementById('errorRetryBtn').addEventListener('click', showUpload);

function showUpload() { hideAll(); uploadPanel.classList.remove('hidden'); clearSelection(); }
function hideAll() {
  [uploadPanel, progressPanel, resultPanel, errorPanel].forEach(p => p.classList.add('hidden'));
}
function showProgress(label, pct) {
  hideAll();
  progressPanel.classList.remove('hidden');
  progressLabel.textContent = label;
  progressBar.style.width = pct + '%';
}
function setProgress(label, pct) {
  progressLabel.textContent = label;
  progressBar.style.width = pct + '%';
}
function showError(msg) {
  hideAll();
  errorPanel.classList.remove('hidden');
  errorMsg.textContent = 'Error: ' + msg;
}
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
