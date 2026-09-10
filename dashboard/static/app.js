// Keep standalone and authenticated OCC iframe requests on their own API paths.
const insightBase = /^\/insight-agent(?:\/|$)/.test(location.pathname) ? '/insight-agent' : '';
const directFetch = window.fetch.bind(window);
window.fetch = async (input, init = {}) => {
  if (insightBase && typeof input === 'string' && input.startsWith('/api/')) {
    const headers = new Headers(init.headers);
    if (!['GET', 'HEAD', 'OPTIONS'].includes((init.method || 'GET').toUpperCase())) {
      const auth = await directFetch('/api/auth/status').then(r => r.json());
      if (auth.csrfToken) headers.set('X-Command-Center-CSRF', auth.csrfToken);
    }
    return directFetch(insightBase + input, { ...init, headers });
  }
  return directFetch(input, init);
};
let currentJobId = null;
let pollTimer = null;
let allReports = [];
let currentViewerFile = null;

// API text can contain scanned-page content or user-controlled filenames.
// Escape both text and quoted data attributes before using an HTML template.
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[c]);
}

function statusClass(value) {
  return ['queued', 'running', 'done', 'error', 'stopped'].includes(value) ? value : 'queued';
}

// Navigation
function nav(el, page) {
  if (!['overview', 'scan', 'bulk', 'monitor', 'jobs', 'reports', 'skills', 'settings', 'help'].includes(page)) return;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  el.classList.add('active');
  const actions = {
    overview: loadOverview,
    reports: loadReports,
    jobs: loadJobs,
    skills: loadSkillStatus,
    settings: loadSettings,
    monitor: loadMonitors,
    bulk: () => updateBulkCount(),
  };
  if (actions[page]) return actions[page]();
}

function toast(msg, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show ' + type;
  setTimeout(() => t.className = 'toast', 3000);
}

// Status & API dots
async function loadStatus() {
  try {
    const d = await fetch('/api/status').then(r => r.json());
    document.getElementById('stat-reports').textContent = d.reports_count;
    document.getElementById('stat-jobs').textContent = d.active_jobs;
    document.getElementById('stat-monitors').textContent = d.monitors_active || 0;
    document.getElementById('stat-skill').textContent = d.has_optimized_skill ? 'Optimized ✓' : 'Seed';

    // API dots
    ['nim','groq','gemini'].forEach(k => {
      const dot = document.getElementById('dot-' + k);
      dot.className = 'dot ' + (d['api_' + k] ? 'on' : 'off');
    });

    // Badges
    const jb = document.getElementById('jobs-badge');
    if (d.active_jobs > 0) { jb.textContent = d.active_jobs; jb.style.display = ''; }
    else { jb.style.display = 'none'; }

    const mb = document.getElementById('monitor-badge');
    if ((d.monitors_active || 0) > 0) { mb.textContent = d.monitors_active; mb.style.display = ''; }
    else { mb.style.display = 'none'; }
  } catch {}
}

// Overview
async function loadOverview() {
  await loadStatus();
  allReports = await fetch('/api/reports').then(r => r.json());
  const el = document.getElementById('recent-list');
  if (!allReports.length) { el.innerHTML = '<div class="empty" style="padding:16px">No reports yet. Run your first scan!</div>'; return; }
  el.innerHTML = allReports.slice(0, 4).map(r => `
    <div style="padding:8px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
      <div>
        <div style="font-size:13px;font-weight:600">${escapeHtml(r.domain)}</div>
        <div style="font-size:11px;color:var(--muted)">${escapeHtml(r.created)}</div>
      </div>
      <div class="flex" style="gap:6px">
        ${r.score != null ? scoreBadge(r.score) : ''}
        <button class="btn btn-outline btn-sm" data-action="open-report" data-filename="${escapeHtml(r.filename)}">View</button>
      </div>
    </div>
  `).join('');
  drawSparkline(allReports.slice(0, 10).reverse().filter(r => r.score != null));
}

