/* VERITAS v3.4.2 — Frontend App Logic */

const API = '/api/v1';

// ── Step definitions ─────────────────────────────────────────────────────────
const STEP_NAMES = {
  '0': ['🏷️', 'Experiment Classification'],
  '1': ['🎯', 'Claim Integrity', '40%'],
  '2': ['🔗', 'Traceability Audit', '30%'],
  '3': ['🔄', 'Series Continuity', '20%'],
  '4': ['📰', 'Publication Readiness', '10%'],
  '5': ['⚡', 'Priority Fix Synthesis'],
};

const FILE_ICONS = { pdf:'📕', docx:'📘', doc:'📘', txt:'📄', md:'📝' };

const PROGRESS_STEPS = [
  { key:'precheck', label:'🚦 PRECHECK', pct:15 },
  { key:'classify', label:'🏷️ CLASSIFY', pct:30 },
  { key:'pipeline', label:'⚙️ PIPELINE', pct:65 },
  { key:'enrich',   label:'🧬 ENRICH',   pct:82 },
  { key:'render',   label:'📄 RENDER',   pct:97 },
];

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const dropZone      = $('dropZone');
const fileInput     = $('fileInput');
const fileInfo      = $('fileInfo');
const fileNameEl    = $('fileName');
const fileSizeEl    = $('fileSize');
const fileTypeIcon  = $('fileTypeIcon');
const clearFileBtn  = $('clearFile');
const submitBtn     = $('submitBtn');
const templateSel   = $('templateSelect');
const roundInput    = $('roundInput');
const outputFormat  = $('outputFormat');
const uploadPanel   = $('uploadPanel');
const progressPanel = $('progressPanel');
const resultPanel   = $('resultPanel');
const errorPanel    = $('errorPanel');
const progressLabel = $('progressLabel');
const progressBar   = $('progressBar');
const progressPct   = $('progressPct');
const spinnerEmoji  = $('spinnerEmoji');
const omegaValue    = $('omegaValue');
const omegaBar      = $('omegaBar');
const omegaVerdict  = $('omegaVerdict');
const metaChips     = $('metaChips');
const precheckRow   = $('precheckRow');
const downloadGroup = $('downloadGroup');
const scoreGrid     = $('scoreGrid');
const stepsContainer = $('stepsContainer');
const priorityBox   = $('priorityBox');
const errorMsg      = $('errorMsg');

let selectedFile = null;
let lastReport   = null;
let lastMd       = '';

// ── File selection ────────────────────────────────────────────────────────────
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', e => { if (!dropZone.contains(e.relatedTarget)) dropZone.classList.remove('drag-over'); });
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});
fileInput.addEventListener('change', () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });
clearFileBtn.addEventListener('click', clearSelection);

function setFile(f) {
  selectedFile = f;
  const ext = f.name.split('.').pop().toLowerCase();
  fileTypeIcon.textContent = FILE_ICONS[ext] || '📄';
  fileNameEl.textContent = f.name;
  fileSizeEl.textContent = formatBytes(f.size);
  fileInfo.classList.remove('hidden');
  dropZone.classList.add('hidden');
  submitBtn.disabled = false;

  // Warn: binary files can't be forwarded to rebuttal/journal/review-sim tabs
  const binaryExts = ['pdf', 'docx', 'doc'];
  const binaryWarning = document.getElementById('binaryFileWarning');
  if (binaryWarning) {
    binaryWarning.classList.toggle('hidden', !binaryExts.includes(ext));
  }
}

function clearSelection() {
  selectedFile = null;
  fileInput.value = '';
  fileInfo.classList.add('hidden');
  dropZone.classList.remove('hidden');
  submitBtn.disabled = true;
}

function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB';
  return (b / (1024 * 1024)).toFixed(2) + ' MB';
}

