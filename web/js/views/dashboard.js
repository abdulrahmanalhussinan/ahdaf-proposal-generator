import { html, useEffect, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { link, navigate, toastError } from '../lib/store.js';
import { relTime } from '../lib/format.js';
import { Btn, Icon, StatusBadge, Menu, Empty, setTitle } from '../components/ui.js';
import { rowMenu } from './actions.js';

export function Dashboard() {
  const [data, setData] = useState(null);
  const load = () => api.get('/api/dashboard').then(setData).catch(toastError);
  useEffect(() => { setTitle('الرئيسية'); load(); }, []);
  const st = data?.stats;
  const by = st?.by_status || {};

  return html`<div class="content">
    <section class="hero">
      <div class="copy">
        <h1>عرض فني جاهز للعميل، من معلومات المشروع مباشرة</h1>
        <p>أدخل بيانات المشروع، وسيكتب النظام العرض كاملًا بهوية أهداف: الفهم، والأهداف، والمنهجية، والجدول الزمني، والمخرجات، والمؤشرات. راجعه وعدّله ثم صدّره PDF.</p>
        <div class="actions">
          <${Btn} kind="on-dark" size="lg" icon="filePlus" href="/new">إنشاء عرض جديد</${Btn}>
          <${Btn} kind="light" size="lg" icon="layout" href="/templates" class="btn glass lg">البدء من قالب</${Btn}>
        </div>
      </div>
      <div class="stairs" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
    </section>

    <div class="stats">
      ${[
        ['إجمالي العروض', st?.total], ['مسودات قيد العمل', by.draft], ['قيد المراجعة أو مُرسلة', (by.sent || 0) + (by.review || 0)], ['عروض معتمدة', by.approved],
      ].map(([l, v]) => html`<div class="card-ui stat"><div class="v">${v ?? (data ? 0 : '—')}</div><div class="l">${l}</div></div>`)}
    </div>

    <div class="section-title"><h2>آخر العروض</h2><a href="/proposals" onClick=${(e) => link(e, '/proposals')}>كل العروض</a></div>
    <div class="card-ui">
      ${!data ? html`<div style="padding:18px" class="stack">${[1, 2, 3].map(() => html`<div class="skeleton" style="height:44px"></div>`)}</div>`
        : data.recent.length === 0 ? html`<${Empty} title="لا توجد عروض بعد" text="أنشئ أول عرض فني وسيظهر هنا." action=${html`<${Btn} kind="primary" icon="plus" href="/new">إنشاء عرض</${Btn}>`} />`
        : html`<div class="table-wrap"><table class="table"><thead><tr><th>العميل والمشروع</th><th>النوع</th><th>الحالة</th><th>آخر تعديل</th><th></th></tr></thead><tbody>
          ${data.recent.map((p) => html`<tr class="clickable" onClick=${() => navigate(`/proposals/${p.id}/edit`)}>
            <td><div class="t-main">${p.project_name}${p.is_demo && html`<span class="tag-demo">Demo</span>`}</div><div class="t-sub">${p.client_name}</div></td>
            <td class="t-sub">${p.type_label}</td><td><${StatusBadge} status=${p.status} /></td><td class="t-sub">${relTime(p.updated_at)}</td>
            <td onClick=${(e) => e.stopPropagation()} style="text-align:left"><${Menu} trigger=${(t) => html`<button class="btn ghost icon" aria-label="إجراءات" onClick=${t}><${Icon} name="more" /></button>`} items=${rowMenu(p, { onChange: load })} /></td></tr>`)}
        </tbody></table></div>`}
    </div>

    <div class="section-title"><h2>أدوات العمل</h2></div>
    <div class="quick">
      ${[
        ['/templates', 'layout', 'القوالب', `${data?.templates ?? ''} قالب جاهز لأنواع المشاريع المتكررة`],
        ['/library', 'book', 'مكتبة المحتوى', 'الخدمات والمخرجات والمنهجيات والمؤشرات التي يستخدمها النظام'],
        ['/clients', 'users', 'العملاء', `${st?.clients ?? ''} عميل وعروضهم`],
        ['/settings', 'settings', 'الإعدادات', 'بيانات الشركة والأسلوب الافتراضي للعروض'],
      ].map(([to, ic, t, d]) => html`<a class="card-ui" href=${to} onClick=${(e) => link(e, to)}><span class="qi"><${Icon} name=${ic} /></span><b>${t}</b><span>${d}</span></a>`)}
    </div>
  </div>`;
}
