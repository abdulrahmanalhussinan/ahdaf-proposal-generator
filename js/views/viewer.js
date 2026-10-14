import { html, useEffect, useRef, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { navigate, toastError } from '../lib/store.js';
import { shortDate, relTime } from '../lib/format.js';
import { Btn, Icon, StatusBadge, Menu, Spinner, Empty, setTitle } from '../components/ui.js';
import { renderDocument } from '../document/render.js';
import { exportFile, duplicate, reuse, remove } from './actions.js';

export function Viewer({ params }) {
  const [p, setP] = useState(null);
  const [settings, setSettings] = useState({});
  const [err, setErr] = useState(null);
  const [pages, setPages] = useState(0);
  const host = useRef(null);
  const wrap = useRef(null);

  useEffect(() => {
    Promise.all([api.get(`/api/proposals/${params.id}`), api.get('/api/settings')])
      .then(([prop, s]) => { setP(prop); setSettings(s.values || {}); setTitle(prop.project_name); })
      .catch((e) => (e.status === 404 ? setErr('notfound') : toastError(e)));
  }, [params.id]);

  useEffect(() => {
    if (!p || !host.current) return undefined;
    const draw = () => renderDocument(host.current, p, settings, { scaleTo: Math.min(1100, wrap.current.clientWidth - 32) })
      .then((r) => setPages(r.pageCount)).catch((e) => console.warn(e));
    draw();
    let t;
    const onResize = () => { clearTimeout(t); t = setTimeout(draw, 250); };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [p, settings]);

  if (err === 'notfound') return html`<div class="content"><${Empty} icon="search" title="العرض غير موجود" action=${html`<${Btn} kind="primary" href="/proposals">العروض السابقة</${Btn}>`} /></div>`;
  if (!p) return html`<div class="content" style="display:grid;place-items:center;min-height:50vh"><${Spinner} /></div>`;

  return html`<div class="content">
    <div class="page-head">
      <div><h1>${p.project_name}${p.is_demo && html`<span class="tag-demo">Demo</span>`}</h1>
        <p class="inline" style="gap:8px"><span>${p.client_name}</span>·<span>${p.meta?.type_label || ''}</span>·<${StatusBadge} status=${p.status} />·<span class="ltr">${p.number}</span>·<span>أُنشئ ${shortDate(p.created_at)}، آخر تعديل ${relTime(p.updated_at)}</span>·<span>${pages} صفحة</span></p></div>
      <div class="actions">
        <${Btn} kind="primary" icon="edit" href=${`/proposals/${p.id}/edit`}>تعديل</${Btn}>
        <${Btn} kind="light" icon="pdf" onClick=${() => exportFile(p, 'pdf')}>تصدير PDF</${Btn}>
        <${Btn} kind="light" icon="presentation" onClick=${() => exportFile(p, 'pptx')}>PowerPoint</${Btn}>
        <${Menu} align="left" trigger=${(t) => html`<button class="btn light icon" aria-label="المزيد" onClick=${t}><${Icon} name="more" /></button>`} items=${[
          { label: 'نسخ العرض', icon: 'copy', onClick: () => duplicate(p) },
          { label: 'إعادة استخدام لعميل آخر', icon: 'refresh', onClick: () => reuse(p) },
          '-',
          { label: 'حذف', icon: 'trash', danger: true, onClick: () => remove(p, () => navigate('/proposals')) },
        ]} />
      </div>
    </div>
    <div class="viewer" ref=${wrap}><div ref=${host}></div></div>
  </div>`;
}
