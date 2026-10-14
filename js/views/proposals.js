import { html, useEffect, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { navigate, toastError, useStore } from '../lib/store.js';
import { relTime, shortDate, STATUS } from '../lib/format.js';
import { Btn, Icon, StatusBadge, Menu, Empty, Select, useDebounced, setTitle } from '../components/ui.js';
import { rowMenu } from './actions.js';

export function Proposals({ query }) {
  const meta = useStore((s) => s.meta);
  const [q, setQ] = useState(query.get('q') || '');
  const [status, setStatus] = useState(query.get('status') || '');
  const [type, setType] = useState(query.get('type') || '');
  const [year, setYear] = useState(query.get('year') || '');
  const [clientId] = useState(query.get('client') || '');
  const [data, setData] = useState(null);

  const load = (over = {}) => {
    const p = new URLSearchParams({ q, status, type, year, client_id: clientId, ...over });
    api.get(`/api/proposals?${p}`).then(setData).catch(toastError);
  };
  const debounced = useDebounced((v) => load({ q: v }), 250);
  useEffect(() => { setTitle('العروض السابقة'); }, []);
  useEffect(() => { load(); }, [status, type, year]);
  useEffect(() => { const nq = query.get('q') || ''; if (nq !== q) { setQ(nq); load({ q: nq }); } }, [query.get('q')]);

  const items = data?.items || [];
  const filtered = q || status || type || year || clientId;
  return html`<div class="content">
    <div class="page-head"><div><h1>العروض السابقة</h1><p>كل العروض المحفوظة. ابحث بالعميل أو المشروع أو الخدمة أو القطاع أو السنة.</p></div>
      <div class="actions"><${Btn} kind="primary" icon="filePlus" href="/new">إنشاء عرض جديد</${Btn}></div></div>
    <div class="filters">
      <div class="search-in"><${Icon} name="search" /><input class="input" type="search" placeholder="ابحث: اسم العميل، المشروع، الخدمة، القطاع، 2026…" value=${q}
        onInput=${(e) => { setQ(e.target.value); debounced(e.target.value); }} aria-label="بحث" /></div>
      <${Select} value=${status} onChange=${setStatus} placeholder="كل الحالات" options=${Object.entries(STATUS).map(([k, v]) => ({ value: k, label: v.label }))} />
      <${Select} value=${type} onChange=${setType} placeholder="كل الأنواع" options=${(meta?.project_types || []).map((t) => ({ value: t.key, label: t.label }))} />
      <${Select} value=${year} onChange=${setYear} placeholder="كل السنوات" options=${(data?.years || []).map((y) => ({ value: y, label: y }))} />
    </div>
    <div class="card-ui">
      ${!data ? html`<div style="padding:18px" class="stack">${[1, 2, 3, 4].map(() => html`<div class="skeleton" style="height:46px"></div>`)}</div>`
        : items.length === 0 ? html`<${Empty} icon=${filtered ? 'search' : 'folder'} title=${filtered ? 'لا توجد نتائج مطابقة' : 'لا توجد عروض بعد'}
            text=${filtered ? 'جرّب كلمة أخرى أو أزل بعض عوامل التصفية.' : 'أنشئ أول عرض فني وسيُحفظ هنا تلقائيًا.'}
            action=${!filtered && html`<${Btn} kind="primary" icon="plus" href="/new">إنشاء عرض</${Btn}>`} />`
        : html`
        <div class="table-wrap has-m"><table class="table"><thead><tr><th>رقم العرض</th><th>العميل</th><th>المشروع</th><th>النوع</th><th>الحالة</th><th>تاريخ الإنشاء</th><th>آخر تعديل</th><th></th></tr></thead><tbody>
        ${items.map((p) => html`<tr class="clickable" onClick=${() => navigate(`/proposals/${p.id}`)}>
          <td class="t-sub ltr">${p.number}</td>
          <td><div class="t-main">${p.client_name}${p.is_demo && html`<span class="tag-demo">Demo</span>`}</div><div class="t-sub">${p.sector_label}</div></td>
          <td><div>${p.project_name}</div>${p.missing_count > 0 && html`<div class="t-sub" style="color:var(--warn)">${p.missing_count} معلومات ناقصة</div>`}</td>
          <td class="t-sub">${p.type_label}</td><td><${StatusBadge} status=${p.status} /></td>
          <td class="t-sub nowrap">${shortDate(p.created_at)}</td><td class="t-sub nowrap">${relTime(p.updated_at)}</td>
          <td onClick=${(e) => e.stopPropagation()} style="text-align:left"><${Menu} trigger=${(t) => html`<button class="btn ghost icon" aria-label="إجراءات" onClick=${t}><${Icon} name="more" /></button>`} items=${rowMenu(p, { onChange: () => load() })} /></td>
        </tr>`)}
        </tbody></table></div>
        <div class="m-cards" style="padding:10px">${items.map((p) => html`<div class="card-ui m-card">
          <div class="r"><div class="grow" onClick=${() => navigate(`/proposals/${p.id}`)}><div class="t-main" style="font-weight:700">${p.project_name}${p.is_demo && html`<span class="tag-demo">Demo</span>`}</div><div class="t-sub muted" style="font-size:13px">${p.client_name} · ${p.type_label}</div></div>
          <${Menu} trigger=${(t) => html`<button class="btn ghost icon" aria-label="إجراءات" onClick=${t}><${Icon} name="more" /></button>`} items=${rowMenu(p, { onChange: () => load() })} /></div>
          <div class="r"><${StatusBadge} status=${p.status} /><span class="muted" style="font-size:12.5px">${relTime(p.updated_at)}</span><span class="muted ltr" style="font-size:12px;margin-inline-start:auto">${p.number}</span></div>
        </div>`)}</div>`}
    </div>
    ${data && items.length > 0 && html`<p class="muted" style="margin-top:10px;font-size:13px">${items.length} عرض</p>`}
  </div>`;
}
