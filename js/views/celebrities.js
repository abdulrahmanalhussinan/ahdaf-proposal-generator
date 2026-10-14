// The team's celebrity / influencer list. Upload sheets here; proposals only ever name people from it.
import { html, useEffect, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { store, toast, toastError, confirmDialog } from '../lib/store.js';
import { Btn, Icon, Empty, Spinner, setTitle } from '../components/ui.js';

export function Celebrities() {
  const [data, setData] = useState(null);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const load = (query = q) => api.get(`/api/celebrities?q=${encodeURIComponent(query)}`).then((r) => {
    setData(r);
    const m = store.get().meta;
    if (m && !query) store.set({ meta: { ...m, celebrities: r.total } });
  }).catch(toastError);
  useEffect(() => { setTitle('المشاهير'); load(''); }, []);
  useEffect(() => { const t = setTimeout(() => load(q), 250); return () => clearTimeout(t); }, [q]);

  const upload = async (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!file) return;
    setBusy(true);
    try {
      const r = await api.uploadFile('/api/celebrities/import', file);
      toast(`أُضيف ${r.added} اسم${r.skipped ? ` (تخطينا ${r.skipped} مكرر)` : ''}`);
      await load('');
    } catch (err) { toastError(err); } finally { setBusy(false); }
  };
  const removeSource = async (src) => {
    if (!(await confirmDialog({ title: 'حذف أسماء هذا الملف', message: `ستُحذف كل الأسماء التي جاءت من «${src}».`, confirmLabel: 'حذف', danger: true }))) return;
    try { await api.del(`/api/celebrities?source=${encodeURIComponent(src)}`); await load(''); } catch (err) { toastError(err); }
  };

  return html`<div class="content">
    <div class="page-head"><div><h1>المشاهير</h1><p>ارفع شيت المشاهير والمؤثرين، والنظام يرشّح منه في العروض حسب الفكرة والمدينة والقطاع. لا يذكر أي اسم من خارج هذه القائمة، والأرقام تُنقل كما هي في الشيت.</p></div>
      <div class="actions"><label class="btn primary" style="cursor:pointer">${busy ? html`<${Spinner} />` : html`<${Icon} name="upload" />`}${busy ? 'جارٍ القراءة…' : 'رفع شيت (Excel أو CSV)'}
        <input type="file" accept=".xlsx,.xlsm,.csv" style="display:none" onChange=${upload} disabled=${busy} /></label></div></div>
    <div class="notice info" style="margin-bottom:16px"><${Icon} name="info" /><span>يتعرف النظام على الأعمدة تلقائيًا، مثل: الاسم، الحساب، المنصة، عدد المتابعين، المجال، المدينة، ملاحظات. وإذا كان لكل منصة عمود (سناب، تيك توك…) يقرؤه أيضًا. أعمدة السعر تُحفظ هنا ولا تظهر في العروض.</span></div>
    ${!data ? html`<${Spinner} />` : html`
      ${data.sources.length > 0 && html`<div class="chips" style="margin-bottom:14px">${data.sources.map((s) => html`<span class="chip on">${s.source} · ${s.n}<button class="btn ghost icon sm" aria-label="حذف" onClick=${() => removeSource(s.source)}><${Icon} name="x" size=${13} /></button></span>`)}</div>`}
      ${data.total === 0 ? html`<${Empty} icon="star" title="لا توجد قائمة مشاهير بعد" text="ارفع الشيت مرة وحدة، ويستخدمه النظام في كل العروض اللي تحتاج مشاهير." />` : html`
        <div class="card-ui pad stack">
          <div class="inline" style="justify-content:space-between"><b>${data.total} اسم</b>
            <input class="input" style="max-width:280px" type="search" placeholder="ابحث بالاسم أو المجال أو المدينة" value=${q} onInput=${(e) => setQ(e.target.value)} /></div>
          <div class="table-wrap"><table class="table"><thead><tr><th>الاسم</th><th>الحساب</th><th>المنصات</th><th>المتابعون</th><th>المجال</th><th>المدينة</th><th></th></tr></thead>
            <tbody>${data.items.slice(0, 500).map((c) => html`<tr><td><b>${c.name}</b></td><td class="ltr">${c.handle || '—'}</td><td>${c.platforms || '—'}</td><td class="ltr">${c.followers || '—'}</td><td>${c.category || '—'}</td><td>${c.city || '—'}</td>
              <td><button class="btn ghost icon sm" aria-label="حذف" onClick=${async () => { try { await api.del(`/api/celebrities/${c.id}`); load(); } catch (err) { toastError(err); } }}><${Icon} name="trash" size=${15} /></button></td></tr>`)}</tbody></table></div>
          ${data.items.length > 500 && html`<p class="muted">يظهر أول 500 اسم. استخدم البحث للوصول للباقي.</p>`}
        </div>`}`}
  </div>`;
}