function scoreBadge(score) {
  const cls = score >= 75 ? 'score-a' : score >= 50 ? 'score-b' : 'score-c';
  return `<span class="score-badge ${cls}">${escapeHtml(score)}</span>`;
}

function drawSparkline(data) {
  data = data.filter(r => Number.isFinite(Number(r.score)));
  if (data.length < 2) return;
  document.getElementById('score-chart-wrap').style.display = 'block';
  const svg = document.getElementById('sparkline');
  const scores = data.map(r => Math.max(0, Math.min(100, Number(r.score))));
  const min = Math.min(...scores) - 5;
  const max = Math.max(...scores) + 5;
  const W = 400, H = 50;
  const pts = scores.map((s, i) => {
    const x = (i / (scores.length - 1)) * W;
    const y = H - ((s - min) / (max - min)) * H;
    return `${x},${y}`;
  }).join(' ');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = `
    <polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>
    ${scores.map((s, i) => {
      const x = (i / (scores.length - 1)) * W;
      const y = H - ((s - min) / (max - min)) * H;
      return `<circle cx="${x}" cy="${y}" r="3" fill="var(--accent2)"/><title>${escapeHtml(data[i].domain)}: ${s}/100</title>`;
    }).join('')}
  `;
}

// Quick scan
function quickScan() {
  const t = document.getElementById('quick-target').value.trim();
  if (!t) { toast('Enter a target domain', 'error'); return; }
  document.getElementById('scan-target').value = t;
  document.getElementById('scan-nopdf').checked = document.getElementById('quick-nopdf').checked;
  document.querySelector('[data-page="scan"]').click();
  setTimeout(startScan, 80);
}

// Single scan
async function startScan() {
  const target = document.getElementById('scan-target').value.trim();
  if (!target) { toast('Enter a target domain', 'error'); return; }
  const btn = document.getElementById('scan-btn');
  btn.disabled = true; btn.textContent = 'Scanning…';
  const payload = {
    target,
    report_type: document.getElementById('scan-type').value,
    keywords: document.getElementById('scan-keywords').value,
    no_pdf: document.getElementById('scan-nopdf').checked,
  };
  const d = await fetch('/api/scan', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }).then(r => r.json());
  currentJobId = d.job_id;
  document.getElementById('scan-result-area').style.display = 'block';
  document.getElementById('scan-job-target').textContent = target;
  document.getElementById('scan-output').style.display = 'none';
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => pollJob(currentJobId, 'scan'), 1500);
}

async function pollJob(jobId, context) {
  const job = await fetch('/api/job/' + encodeURIComponent(jobId)).then(r => r.json());
  if (context === 'scan') {
    document.getElementById('scan-job-badge').textContent = job.status.toUpperCase();
    document.getElementById('scan-job-badge').className = 'badge ' + job.status;
    const bar = document.getElementById('scan-progress-bar');
    if (job.status === 'running') bar.style.width = '60%';
    else if (job.status === 'done') bar.style.width = '100%';
    else if (job.status === 'error') { bar.style.width = '100%'; bar.style.background = 'var(--red)'; }
    document.getElementById('scan-job-meta').textContent = `${job.progress} · ${job.started_at}${job.finished_at ? ' → ' + job.finished_at : ''}`;
    if (job.output) {
      const out = document.getElementById('scan-output');
      out.style.display = 'block';
      out.textContent = job.output.slice(-2000);
      out.scrollTop = out.scrollHeight;
    }
    if (job.status === 'done' || job.status === 'error') {
      clearInterval(pollTimer);
      document.getElementById('scan-btn').disabled = false;
      document.getElementById('scan-btn').textContent = 'Launch Scan';
      toast(job.status === 'done' ? (job.score ? `Done — SEO Score: ${job.score}/100` : 'Scan complete!') : 'Scan failed', job.status === 'done' ? 'success' : 'error');
      loadStatus();
    }
  }
  return job;
}

