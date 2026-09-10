import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../dashboard/static/app.js', import.meta.url), 'utf8');
const html = fs.readFileSync(new URL('../dashboard/templates/index.html', import.meta.url), 'utf8');
const unsafe = '\"><img src=x onerror=alert(1)>&\' report.md';

function harness(pathname = '/insight-agent/') {
  const nodes = new Map();
  const handlers = {};
  const calls = [];
  const element = id => {
    if (!nodes.has(id)) nodes.set(id, {
      id, textContent: '', innerHTML: '', style: {}, value: '', dataset: {},
      classList: { add() {}, remove() {} }, setAttribute() {}, scrollIntoView() {},
    });
    return nodes.get(id);
  };
  const report = { domain: unsafe, filename: unsafe, created: unsafe, size_kb: unsafe, score: 80, has_pdf: true };
  const context = {
    location: { pathname }, Headers,
    document: {
      getElementById: element,
      querySelectorAll: () => [],
      addEventListener: (name, fn) => { handlers[name] = fn; },
    },
    setTimeout: () => 1, setInterval: () => 1, clearInterval() {},
    fetch: async (url, init = {}) => {
      calls.push({ url, init });
      let data = {};
      if (url === '/api/auth/status') data = { csrfToken: 'test-only-csrf' };
      else if (url.endsWith('/api/status')) data = { reports_count: 1, active_jobs: 0 };
      else if (url.endsWith('/api/reports')) data = [report, { ...report, score: 60 }];
      else if (url.endsWith('/api/monitor/list')) data = [{ target: unsafe, interval: 60, scan_count: unsafe, last_scan: unsafe, status: 'running' }];
      else if (url.endsWith('/api/jobs')) data = [{ target: unsafe, id: unsafe, started_at: unsafe, finished_at: unsafe, status: unsafe, score: unsafe }];
      else if (url.includes('/api/report/')) data = { content: unsafe };
      else if (url.endsWith('/api/settings')) data = { configured: {}, status: 'ok' };
      return { ok: true, json: async () => data };
    },
    open: (...args) => calls.push({ open: args }),
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(source, context);
  return { context, nodes, element, handlers, calls };
}

const flush = () => new Promise(resolve => setImmediate(resolve));

test('external script bootstraps standalone and prefixed dashboards without inline handlers', async () => {
  assert.match(html, /<script src="\.\/static\/app\.js" defer><\/script>/);
  assert.doesNotMatch(html + source, /\son(?:click|input|change)\s*=/i);
  assert.doesNotMatch(source, /\beval\s*\(|new Function\s*\(/);
  for (const pathname of ['/', '/insight-agent/']) {
    const h = harness(pathname);
    await flush();
    const base = pathname === '/' ? '' : '/insight-agent';
    assert.ok(h.calls.some(c => c.url === base + '/api/status'));
    assert.ok(h.calls.some(c => c.url === base + '/api/reports'));
    assert.equal(h.element('stat-reports').textContent, 1);
    assert.equal(typeof h.handlers.click, 'function');
    assert.equal(typeof h.handlers.input, 'function');
  }
});

test('untrusted reports, monitors, jobs and chart labels remain escaped text', async () => {
  const h = harness();
  await flush();
  await h.context.loadReports();
  await h.context.loadMonitors();
  await h.context.loadJobs();
  for (const id of ['recent-list', 'reports-table-body', 'monitor-list', 'jobs-list', 'sparkline']) {
    const rendered = h.element(id).innerHTML;
    assert.ok(rendered.includes('&lt;img'), `${id} must escape markup`);
    assert.ok(!rendered.includes('<img'), `${id} must not insert an element`);
    assert.ok(!rendered.includes(unsafe), `${id} must not interpolate raw values`);
  }
  assert.match(h.element('reports-table-body').innerHTML, /data-filename="&quot;&gt;&lt;img/);
  assert.equal(h.context.statusClass(unsafe), 'queued');
});

test('delegated actions preserve literal filenames, prefix, CSRF and navigation', async () => {
  const h = harness();
  await flush();
  async function click(dataset) {
    const el = { dataset, classList: { add() {} } };
    h.handlers.click({ target: { closest: () => el }, preventDefault() {} });
    await flush();
  }
  await click({ action: 'navigate', page: 'settings' });
  assert.ok(h.calls.some(c => c.url === '/insight-agent/api/settings'));
  await click({ action: 'open-report', filename: unsafe });
  assert.ok(h.calls.some(c => c.url === '/insight-agent/api/report/' + encodeURIComponent(unsafe)));
  assert.equal(h.element('report-content').textContent, unsafe);
  await click({ action: 'stop-monitor', target: unsafe });
  const stop = h.calls.find(c => c.url === '/insight-agent/api/monitor/stop');
  assert.equal(JSON.parse(stop.init.body).target, unsafe);
  assert.equal(stop.init.headers.get('X-Command-Center-CSRF'), 'test-only-csrf');
  const count = h.calls.length;
  await click({ action: 'constructor' });
  assert.equal(h.calls.length, count, 'prototype properties cannot invoke actions');
});
