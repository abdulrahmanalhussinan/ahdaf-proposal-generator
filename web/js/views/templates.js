import { html, useEffect, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { navigate, toast, toastError, confirmDialog, useStore } from '../lib/store.js';
import { Btn, Icon, Modal, Input, TextArea, Empty, Spinner, setTitle } from '../components/ui.js';

export function Templates() {
  const meta = useStore((s) => s.meta);
  const [items, setItems] = useState(null);
  const [edit, setEdit] = useState(null);
  const load = () => api.get('/api/templates').then((r) => setItems(r.items)).catch(toastError);
  useEffect(() => { setTitle('القوالب'); load(); }, []);
  const types = Object.fromEntries((meta?.project_types || []).map((t) => [t.key, t]));

  const del = async (t) => {
    if (!(await confirmDialog({ title: 'حذف القالب', danger: true, confirmLabel: 'حذف', message: `سيُحذف القالب «${t.name}». العروض التي أُنشئت منه لن تتأثر.` }))) return;
    try { await api.del(`/api/templates/${t.id}`); toast('تم حذف القالب'); load(); } catch (e) { toastError(e); }
  };
  const save = async () => {
    try { await api.put(`/api/templates/${edit.id}`, { name: edit.name, description: edit.description, project_type: edit.project_type, inputs: edit.inputs }); toast('تم حفظ القالب'); setEdit(null); load(); } catch (e) { toastError(e); }
  };

  return html`<div class="content">
    <div class="page-head"><div><h1>القوالب</h1><p>نقاط بداية جاهزة لأنواع المشاريع المتكررة: الخدمات والمدة والمنصات معبأة مسبقًا. أضف قوالبك من داخل أي عرض عبر «حفظ كقالب».</p></div></div>
    ${!items ? html`<${Spinner} />` : items.length === 0 ? html`<${Empty} icon="layout" title="لا توجد قوالب" text="احفظ أي عرض كقالب ليظهر هنا." />` : html`
    <div class="tpl-grid">${items.map((t) => html`<div class="card-ui tpl">
      <div class="inline"><span class="ti"><${Icon} name=${types[t.project_type]?.icon || 'layout'} /></span>${t.is_builtin ? html`<span class="badge violet plain">قالب أساسي</span>` : html`<span class="badge green plain">قالب الشركة</span>`}</div>
      <b>${t.name}</b><p>${t.description || types[t.project_type]?.label || ''}</p>
      <div class="acts"><${Btn} kind="primary" size="sm" icon="filePlus" onClick=${() => navigate(`/new?template=${t.id}`)}>استخدام القالب</${Btn}>
        ${!t.is_builtin && html`<${Btn} kind="ghost" size="sm" icon="edit" onClick=${() => setEdit({ ...t })}>تعديل</${Btn}><${Btn} kind="ghost" size="sm" icon="trash" onClick=${() => del(t)}>حذف</${Btn}>`}</div>
    </div>`)}</div>`}
    ${edit && html`<${Modal} title="تعديل القالب" onClose=${() => setEdit(null)} footer=${html`<${Btn} kind="primary" onClick=${save}>حفظ</${Btn}><${Btn} kind="ghost" onClick=${() => setEdit(null)}>إلغاء</${Btn}>`}>
      <div class="stack"><div class="field"><span class="lbl">اسم القالب</span><${Input} value=${edit.name} onInput=${(v) => setEdit({ ...edit, name: v })} /></div>
      <div class="field"><span class="lbl">الوصف</span><${TextArea} minRows=${2} value=${edit.description} onInput=${(v) => setEdit({ ...edit, description: v })} /></div></div>
    </${Modal}>`}
  </div>`;
}