// Bulk scan
function updateBulkCount() {
  const lines = document.getElementById('bulk-targets')?.value.split('\n').filter(l => l.trim()).length || 0;
  const lbl = document.getElementById('bulk-count-label');
  if (lbl) lbl.textContent = lines > 0 ? `${Math.min(lines, 10)} domain(s) queued` : '';
}

async function startBulk() {
  const targets = document.getElementById('bulk-targets').value;
  if (!targets.trim()) { toast('Enter at least one domain', 'error'); return; }
  const btn = document.getElementById('bulk-btn');
  btn.disabled = true; btn.textContent = 'Launching…';
  const payload = {
    targets,
    report_type: document.getElementById('bulk-type').value,
    keywords: document.getElementById('bulk-keywords').value,
  };
  const d = await fetch('/api/scan/batch', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }).then(r => r.json());
  if (d.error) { toast(d.error, 'error'); btn.disabled = false; btn.textContent = 'Launch Bulk Scan'; return; }
  toast(`${d.count} scans started!`, 'info');
  btn.disabled = false; btn.textContent = 'Launch Bulk Scan';
  // Render job cards
  const grid = document.getElementById('bulk-results');
  grid.innerHTML = d.job_ids.map(jid => `
    <div class="job-card" id="bulk-job-${escapeHtml(jid)}">
      <div class="job-header">
        <span class="job-target" id="bulk-t-${escapeHtml(jid)}">Loading…</span>
        <span class="badge queued" id="bulk-b-${escapeHtml(jid)}">QUEUED</span>
      </div>
      <div class="progress-bar"><div class="progress-fill" id="bulk-p-${escapeHtml(jid)}" style="width:5%"></div></div>
      <div class="job-meta" id="bulk-m-${escapeHtml(jid)}">Waiting…</div>
    </div>
  `).join('');
  // Poll all
  d.job_ids.forEach(jid => pollBulkJob(jid));
}

async function pollBulkJob(jid) {
  const poll = setInterval(async () => {
    const job = await fetch('/api/job/' + encodeURIComponent(jid)).then(r => r.json());
    const t = document.getElementById('bulk-t-' + jid);
    const b = document.getElementById('bulk-b-' + jid);
    const p = document.getElementById('bulk-p-' + jid);
    const m = document.getElementById('bulk-m-' + jid);
    if (!t) { clearInterval(poll); return; }
    if (t) t.textContent = job.target;
    if (b) { b.textContent = job.status.toUpperCase(); b.className = 'badge ' + job.status; }
    if (p) p.style.width = job.status === 'done' ? '100%' : job.status === 'running' ? '60%' : '10%';
    if (m) m.textContent = job.progress + (job.score ? ` · SEO Score: ${job.score}/100` : '');
    if (job.status === 'done' || job.status === 'error') {
      clearInterval(poll);
      loadStatus();
    }
  }, 2000);
}

// Monitor
async function startMonitor() {
  const target = document.getElementById('mon-target').value.trim();
  if (!target) { toast('Enter a target domain', 'error'); return; }
  const interval = parseInt(document.getElementById('mon-interval').value);
  const d = await fetch('/api/monitor/start', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ target, interval }) }).then(r => r.json());
  if (d.status === 'started') { toast(`Monitor started: ${target}`, 'success'); loadMonitors(); loadStatus(); }
  else toast(d.error || 'Failed', 'error');
}

async function stopMonitor(target) {
  await fetch('/api/monitor/stop', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ target }) });
  toast(`Monitor stopped: ${target}`);
  loadMonitors(); loadStatus();
}

