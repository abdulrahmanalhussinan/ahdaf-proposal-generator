// القوالب: the four proposal designs. Pick one, then create the proposal with it.
import { html, useEffect } from '../vendor/preact-htm.js';
import { navigate } from '../lib/store.js';
import { Btn, setTitle } from '../components/ui.js';
import { DesignPicker } from '../components/designs.js';

export function Templates() {
  useEffect(() => { setTitle('القوالب'); }, []);
  return html`<div class="content">
    <div class="page-head"><div><h1>القوالب</h1><p>أربعة تصاميم للعرض الفني. اختر واحدًا وابدأ، وتقدر تبدّل التصميم لأي عرض لاحقًا من المحرر.</p></div></div>
    <${DesignPicker} width=${280} onChange=${(k) => navigate(`/new?design=${k}`)}
      action=${(k) => html`<div style="margin-top:10px"><${Btn} kind="primary" size="sm" icon="filePlus" onClick=${(e) => { e.stopPropagation(); navigate(`/new?design=${k}`); }}>إنشاء عرض بهذا التصميم</${Btn}></div>`} />
  </div>`;
}
