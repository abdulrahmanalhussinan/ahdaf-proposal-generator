// Browser-edition backend. Loads Pyodide, unpacks the app's Python package (py/app.zip) and answers
// API calls by calling app.browser.handle() in-process. The SQLite database lives in IndexedDB
// (Pyodide IDBFS at /data), so proposals stay on this device and survive reloads.
import { ApiError } from './api.js';

const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.29.5/full/';
const APP_DIR = '/home/pyodide/ahdaf';
let ready = null;
let py = null;
let browser = null;
let pptxReady = null;
let syncTimer = null;

function syncfs(populate) {
  return new Promise((resolve, reject) => py.FS.syncfs(populate, (err) => (err ? reject(err) : resolve())));
}

function persistSoon() {
  clearTimeout(syncTimer);
  syncTimer = setTimeout(() => syncfs(false).catch((e) => console.warn('persist failed', e)), 400);
}

export function boot() {
  if (!ready) {
    ready = (async () => {
      const { loadPyodide } = await import(`${PYODIDE}pyodide.mjs`);
      py = await loadPyodide({ indexURL: PYODIDE });
      await py.loadPackage(['sqlite3']);
      py.FS.mkdirTree('/data');
      py.FS.mount(py.FS.filesystems.IDBFS, {}, '/data');
      await syncfs(true);
      const res = await fetch(`py/app.zip?v=${encodeURIComponent(window.AHDAF_BUILD || '')}`);
      if (!res.ok) throw new Error(`تعذر تحميل ملفات النظام (${res.status})`);
      py.unpackArchive(await res.arrayBuffer(), 'zip', { extractDir: APP_DIR });
      py.runPython(`
import os, sys
sys.path.insert(0, ${JSON.stringify(APP_DIR)})
os.environ.update({"AHDAF_DATA_DIR": "/data", "AHDAF_SQLITE_WAL": "0", "AI_PROVIDER": "rules"})
from app import browser as _ahdaf_browser
_ahdaf_browser.init()
`);
      browser = py.globals.get('_ahdaf_browser');
      await syncfs(false);
      return py;
    })();
    ready.catch(() => { ready = null; });
  }
  return ready;
}

const extras = {};
// Readers for uploaded files load on first use only.
function packagesFor(path) {
  if (path.endsWith('/api/celebrities/import')) return extras.xlsx || (extras.xlsx = py.loadPackage(['openpyxl']));
  if (path.endsWith('/api/documents')) {
    return extras.pdf || (extras.pdf = py.loadPackage(['micropip']).then(() => py.pyimport('micropip').install('pypdf')));
  }
  return null;
}

export async function request(method, url, body) {
  await boot();
  const u = new URL(url, location.href);
  const need = method === 'POST' ? packagesFor(u.pathname) : null;
  if (need) await need;
  const query = Object.fromEntries(u.searchParams.entries());
  const out = JSON.parse(browser.handle(method, u.pathname.replace(/^.*?(\/api\/)/, '/api/'), JSON.stringify(query), JSON.stringify(body ?? null)));
  if (method !== 'GET') persistSoon();
  if (out.status >= 400) throw new ApiError(out.body?.detail || `حدث خطأ (${out.status})`, out.status);
  return out.status === 204 ? null : out.body;
}

export async function exportPptx(proposalId) {
  await boot();
  if (!pptxReady) {
    pptxReady = (async () => {
      await py.loadPackage(['lxml', 'Pillow', 'micropip', 'typing-extensions']);
      const micropip = py.pyimport('micropip');
      await micropip.install(['python-pptx==1.0.2', 'XlsxWriter']);
      py.FS.mkdirTree(`${APP_DIR}/web/assets/brand`);
      for (const name of ['logo-white.png', 'logo-purple.png', 'mark-white.png', 'mark-purple.png']) {
        const buf = new Uint8Array(await (await fetch(`assets/brand/${name}`)).arrayBuffer());
        py.FS.writeFile(`${APP_DIR}/web/assets/brand/${name}`, buf);
      }
    })();
    pptxReady.catch(() => { pptxReady = null; });
  }
  await pptxReady;
  const data = browser.export_pptx(proposalId);
  const bytes = data.toJs();
  data.destroy();
  return new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation' });
}