// ── Submit ────────────────────────────────────────────────────────────────────
submitBtn.addEventListener('click', async () => {
  if (!selectedFile) return;
  const format   = outputFormat.value;
  const template = templateSel.value;
  const round    = parseInt(roundInput.value) || 1;
  const domain   = $('domainSelect') ? $('domainSelect').value : 'biomedical';

  showProgress(0);

  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('template', template);
  fd.append('round_number', round);
  fd.append('domain', domain);

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
  // Capture plain-text files for rebuttal/journal/review-sim tab APIs
  try {
    const file = fd.get('file');
    if (file && (file.type === 'text/plain' || file.name.endsWith('.md'))) {
      const txt = await file.text();
      if (!lastReport) lastReport = {};
      lastReport._source_text = txt;
    }
  } catch { /* binary files (PDF/DOCX) — skip */ }

  await animateProgress(0, 2);  // precheck + classify
  const res = await fetch(`${API}/critique/upload`, { method: 'POST', body: fd });
  await animateProgress(2, 3);  // pipeline
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  const report = await res.json();
  lastReport = { ...report, _source_text: lastReport?._source_text };
  lastMd = buildMarkdown(report);
  await animateProgress(3, 4);  // enrich
  await animateProgress(4, 5);  // render
  await sleep(200);
  renderReportFull(report);
}

async function runDownload(fd, format) {
  await animateProgress(0, 3);
  const res = await fetch(`${API}/critique/download`, { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Server error ${res.status}`);
  }
  setProgressRaw(100, '✅ Download ready!');
  const blob = await res.blob();
  triggerDownload(blob, `veritas_critique.${format}`);
  await sleep(600);
  showUpload();
}

function triggerDownload(blob, name) {
  const url = URL.createObjectURL(blob);
  const a   = Object.assign(document.createElement('a'), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

// ── Progress animation ────────────────────────────────────────────────────────
const SPINNER_EMOJIS = ['🔬','🧬','⚗️','🔭','📊','🧪'];
let spinIdx = 0;
let spinInterval;

function showProgress(stepIdx) {
  hideAll();
  progressPanel.classList.remove('hidden');
  spinInterval = setInterval(() => {
    spinnerEmoji.textContent = SPINNER_EMOJIS[spinIdx++ % SPINNER_EMOJIS.length];
  }, 600);
  updateProgressSteps(stepIdx);
}

function setProgressRaw(pct, label) {
  progressBar.style.width = pct + '%';
  progressPct.textContent = Math.round(pct) + '%';
  if (label) progressLabel.textContent = label;
}

async function animateProgress(fromStep, toStep) {
  const from = PROGRESS_STEPS[fromStep] || { pct: 0 };
  const to   = PROGRESS_STEPS[Math.min(toStep, PROGRESS_STEPS.length - 1)];
  updateProgressSteps(toStep);
  progressLabel.textContent = to.label + '...';
  const start = from.pct, end = to.pct;
  const dur = 400;
  const t0 = performance.now();
  await new Promise(resolve => {
    function tick(t) {
      const p = Math.min((t - t0) / dur, 1);
      setProgressRaw(start + (end - start) * easeOut(p), null);
      if (p < 1) requestAnimationFrame(tick); else resolve();
    }
    requestAnimationFrame(tick);
  });
}

function updateProgressSteps(activeIdx) {
  document.querySelectorAll('.pstep').forEach((el, i) => {
    el.classList.remove('active', 'done');
    if (i < activeIdx) el.classList.add('done');
    else if (i === activeIdx) el.classList.add('active');
  });
}

function easeOut(t) { return 1 - Math.pow(1 - t, 2); }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Render report ─────────────────────────────────────────────────────────────
function renderReportFull(r) {
  clearInterval(spinInterval);
  hideAll();
  resultPanel.classList.remove('hidden');

  // Omega score
  const omega = r.omega_score || 0;
  omegaValue.textContent = omega.toFixed(4);
  omegaBar.style.width = (omega * 100).toFixed(1) + '%';
  if (omega >= 0.80) {
    omegaValue.className = 'omega-value high';
    omegaBar.style.background = 'linear-gradient(90deg,#22c55e,#16a34a)';
    omegaVerdict.textContent = '✅ Publication-Ready';
    omegaVerdict.className = 'omega-verdict verdict-ready';
  } else if (omega >= 0.60) {
    omegaValue.className = 'omega-value medium';
    omegaBar.style.background = 'linear-gradient(90deg,#f59e0b,#d97706)';
    omegaVerdict.textContent = '⚠️ Needs Revision';
    omegaVerdict.className = 'omega-verdict verdict-review';
  } else {
    omegaValue.className = 'omega-value low';
    omegaBar.style.background = 'linear-gradient(90deg,#ef4444,#b91c1c)';
    omegaVerdict.textContent = '❌ Major Issues';
    omegaVerdict.className = 'omega-verdict verdict-major';
  }

  // Meta chips
  metaChips.innerHTML = [
    ['🏷️ Experiment Type', r.experiment_class || '—'],
    ['🔄 Round', `#${r.round_number}`],
    ['❌ Not Traceable', r.not_traceable_count],
    ['🔶 Partial', r.partially_traceable_count],
  ].map(([l, v]) => `
    <div class="meta-chip">
      <span class="meta-chip-label">${l}</span>
      <span class="meta-chip-value">${escHtml(String(v))}</span>
    </div>
  `).join('');

  // Precheck badge
  const mode = r.precheck?.mode || 'FULL';
  const modeEmoji = { FULL:'🟢', PARTIAL:'🟡', LIMITED:'🟠', BLOCKED:'🔴' }[mode] || '🔵';
  const badgeClass = { FULL:'badge-full', PARTIAL:'badge-partial', LIMITED:'badge-limited', BLOCKED:'badge-blocked' }[mode] || 'badge-partial';
  const missing = r.precheck?.missing_artifacts?.length
    ? ` — ⚠️ Missing: ${r.precheck.missing_artifacts.join(', ')}`
    : '';
  precheckRow.innerHTML = `<span class="precheck-badge ${badgeClass}">${modeEmoji} ${r.precheck?.line1 || mode}${missing}</span>`;

  // Download buttons
  downloadGroup.innerHTML = [
    ['📝 MD', 'md'], ['📘 DOCX', 'docx'], ['📕 PDF', 'pdf'], ['🔤 TEX', 'tex']
  ].map(([label, fmt]) =>
    `<button class="btn-download" data-format="${fmt}">${label}</button>`
  ).join('');
  downloadGroup.querySelectorAll('.btn-download').forEach(btn =>
    btn.addEventListener('click', () => reDownload(btn.dataset.format))
  );

  // Score mini-cards
  scoreGrid.innerHTML = '';
  if (r.irf_scores) scoreGrid.appendChild(buildScoreCard('⚡ LOGOS IRF-Calc 6D', r.irf_scores,
    ['M','A','D','I','F','P'], r.irf_scores.composite, 0.78));
  if (r.hsta_scores) scoreGrid.appendChild(buildScoreCard('📊 HSTA 4D Bibliometric', r.hsta_scores,
    ['N','C','T','R'], r.hsta_scores.composite, 0.60));
  if (r.bibliography_stats) {
    const b = r.bibliography_stats;
    const bCard = document.createElement('div');
    bCard.className = 'score-card';
    bCard.innerHTML = `
      <div class="score-card-title">📚 Bibliography</div>
      <div class="score-dims">
        <span class="dim-chip">${b.total_refs} refs</span>
        <span class="dim-chip">${b.oldest_year || '?'}–${b.newest_year || '?'}</span>
        <span class="dim-chip ${b.self_citation_detected ? 'fail' : 'pass'}">${b.self_citation_detected ? '⚠️ Self-cite' : '✅ No self-cite'}</span>
        ${b.quality_score != null ? `<span class="dim-chip ${b.quality_score >= 0.7 ? 'pass' : 'fail'}">Q: ${b.quality_score.toFixed(2)}</span>` : ''}
      </div>`;
    scoreGrid.appendChild(bCard);
  }
  if (r.reproducibility_checklist) {
    const rc = r.reproducibility_checklist;
    const sat = Object.values(rc.items || {}).filter(v => v === true).length;
    const tot = Object.keys(rc.items || {}).length;
    const rcCard = document.createElement('div');
    rcCard.className = 'score-card';
    rcCard.innerHTML = `
      <div class="score-card-title">✅ Reproducibility (${sat}/${tot})</div>
      <div class="score-dims">
        ${Object.entries(rc.items || {}).map(([k, v]) =>
          `<span class="dim-chip ${v === true ? 'pass' : v === false ? 'fail' : ''}">${k}</span>`
        ).join('')}
      </div>`;
    scoreGrid.appendChild(rcCard);
  }

  // Step accordion
  stepsContainer.innerHTML = '';
  r.steps.forEach((step, idx) => {
    const [emoji, name, weight] = STEP_NAMES[step.step_id] || ['📌', `Step ${step.step_id}`];
    const isFirst = idx === 0;
    const card = document.createElement('div');
    card.className = `step-card${isFirst ? ' open' : ''}`;
    card.innerHTML = `
      <div class="step-header">
        <div class="step-left">
          <span class="step-num">STEP ${step.step_id}</span>
          <span class="step-title">${emoji} ${name}</span>
        </div>
        <div class="step-right">
          ${weight ? `<span class="step-weight">${weight}</span>` : ''}
          <span class="step-chevron">›</span>
        </div>
      </div>
      <div class="step-body${isFirst ? '' : ' hidden'}">
        <p class="step-prose">${escHtml(step.prose)}</p>
        ${step.findings.length ? `
          <ul class="findings-list">
            ${step.findings.map(f => `
              <li class="finding-item tc-${f.traceability.replace(/ /g,'-')}">
                <span class="finding-code">[${f.code}]</span>
                ${escHtml(f.description)}
                ${f.verbatim_quote ? `<div class="finding-quote">"${escHtml(f.verbatim_quote)}"</div>` : ''}
              </li>
            `).join('')}
          </ul>
        ` : ''}
      </div>
    `;
    card.querySelector('.step-header').addEventListener('click', () => {
      const body = card.querySelector('.step-body');
      const open = !body.classList.contains('hidden');
      body.classList.toggle('hidden', open);
      card.classList.toggle('open', !open);
    });
    stepsContainer.appendChild(card);
  });

  // Priority fix
  priorityBox.innerHTML = `
    <div class="priority-label">⚡ PRIORITY FIX</div>
    <div>${escHtml(r.priority_fix)}</div>
    ${r.next_liability ? `<div class="next-liability">🔶 Next Liability: ${escHtml(r.next_liability)}</div>` : ''}
  `;
}

function buildScoreCard(title, scores, dims, composite, threshold) {
  const card = document.createElement('div');
  card.className = 'score-card';
  card.innerHTML = `
    <div class="score-card-title">${title} — ${composite >= threshold ? '✅' : '⚠️'} ${composite.toFixed(3)}</div>
    <div class="score-dims">
      ${dims.map(d => {
        const v = scores[d];
        return v != null
          ? `<span class="dim-chip ${v >= threshold ? 'pass' : 'fail'}">${d}: ${v.toFixed(2)}</span>`
          : '';
      }).join('')}
    </div>`;
  return card;
}

// ── Re-download ───────────────────────────────────────────────────────────────
async function reDownload(format) {
  if (!selectedFile) return;
  if (format === 'md') {
    const blob = new Blob([lastMd], { type: 'text/markdown' });
    triggerDownload(blob, 'veritas_critique.md');
    return;
  }
  const domain = $('domainSelect') ? $('domainSelect').value : 'biomedical';
  const fd = new FormData();
  fd.append('file', selectedFile);
  fd.append('template', templateSel.value);
  fd.append('round_number', parseInt(roundInput.value) || 1);
  fd.append('format', format);
  fd.append('domain', domain);
  try {
    const res = await fetch(`${API}/critique/download`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const blob = await res.blob();
    triggerDownload(blob, `veritas_critique.${format}`);
  } catch (e) {
    alert('⚠️ Download failed: ' + e.message);
  }
}

function buildMarkdown(r) {
  let md = `# VERITAS Critique Report\n\n`;
  md += `**Omega Score:** ${r.omega_score?.toFixed(4)}\n`;
  md += `**Experiment Class:** ${r.experiment_class || '—'}\n`;
  md += `**Round:** ${r.round_number}\n\n`;
  md += `## PRECHECK\n${r.precheck?.line1 || ''}\n\n`;
  r.steps.forEach(s => {
    md += `## STEP ${s.step_id}\n${s.prose}\n\n`;
    s.findings.forEach(f => { md += `- [${f.code}] ${f.description}\n`; });
    md += '\n';
  });
  md += `## Priority Fix\n${r.priority_fix}\n`;
  return md;
}

// ── Clipboard ─────────────────────────────────────────────────────────────────
$('copyMdBtn').addEventListener('click', async () => {
  if (!lastMd) return;
  try {
    await navigator.clipboard.writeText(lastMd);
    const btn = $('copyMdBtn');
    const orig = btn.textContent;
    btn.textContent = '✅ Copied!';
    setTimeout(() => { btn.textContent = orig; }, 1800);
  } catch { alert('Copy failed — use the MD download instead.'); }
});

// ── UI helpers ────────────────────────────────────────────────────────────────
$('newAnalysisBtn').addEventListener('click', showUpload);
$('errorRetryBtn').addEventListener('click', showUpload);

function showUpload() {
  clearInterval(spinInterval);
  hideAll();
  uploadPanel.classList.remove('hidden');
  clearSelection();
}
function hideAll() {
  [uploadPanel, progressPanel, resultPanel, errorPanel].forEach(p => p.classList.add('hidden'));
}
function showError(msg) {
  clearInterval(spinInterval);
  hideAll();
  errorPanel.classList.remove('hidden');
  errorMsg.textContent = msg;
}
function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Tab switching ──────────────────────────────────────────────────────────────
document.querySelectorAll('.rtab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.rtab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.rtab-pane').forEach(p => p.classList.add('hidden'));
    btn.classList.add('active');
    const pane = document.getElementById('rtab-' + btn.dataset.tab);
    if (pane) pane.classList.remove('hidden');
  });
});

