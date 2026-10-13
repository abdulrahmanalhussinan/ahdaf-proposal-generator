// Proposal actions shared by the list, dashboard, viewer and editor.
import { api } from '../lib/api.js';
import { navigate, toast, toastError, confirmDialog } from '../lib/store.js';

export const REUSE_KEY = 'ahdaf.wizard.prefill';

export async function exportFile(p, kind) {
  const ext = kind === 'pptx' ? 'pptx' : 'pdf';
  try {
    toast(kind === 'pptx' ? 'جارٍ تجهيز ملف PowerPoint…' : 'جارٍ تجهيز ملف PDF…', 'ok', 2500);
    const name = await api.download(`/api/proposals/${p.id}/export/${ext}`, `proposal.${ext}`);
    toast(`تم تنزيل الملف: ${name}`);
  } catch (e) { toastError(e); }
}

export async function duplicate(p, after) {
  try {
    const copy = await api.post(`/api/proposals/${p.id}/duplicate`);
    toast('تم نسخ العرض');
    if (after) after(copy); else navigate(`/proposals/${copy.id}/edit`);
  } catch (e) { toastError(e); }
}

export async function reuse(p) {
  try {
    const { inputs } = await api.get(`/api/proposals/${p.id}/reuse`);
    try { sessionStorage.setItem(REUSE_KEY, JSON.stringify({ inputs, from: p.project_name })); } catch { /* storage unavailable */ }
    navigate('/new?reuse=1');
  } catch (e) { toastError(e); }
}

export async function remove(p, after) {
  const ok = await confirmDialog({ title: 'حذف العرض', danger: true, confirmLabel: 'حذف نهائي',
    message: `سيُحذف العرض «${p.project_name}» للعميل «${p.client_name}» وكل نسخه المحفوظة. لا يمكن التراجع عن الحذف.` });
  if (!ok) return;
  try {
    await api.del(`/api/proposals/${p.id}`);
    toast('تم حذف العرض');
    after && after();
  } catch (e) { toastError(e); }
}

export function rowMenu(p, { onChange } = {}) {
  return [
    { label: 'فتح', icon: 'eye', onClick: () => navigate(`/proposals/${p.id}`) },
    { label: 'تعديل', icon: 'edit', onClick: () => navigate(`/proposals/${p.id}/edit`) },
    { label: 'نسخ العرض', icon: 'copy', onClick: () => duplicate(p, () => onChange && onChange()) },
    { label: 'إعادة استخدام لعميل آخر', icon: 'refresh', onClick: () => reuse(p) },
    '-',
    { label: 'تصدير PDF', icon: 'pdf', onClick: () => exportFile(p, 'pdf') },
    { label: 'تصدير PowerPoint', icon: 'presentation', onClick: () => exportFile(p, 'pptx') },
    '-',
    { label: 'حذف', icon: 'trash', danger: true, onClick: () => remove(p, onChange) },
  ];
}
