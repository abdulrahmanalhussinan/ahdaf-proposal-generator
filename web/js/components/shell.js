import { html, useState } from '../vendor/preact-htm.js';
import { Icon, Btn } from './ui.js';
import { logoSVG, markSVG } from '../lib/brand.js';
import { store, useStore, link, navigate, hrefOf } from '../lib/store.js';
import { STATIC } from '../lib/env.js';

const NAV = [
  { to: '/', label: 'الرئيسية', icon: 'home', exact: true },
  { to: '/proposals', label: 'العروض السابقة', icon: 'folder' },
  { to: '/templates', label: 'القوالب', icon: 'layout' },
  { to: '/clients', label: 'العملاء', icon: 'users' },
  { to: '/library', label: 'مكتبة المحتوى', icon: 'book' },
  { to: '/settings', label: 'الإعدادات', icon: 'settings' },
];

function isActive(item, path) {
  if (item.exact) return path === item.to;
  return path === item.to || path.startsWith(`${item.to}/`);
}

export function Shell({ path, children, bare }) {
  const meta = useStore((s) => s.meta);
  const navOpen = useStore((s) => s.navOpen);
  const [q, setQ] = useState('');
  const ai = meta?.ai;
  const submit = (e) => { e.preventDefault(); navigate(`/proposals?q=${encodeURIComponent(q.trim())}`); };
  return html`<div class=${`app ${navOpen ? 'nav-open' : ''} ${bare ? 'bare' : ''}`} onClick=${(e) => { if (navOpen && e.target.classList.contains('app')) store.set({ navOpen: false }); }}>
    <aside class="side" aria-label="القائمة الرئيسية">
      <a class="brand" href=${hrefOf('/')} onClick=${(e) => link(e, '/')}>
        <span dangerouslySetInnerHTML=${{ __html: logoSVG('#fff', 34) }}></span>
        <small>مولّد العروض الفنية</small>
      </a>
      <div class="cta"><${Btn} kind="on-dark" block icon="filePlus" href="/new">إنشاء عرض جديد</${Btn}></div>
      <nav>${NAV.map((n) => html`<a class=${`nav ${isActive(n, path) ? 'on' : ''}`} href=${hrefOf(n.to)} aria-current=${isActive(n, path) ? 'page' : null} onClick=${(e) => link(e, n.to)}><${Icon} name=${n.icon} />${n.label}</a>`)}</nav>
      <span class="stairs" dangerouslySetInnerHTML=${{ __html: markSVG('#fff', 230) }}></span>
      <div class="foot">
        <span class="ai"><span class=${`dot ${ai?.enabled ? 'on' : ''}`}></span>${ai?.enabled ? 'الكتابة بالذكاء الاصطناعي مفعّلة' : 'محرك الكتابة الداخلي'}</span>
        ${STATIC && html`<span title="نسخة تعمل بالكامل داخل متصفحك، والعروض تُحفظ على هذا الجهاز فقط">نسخة المتصفح · العروض محفوظة على جهازك</span>`}
        <span>أهداف للخدمات التسويقية</span>
      </div>
    </aside>
    <div class="main">
      ${!bare && html`<header class="top">
        <button class="btn ghost icon burger" aria-label="القائمة" onClick=${() => store.set({ navOpen: !navOpen })}><${Icon} name="menu" /></button>
        <form class="search" role="search" onSubmit=${submit}>
          <${Icon} name="search" />
          <input type="search" placeholder="ابحث في العروض: عميل، مشروع، خدمة، قطاع، سنة…" value=${q} onInput=${(e) => setQ(e.target.value)} aria-label="بحث في العروض" />
        </form>
        <div class="user"><span>${meta?.user?.name || ''}</span><span class="avatar">أ</span></div>
      </header>`}
      ${children}
    </div>
  </div>`;
}