// ── Domain selector ───────────────────────────────────────────────────────────
const domainSelect = $('domainSelect');

// Populate domain selector from API on page load
(async () => {
  try {
    const res = await fetch(`${API}/domains`);
    if (!res.ok) return;
    const domains = await res.json();
    if (!domains.length) return;
    domainSelect.innerHTML = domains
      .map(d => `<option value="${d.key}"${d.key === 'biomedical' ? ' selected' : ''}>${d.name}</option>`)
      .join('');
  } catch { /* keep static fallback options */ }
})();

// ── Rebuttal tab ──────────────────────────────────────────────────────────────
const rebuttalRunBtn    = $('rebuttalRunBtn');
const rebuttalSummary   = $('rebuttalSummary');
const rebuttalItems     = $('rebuttalItems');
const rebuttalActions   = $('rebuttalActions');
const downloadLetterBtn = $('downloadLetterBtn');
let lastRebuttalReport  = null;

rebuttalRunBtn.addEventListener('click', async () => {
  if (!lastReport) { alert('Run a critique first.'); return; }
  const style  = $('rebuttalStyle').value;
  const domain = domainSelect ? domainSelect.value : 'biomedical';

  rebuttalRunBtn.disabled = true;
  rebuttalRunBtn.textContent = 'Generating...';

  try {
    const res = await fetch(`${API}/rebuttal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        report_text: lastReport._source_text || '',
        style,
        domain,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }
    lastRebuttalReport = await res.json();
    renderRebuttal(lastRebuttalReport, style);
  } catch (e) {
    alert('Rebuttal error: ' + e.message);
  } finally {
    rebuttalRunBtn.disabled = false;
    rebuttalRunBtn.textContent = 'Generate Rebuttal';
  }
});

function renderRebuttal(rb, style) {
  const severity_color = { CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#f59e0b', LOW: '#6b7280' };
  rebuttalSummary.innerHTML = `
    <div class="rebuttal-meta">
      <span class="rebuttal-chip">Total: ${rb.total_issues} issues</span>
      <span class="rebuttal-chip" style="color:${severity_color.CRITICAL}">${rb.critical_count} CRITICAL</span>
      <span class="rebuttal-chip" style="color:${severity_color.HIGH}">${rb.high_count} HIGH</span>
      <span class="rebuttal-chip">Style: ${rb.style.toUpperCase()}</span>
      <span class="rebuttal-chip">Coverage: ${(rb.rebuttal_coverage * 100).toFixed(0)}%</span>
    </div>`;
  rebuttalSummary.classList.remove('hidden');

  rebuttalItems.innerHTML = rb.items.map(item => `
    <div class="rebuttal-item severity-${item.severity.toLowerCase()}">
      <div class="ri-header">
        <span class="ri-id">${escHtml(item.issue_id)}</span>
        <span class="ri-severity" style="color:${severity_color[item.severity] || '#888'}">${item.severity}</span>
        <span class="ri-cat">${escHtml(item.category)}</span>
        ${item.addressed ? '<span class="ri-addressed">Addressed</span>' : ''}
      </div>
      <div class="ri-reviewer"><strong>Reviewer:</strong> ${escHtml(item.reviewer_text)}</div>
      <details class="ri-response">
        <summary>Author Response Template</summary>
        <pre>${escHtml(item.author_response_template)}</pre>
      </details>
    </div>`).join('');

  rebuttalActions.classList.remove('hidden');
}

downloadLetterBtn.addEventListener('click', async () => {
  if (!lastReport) return;
  const style  = $('rebuttalStyle').value;

  downloadLetterBtn.disabled = true;
  downloadLetterBtn.textContent = 'Rendering...';
  try {
    const res = await fetch(`${API}/response-letter`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_text: lastReport._source_text || '', style }),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();
    const blob = new Blob([data.markdown], { type: 'text/markdown' });
    triggerDownload(blob, `response_letter_${style}.md`);
  } catch (e) {
    alert('Letter render error: ' + e.message);
  } finally {
    downloadLetterBtn.disabled = false;
    downloadLetterBtn.textContent = 'Download Response Letter';
  }
});

// ── Journal tab ───────────────────────────────────────────────────────────────
const journalRunBtn  = $('journalRunBtn');
const journalResult  = $('journalResult');

journalRunBtn.addEventListener('click', async () => {
  if (!lastReport) { alert('Run a critique first.'); return; }
  const journal = $('journalSelect').value;
  const domain  = domainSelect ? domainSelect.value : 'biomedical';

  journalRunBtn.disabled = true;
  journalRunBtn.textContent = 'Scoring...';

  try {
    const res = await fetch(`${API}/journal-score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_text: lastReport._source_text || '', journal, domain }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }
    const data = await res.json();
    renderJournalScore(data);
  } catch (e) {
    alert('Journal score error: ' + e.message);
  } finally {
    journalRunBtn.disabled = false;
    journalRunBtn.textContent = 'Score Against Journal';
  }
});

