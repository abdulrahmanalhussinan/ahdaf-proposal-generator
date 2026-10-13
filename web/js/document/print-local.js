// PDF in the browser edition: lay the proposal out with the same paginator, then open the browser's
// print dialog (choose "Save as PDF"). Page size and backgrounds come from the document CSS.
import { renderDocument } from './render.js';

export async function printProposal(proposal, settings) {
  document.getElementById('print-root')?.remove();
  const root = document.createElement('div');
  root.id = 'print-root';
  document.body.appendChild(root);

  const layout = proposal.doc?.layout === 'portrait' ? 'portrait' : 'landscape';
  let size = document.getElementById('print-page-size');
  if (!size) {
    size = document.createElement('style');
    size.id = 'print-page-size';
    document.head.appendChild(size);
  }
  size.textContent = layout === 'portrait' ? '@page { size: 794px 1123px; margin: 0; }' : '@page { size: 1280px 720px; margin: 0; }';

  await renderDocument(root, proposal, settings, { mode: 'print' });
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

  const previousTitle = document.title;
  document.title = `أهداف - عرض فني - ${proposal.client_name} - ${proposal.project_name}`; // default PDF file name
  document.body.classList.add('printing');
  const cleanup = () => {
    document.body.classList.remove('printing');
    root.remove();
    document.title = previousTitle;
    window.removeEventListener('afterprint', cleanup);
  };
  window.addEventListener('afterprint', cleanup);
  window.print();
}
