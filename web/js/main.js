import { html, render, useEffect } from './vendor/preact-htm.js';
import { api } from './lib/api.js';
import { store, useStore, useRoute, match } from './lib/store.js';
import { Shell } from './components/shell.js';
import { Toasts, ConfirmHost, Empty, Btn, Spinner } from './components/ui.js';
import { Dashboard } from './views/dashboard.js';
import { Wizard } from './views/wizard.js';
import { Editor } from './views/editor.js';
import { Proposals } from './views/proposals.js';
import { Viewer } from './views/viewer.js';
import { Templates } from './views/templates.js';
import { Clients } from './views/clients.js';
import { Library } from './views/library.js';
import { Settings } from './views/settings.js';
import { Celebrities } from './views/celebrities.js';
import { STATIC } from './lib/env.js';
import { logoSVG } from './lib/brand.js';

const ROUTES = [
  ['/', Dashboard],
  ['/new', Wizard],
  ['/proposals', Proposals],
  ['/proposals/:id', Viewer],
  ['/proposals/:id/edit', Editor, { bare: true }],
  ['/proposals/:id/inputs', Wizard],
  ['/templates', Templates],
  ['/clients', Clients],
  ['/library', Library],
  ['/library/:kind', Library],
  ['/settings', Settings],
  ['/celebrities', Celebrities],
];

function App() {
  const { path, query } = useRoute();
  const meta = useStore((s) => s.meta);
  useEffect(() => {
    api.get('/api/meta').then((m) => store.set({ meta: m })).catch((e) => store.set({ metaError: e.message }));
  }, []);

  let view = null;
  let opts = {};
  for (const [pattern, Comp, o] of ROUTES) {
    const params = match(pattern, path);
    if (params) { view = html`<${Comp} params=${params} query=${query} path=${path} />`; opts = o || {}; break; }
  }
  if (!meta) {
    if (STATIC && !store.get().metaError) {
      return html`<div class="boot" role="status"><div><span dangerouslySetInnerHTML=${{ __html: logoSVG('#fff', 56) }}></span>
        <h1 style="font-size:24px;margin-top:22px">مولّد العروض الفنية</h1>
        <p>جارٍ تجهيز النظام داخل متصفحك. أول زيارة تستغرق بضع ثوانٍ، والزيارات التالية أسرع.</p><span class="spinner"></span></div></div>`;
    }
    return html`<div style="min-height:100vh;display:grid;place-items:center;color:var(--muted)">${store.get().metaError
      ? html`<${Empty} icon="alert" title="تعذر تحميل النظام" text=${store.get().metaError} />` : html`<${Spinner} />`}</div>`;
  }
  if (!view) {
    view = html`<div class="content"><${Empty} icon="search" title="الصفحة غير موجودة" text="تحقق من الرابط أو عُد إلى الرئيسية." action=${html`<${Btn} kind="primary" href="/">الرئيسية</${Btn}>`} /></div>`;
  }
  return html`<${Shell} path=${path} bare=${opts.bare}>${view}</${Shell}><${Toasts} /><${ConfirmHost} />`;
}

render(html`<${App} />`, document.getElementById('app'));