function renderJournalScore(js) {
  const verdictColor = { ACCEPT: '#22c55e', REVISE: '#f59e0b', REJECT: '#ef4444' };
  const color = verdictColor[js.verdict] || '#888';
  journalResult.innerHTML = `
    <div class="js-hero" style="border-left:4px solid ${color}">
      <div class="js-verdict" style="color:${color}">${js.verdict}</div>
      <div class="js-journal">${escHtml(js.journal_name)}</div>
      <div class="js-omegas">
        <span>Raw Omega: <strong>${js.raw_omega.toFixed(4)}</strong></span>
        <span>Calibrated Omega: <strong>${js.calibrated_omega.toFixed(4)}</strong></span>
        <span>Delta Omega: <strong>${js.omega_delta >= 0 ? '+' : ''}${js.omega_delta.toFixed(4)}</strong></span>
      </div>
      <div class="js-thresholds">
        Accept >= ${js.accept_threshold.toFixed(2)} | Revise >= ${js.revise_threshold.toFixed(2)}
      </div>
    </div>
    <div class="js-steps">
      ${Object.entries(js.step_contributions).map(([sid, sc]) => `
        <div class="js-step-row">
          <span class="js-step-id">STEP ${sid}</span>
          <span class="js-step-vals">raw ${sc.raw.toFixed(3)} x ${sc.multiplier.toFixed(2)} = <strong>${sc.weighted.toFixed(3)}</strong></span>
        </div>`).join('')}
    </div>`;
  journalResult.classList.remove('hidden');
}