async function loadMonitors() {
  const monitors = await fetch('/api/monitor/list').then(r => r.json());
  const el = document.getElementById('monitor-list');
  if (!monitors.length) { el.innerHTML = '<div class="empty">No monitors running</div>'; return; }
  el.innerHTML = monitors.map(m => `
    <div class="monitor-card">
      <div class="monitor-info">
        <div class="monitor-domain">${escapeHtml(m.target)}</div>
        <div class="monitor-meta">
          Interval: ${fmtInterval(m.interval)} · Scans: ${escapeHtml(m.scan_count)}
          ${m.last_scan ? ' · Last: ' + escapeHtml(m.last_scan) : ' · First scan pending'}
        </div>
      </div>
      <div class="flex" style="gap:8px;flex-shrink:0">
        <span class="badge ${statusClass(m.status)}">${escapeHtml(String(m.status).toUpperCase())}</span>
        ${m.status === 'running' ? `<button class="btn btn-red btn-sm" data-action="stop-monitor" data-target="${escapeHtml(m.target)}">Stop</button>` : ''}
      </div>
    </div>
  `).join('');
}

function fmtInterval(s) {
  if (s >= 86400) return (s/86400|0) + 'd';
  if (s >= 3600) return (s/3600|0) + 'h';
  return (s/60|0) + 'm';
}

// Jobs
async function loadJobs() {
  const jobs = await fetch('/api/jobs').then(r => r.json());
  const el = document.getElementById('jobs-list');
  if (!jobs.length) { el.innerHTML = '<div class="empty">No jobs this session</div>'; return; }
  el.innerHTML = jobs.slice().reverse().map(job => `
    <div class="job-card">
      <div class="job-header">
        <span class="job-target">${escapeHtml(job.target)}</span>
        <span class="badge ${statusClass(job.status)}">${escapeHtml(String(job.status).toUpperCase())}</span>
      </div>
      <div class="progress-bar"><div class="progress-fill" style="width:${job.status==='done'?'100':job.status==='running'?'60':job.status==='error'?'100':'10'}%${job.status==='error'?';background:var(--red)':''}"></div></div>
      <div class="job-meta">
        #${escapeHtml(job.id)} · ${escapeHtml(job.started_at)}${job.finished_at ? ' → ' + escapeHtml(job.finished_at) : ''}
        ${job.score != null ? ` · SEO Score: <strong>${escapeHtml(job.score)}/100</strong>` : ''}
      </div>
    </div>
  `).join('');
}

// Reports
async function loadReports() {
  allReports = await fetch('/api/reports').then(r => r.json());
  renderReports(allReports);
}

