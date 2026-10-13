// Headless print page: loads the proposal with a one-time token, lays it out, and signals readiness
// to the PDF exporter via window.__PRINT_READY__.
import { renderDocument } from './document/render.js';

async function main() {
  const params = new URLSearchParams(location.search);
  const id = params.get('id');
  const token = params.get('token');
  const res = await fetch(`/api/proposals/${encodeURIComponent(id)}/print-data?token=${encodeURIComponent(token)}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const { proposal, settings } = await res.json();
  const layout = proposal.doc?.layout === 'portrait' ? 'portrait' : 'landscape';
  document.getElementById('page-size').textContent =
    layout === 'portrait' ? '@page { size: 794px 1123px; margin: 0; }' : '@page { size: 1280px 720px; margin: 0; }';
  document.title = `${proposal.client_name} — ${proposal.project_name}`;
  await renderDocument(document.getElementById('host'), proposal, settings, { mode: 'print', clean: params.get('clean') === '1' });
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  window.__PRINT_READY__ = true;
}

main().catch((err) => {
  window.__PRINT_ERROR__ = String(err && err.message ? err.message : err);
});