// ── Peer Review Simulation tab ────────────────────────────────────────────────
const reviewSimRunBtn  = $('reviewSimRunBtn');
const reviewSimResult  = $('reviewSimResult');

reviewSimRunBtn.addEventListener('click', async () => {
  if (!lastReport) { alert('Run a critique first.'); return; }
  const reviewers = parseInt($('reviewerCount').value) || 3;

  reviewSimRunBtn.disabled = true;
  reviewSimRunBtn.textContent = 'Simulating...';

  try {
    const res = await fetch(`${API}/review-sim`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_text: lastReport._source_text || '', reviewers }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error ${res.status}`);
    }
    const data = await res.json();
    renderReviewSim(data);
  } catch (e) {
    alert('Review sim error: ' + e.message);
  } finally {
    reviewSimRunBtn.disabled = false;
    reviewSimRunBtn.textContent = 'Run Peer Review Simulation';
  }
});

function renderReviewSim(rs) {
  const recColor = { ACCEPT: '#22c55e', REVISE: '#f59e0b', REJECT: '#ef4444' };
  const finalColor = recColor[rs.final_recommendation] || '#888';

  const reviewerRows = rs.per_reviewer.map(r => `
    <div class="rs-reviewer">
      <span class="rs-persona">${r.persona}</span>
      <span class="rs-omega">Omega ${r.calibrated_omega.toFixed(4)}</span>
      <span class="rs-rec" style="color:${recColor[r.recommendation] || '#888'}">${r.recommendation}</span>
    </div>`).join('');

  reviewSimResult.innerHTML = `
    <div class="rs-final" style="border-left:4px solid ${finalColor}">
      <span class="rs-verdict" style="color:${finalColor}">${rs.final_recommendation}</span>
      <span class="rs-omega-final">Final Omega: <strong>${rs.final_omega.toFixed(4)}</strong></span>
      <span class="rs-consensus ${rs.consensus.reached ? 'reached' : 'no-consensus'}">
        ${rs.consensus.reached ? 'Consensus' : 'No consensus'} - spread ${rs.consensus.spread.toFixed(3)}
      </span>
    </div>
    <div class="rs-reviewers">${reviewerRows}</div>
    ${rs.dr3.conflict_detected ? `
    <div class="rs-dr3">
      <strong>DR3 Resolution:</strong> ${escHtml(rs.dr3.resolution_note)}
      (tiebreaker: ${rs.dr3.tiebreaker_persona})
    </div>` : ''}`;
  reviewSimResult.classList.remove('hidden');
}

// ── Hybrid omega display ──────────────────────────────────────────────────────
function maybeRenderHybridOmega(r) {
  if (!r.hybrid_omega && !r.logos_omega) return;
  const chip = document.createElement('div');
  chip.className = 'score-card';
  chip.innerHTML = `
    <div class="score-card-title">Hybrid Omega</div>
    <div class="score-dims">
      ${r.logos_omega != null ? `<span class="dim-chip">LOGOS: ${r.logos_omega.toFixed(4)}</span>` : ''}
      ${r.hybrid_omega != null ? `<span class="dim-chip pass">Hybrid: ${r.hybrid_omega.toFixed(4)}</span>` : ''}
    </div>`;
  scoreGrid.appendChild(chip);
}

// ── renderReport wrapper ──────────────────────────────────────────────────────
function renderReport(r) {
  if (!r._source_text && lastReport && lastReport._source_text) {
    r._source_text = lastReport._source_text;
  }
  renderReportFull(r);
  maybeRenderHybridOmega(r);
}
