import { html, useEffect, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { navigate, toast, toastError, confirmDialog } from '../lib/store.js';
import { relTime } from '../lib/format.js';
import { Btn, Icon, Modal, Input, TextArea, Select, Empty, Spinner, StatusBadge, ImagePicker, Menu, useDebounced, setTitle } from '../components/ui.js';

const blank = { name: '', sector: '', contact_name: '', contact_email: '', contact_phone: '', about: '', website: '', logo: null };

export function Clients() {
  const [items, setItems] = useState(null);
  const [q, setQ] = useState('');
  const [sectors, setSectors] = useState([]);
  const [form, setForm] = useState(null);
  const [detail, setDetail] = useState(null);
  const load = (query = q) => api.get(`/api/clients?q=${encodeURIComponent(query)}`).then((r) => setItems(r.items)).catch(toastError);
  const deb = useDebounced(load, 250);
  useEffect(() => { setTitle('العملاء'); load(''); api.get('/api/library/sectors').then((r) => setSectors(r.items)).catch(() => {}); }, []);
  const sectorName = (k) => sectors.find((s) => s.key === k)?.title || k || '—';

  const save = async () => {
    try {
      const body = { ...form };
      delete body.id;
      if (form.id) await api.put(`/api/clients/${form.id}`, pick(body)); else await api.post('/api/clients', pick(body));
      toast('تم حفظ بيانات العميل'); setForm(null); load();
    } catch (e) { toastError(e); }
  };
  const del = async (c) => {
    if (!(await confirmDialog({ title: 'حذف العميل', danger: true, confirmLabel: 'حذف', message: `سيُحذف «${c.name}» من سجل العملاء. عروضه السابقة تبقى محفوظة.` }))) return;
    try { await api.del(`/api/clients/${c.id}`); toast('تم حذف العميل'); load(); } catch (e) { toastError(e); }
  };
  const open = async (c) => { try { setDetail(await api.get(`/api/clients/${c.id}`)); } catch (e) { toastError(e); } };

  return html`<div class="content">
    <div class="page-head"><div><h1>العملاء</h1><p>سجل العملاء وعروضهم. يُضاف العميل تلقائيًا عند إنشاء عرض باسمه.</p></div>
      <div class="actions"><${Btn} kind="primary" icon="plus" onClick=${() => setForm({ ...blank })}>إضافة عميل</${Btn}></div></div>
    <div class="filters"><div class="search-in"><${Icon} name="search" /><input class="input" type="search" placeholder="ابحث عن عميل أو قطاع…" value=${q} onInput=${(e) => { setQ(e.target.value); deb(e.target.value); }} /></div></div>
    <div class="card-ui">
      ${!items ? html`<div style="padding:18px"><${Spinner} /></div>` : items.length === 0 ? html`<${Empty} icon="users" title=${q ? 'لا توجد نتائج' : 'لا يوجد عملاء بعد'} text="أضف عميلًا أو أنشئ عرضًا وسيُضاف عميله تلقائيًا." />` : html`
      <div class="table-wrap has-m"><table class="table"><thead><tr><th>العميل</th><th>القطاع</th><th>جهة التواصل</th><th>العروض</th><th>آخر عرض</th><th></th></tr></thead><tbody>
      ${items.map((c) => html`<tr class="clickable" onClick=${() => open(c)}>
        <td><div class="inline" style="flex-wrap:nowrap">${c.logo ? html`<img src=${c.logo} alt="" style="width:34px;height:34px;object-fit:contain;border-radius:8px;border:1px solid var(--line);background:#fff" />` : html`<span class="avatar" style="width:34px;height:34px;border-radius:8px;background:var(--lilac);color:var(--brand);display:grid;place-items:center;font-weight:700">${c.name.slice(0, 1)}</span>`}
          <div><div class="t-main">${c.name}${c.is_demo ? html`<span class="tag-demo">Demo</span>` : ''}</div></div></div></td>
        <td class="t-sub">${sectorName(c.sector)}</td><td class="t-sub">${c.contact_name || '—'}</td><td>${c.proposals_count}</td><td class="t-sub">${c.last_proposal_at ? relTime(c.last_proposal_at) : '—'}</td>
        <td onClick=${(e) => e.stopPropagation()} style="text-align:left"><${Menu} trigger=${(t) => html`<button class="btn ghost icon" aria-label="إجراءات" onClick=${t}><${Icon} name="more" /></button>`} items=${[
          { label: 'عرض جديد لهذا العميل', icon: 'filePlus', onClick: () => navigate(`/new?client=${c.id}`) },
          { label: 'تعديل البيانات', icon: 'edit', onClick: () => setForm({ ...blank, ...c }) },
          { label: 'عروض العميل', icon: 'folder', onClick: () => navigate(`/proposals?client=${c.id}`) },
          '-', { label: 'حذف', icon: 'trash', danger: true, onClick: () => del(c) }]} /></td></tr>`)}
      </tbody></table></div>
      <div class="m-cards" style="padding:10px">${items.map((c) => html`<div class="card-ui m-card" onClick=${() => open(c)}><div class="r"><b class="grow">${c.name}</b><span class="badge violet plain">${c.proposals_count} عرض</span></div><span class="muted" style="font-size:13px">${sectorName(c.sector)}</span></div>`)}</div>`}
    </div>
    ${form && html`<${Modal} title=${form.id ? 'تعديل بيانات العميل' : 'إضافة عميل'} onClose=${() => setForm(null)} footer=${html`<${Btn} kind="primary" disabled=${!form.name.trim()} onClick=${save}>حفظ</${Btn}><${Btn} kind="ghost" onClick=${() => setForm(null)}>إلغاء</${Btn}>`}>
      <div class="stack">
        <div class="row"><div class="field"><span class="lbl">اسم العميل<span class="req">*</span></span><${Input} value=${form.name} onInput=${(v) => setForm({ ...form, name: v })} /></div>
          <div class="field"><span class="lbl">القطاع</span><${Select} value=${form.sector} placeholder="اختر القطاع" onChange=${(v) => setForm({ ...form, sector: v })} options=${sectors.map((s) => ({ value: s.key, label: s.title }))} /></div></div>
        <div class="row"><div class="field"><span class="lbl">جهة التواصل</span><${Input} value=${form.contact_name} onInput=${(v) => setForm({ ...form, contact_name: v })} /></div>
          <div class="field"><span class="lbl">البريد الإلكتروني</span><input class="input ltr" type="email" value=${form.contact_email || ''} onInput=${(e) => setForm({ ...form, contact_email: e.target.value })} /></div></div>
        <div class="row"><div class="field"><span class="lbl">الجوال</span><input class="input ltr" value=${form.contact_phone || ''} onInput=${(e) => setForm({ ...form, contact_phone: e.target.value })} /></div>
          <div class="field"><span class="lbl">الموقع</span><input class="input ltr" value=${form.website || ''} onInput=${(e) => setForm({ ...form, website: e.target.value })} /></div></div>
        <div class="field"><span class="lbl">نبذة</span><${TextArea} minRows=${2} value=${form.about} onInput=${(v) => setForm({ ...form, about: v })} /></div>
        <div class="field"><span class="lbl">الشعار</span><${ImagePicker} value=${form.logo} onChange=${(v) => setForm({ ...form, logo: v })} onUpload=${api.upload} /></div>
      </div></${Modal}>`}
    ${detail && html`<${Modal} size="wide" title=${detail.name} onClose=${() => setDetail(null)} footer=${html`<${Btn} kind="primary" icon="filePlus" onClick=${() => navigate(`/new?client=${detail.id}`)}>عرض جديد لهذا العميل</${Btn}><${Btn} kind="ghost" onClick=${() => setDetail(null)}>إغلاق</${Btn}>`}>
      <div class="stack">
        <div class="analysis"><div><span>القطاع</span><b>${sectorName(detail.sector)}</b></div><div><span>جهة التواصل</span><b>${detail.contact_name || '—'}</b></div><div><span>عدد العروض</span><b>${detail.proposals.length}</b></div></div>
        ${detail.about && html`<p class="muted">${detail.about}</p>`}
        ${detail.proposals.length ? html`<table class="table"><thead><tr><th>المشروع</th><th>النوع</th><th>الحالة</th><th>آخر تعديل</th></tr></thead><tbody>
          ${detail.proposals.map((p) => html`<tr class="clickable" onClick=${() => navigate(`/proposals/${p.id}`)}><td class="t-main">${p.project_name}</td><td class="t-sub">${p.type_label}</td><td><${StatusBadge} status=${p.status} /></td><td class="t-sub">${relTime(p.updated_at)}</td></tr>`)}</tbody></table>`
          : html`<p class="muted">لا توجد عروض لهذا العميل بعد.</p>`}
      </div></${Modal}>`}
  </div>`;
}

function pick(c) {
  const out = {};
  for (const k of Object.keys(blank)) out[k] = c[k] === '' ? null : c[k] ?? null;
  out.name = c.name;
  return out;
}