function renderReports(reports) {
  const tbody = document.getElementById('reports-table-body');
  if (!reports.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty">No reports yet</td></tr>'; return; }
  tbody.innerHTML = reports.map(r => `
    <tr>
      <td style="font-weight:600">${escapeHtml(r.domain)}</td>
      <td>${r.score != null ? scoreBadge(r.score) : '<span style="color:var(--muted)">—</span>'}</td>
      <td>${escapeHtml(r.created)}</td>
      <td>${escapeHtml(r.size_kb)} KB</td>
      <td>
        <div class="flex" style="gap:6px">
          <button class="btn btn-outline btn-sm" data-action="open-report" data-filename="${escapeHtml(r.filename)}">View</button>
          ${r.has_pdf ? `<button class="btn btn-outline btn-sm" data-action="pdf-report" data-filename="${escapeHtml(r.filename)}">PDF</button>` : ''}
        </div>
      </td>
    </tr>
  `).join('');
}

function filterReports() {
  const q = document.getElementById('report-search').value.toLowerCase();
  renderReports(allReports.filter(r => r.domain.toLowerCase().includes(q)));
}

async function openReport(filename) {
  const d = await fetch('/api/report/' + encodeURIComponent(filename)).then(r => r.json());
  currentViewerFile = filename;
  document.getElementById('viewer-title').textContent = filename;
  document.getElementById('report-content').textContent = d.content;
  const viewer = document.getElementById('report-viewer');
  const dlBtn = document.getElementById('viewer-download-btn');
  const rep = allReports.find(r => r.filename === filename);
  dlBtn.style.display = rep?.has_pdf ? '' : 'none';
  viewer.style.display = 'block';
  viewer.scrollIntoView({ behavior: 'smooth' });
}

function closeViewer() {
  document.getElementById('report-viewer').style.display = 'none';
  currentViewerFile = null;
}

function downloadReport() {
  if (currentViewerFile) window.open(insightBase + '/api/report/' + encodeURIComponent(currentViewerFile) + '/download', '_blank');
}

function dlReport(filename) {
  window.open(insightBase + '/api/report/' + encodeURIComponent(filename) + '/download', '_blank');
}

// Skills
async function loadSkillStatus() {
  const d = await fetch('/api/status').then(r => r.json());
  const pill = document.getElementById('seo-skill-pill');
  pill.textContent = d.has_optimized_skill ? 'optimized' : 'seed';
  pill.className = 'pill ' + (d.has_optimized_skill ? 'optimized' : 'seed');
}

// Settings
async function loadSettings() {
  const d = await fetch('/api/settings').then(r => r.json());
  for (const [field, key] of [['key-nim', 'NVIDIA_NIM_API_KEY'], ['key-groq', 'GROQ_API_KEY'], ['key-gemini', 'GEMINI_API_KEY']]) {
    document.getElementById(field).value = '';
    document.getElementById(field).placeholder = d.configured?.[key] ? 'Configured — leave blank to keep' : 'Not configured';
  }
  if (d.DEFAULT_REPORT) document.getElementById('default-report').value = d.DEFAULT_REPORT;
  if (d.SCAN_TIMEOUT) document.getElementById('scan-timeout').value = d.SCAN_TIMEOUT;
}

async function saveSettings() {
  const payload = {
    NVIDIA_NIM_API_KEY: document.getElementById('key-nim').value.trim(),
    GROQ_API_KEY: document.getElementById('key-groq').value.trim(),
    GEMINI_API_KEY: document.getElementById('key-gemini').value.trim(),
  };
  const d = await fetch('/api/settings', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }).then(r => r.json());
  toast(d.message || 'Saved!', d.status === 'ok' ? 'success' : 'error');
  loadStatus();
}

async function saveDefaults() {
  const payload = {
    DEFAULT_REPORT: document.getElementById('default-report').value,
    SCAN_TIMEOUT: document.getElementById('scan-timeout').value,
  };
  const d = await fetch('/api/settings', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) }).then(r => r.json());
  toast(d.message || 'Saved!', d.status === 'ok' ? 'success' : 'error');
}

// Explicit allowlist: data attributes select actions, never executable code.
const clickActions = Object.freeze({
  navigate: el => nav(el, el.dataset.page),
  'quick-scan': quickScan,
  'start-scan': startScan,
  'start-bulk': startBulk,
  'start-monitor': startMonitor,
  'load-monitors': loadMonitors,
  'load-jobs': loadJobs,
  'load-reports': loadReports,
  'download-report': downloadReport,
  'close-viewer': closeViewer,
  'save-settings': saveSettings,
  'load-settings': loadSettings,
  'save-defaults': saveDefaults,
  'open-report': el => openReport(el.dataset.filename),
  'pdf-report': el => dlReport(el.dataset.filename),
  'stop-monitor': el => stopMonitor(el.dataset.target),
});
document.addEventListener('click', event => {
  const el = event.target.closest('[data-action]');
  if (!el || el.disabled || !Object.hasOwn(clickActions, el.dataset.action)) return;
  event.preventDefault();
  Promise.resolve().then(() => clickActions[el.dataset.action](el))
    .catch(() => toast('Request failed. Please try again.', 'error'));
});
document.addEventListener('input', event => {
  if (event.target.id === 'bulk-targets') updateBulkCount();
  if (event.target.id === 'report-search') filterReports();
});

// Init
loadOverview().catch(() => toast('Dashboard data could not be loaded.', 'error'));
setInterval(loadStatus, 8000);
