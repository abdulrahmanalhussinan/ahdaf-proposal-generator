// The four proposal designs, shown as live miniature pages rendered by the real document renderer.
import { html, useEffect, useRef } from '../vendor/preact-htm.js';
import { renderDocument, DESIGNS } from '../document/render.js';
import { Icon } from './ui.js';

export const DESIGN_KEYS = Object.keys(DESIGNS);

function sample(theme) {
  return {
    number: '', client_name: '', project_name: '',
    doc: {
      theme, layout: 'landscape', show_toc: false,
      cover: { kicker: 'عرض فني', title: 'اسم المشروع', subtitle: 'سطر يصف المشروع باختصار.', client: 'اسم العميل',
        prepared_by: 'شركة أهداف للخدمات التسويقية', date: 'أكتوبر 2026', version: '1.0' },
      sections: [{ id: 'sample', type: 'understanding', title: 'فهمنا للمشروع', title_en: 'Our Understanding', subtitle: 'قراءتنا للاحتياج والتحدي والفرصة.',
        visible: true, divider: false, blocks: [
          { id: 'c', type: 'cards', columns: 3, items: [
            { title: 'التحدي', text: 'ما الذي يقف بين العلامة وجمهورها اليوم.', icon: 'alert' },
            { title: 'الفرصة', text: 'المساحة التي يمكن أن تتميز فيها العلامة.', icon: 'spark' },
            { title: 'الجمهور', text: 'الشرائح التي يخاطبها المشروع.', icon: 'users' }] },
          { id: 'k', type: 'callout', label: 'الخلاصة', text: 'فكرة واحدة واضحة تجمع كل المخرجات.' }] }],
    },
  };
}

function Preview({ theme, width }) {
  const host = useRef(null);
  useEffect(() => {
    if (host.current) renderDocument(host.current, sample(theme), {}, { scaleTo: width, noClosing: true }).catch(() => {});
  }, [theme, width]);
  return html`<div class="design-prev" ref=${host} aria-hidden="true"></div>`;
}

export function DesignPicker({ value, onChange, width = 250, action }) {
  return html`<div class="design-grid" role="radiogroup" aria-label="تصميم العرض">
    ${DESIGN_KEYS.map((k) => html`<div role="radio" tabIndex="0" aria-checked=${value === k} class=${`design-opt ${value === k ? 'on' : ''}`}
        onClick=${() => onChange && onChange(k)} onKeyDown=${(e) => { if ((e.key === 'Enter' || e.key === ' ') && onChange) { e.preventDefault(); onChange(k); } }}>
      <${Preview} theme=${k} width=${width} />
      <div class="design-meta"><b>${value === k ? html`<${Icon} name="check" size=${16} />` : ''}${DESIGNS[k].name}</b><span>${DESIGNS[k].note}</span>
        ${action && action(k)}</div>
    </div>`)}
  </div>`;
}
