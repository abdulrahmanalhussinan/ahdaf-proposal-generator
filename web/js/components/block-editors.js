// Editors for each block type of the proposal document.
import { html } from '../vendor/preact-htm.js';
import { Icon, Input, TextArea, Select, LinesInput, ImagePicker } from './ui.js';
import { api } from '../lib/api.js';
import { hasPlaceholder, parseISO, addDays, toISO, fmtDate } from '../lib/format.js';

export const BLOCK_LABELS = {
  lead: 'نص افتتاحي', paragraph: 'فقرة', callout: 'خلاصة مميزة', list: 'قائمة', cards: 'بطاقات', stats: 'أرقام',
  objectives: 'الأهداف', services: 'الخدمات', phases: 'المراحل', deliverables: 'جدول المخرجات', timeline: 'الجدول الزمني',
  team: 'فريق العمل', kpis: 'مؤشرات الأداء', risks: 'سجل المخاطر', table: 'جدول', steps: 'خطوات', image: 'صورة',
};
export const BLOCK_ICONS = {
  lead: 'quote', paragraph: 'text', callout: 'flag', list: 'list', cards: 'grid', stats: 'chart', objectives: 'target',
  services: 'layers', phases: 'compass', deliverables: 'table', timeline: 'calendar', team: 'users', kpis: 'chart',
  risks: 'alert', table: 'table', steps: 'list', image: 'image',
};
export const NEW_BLOCKS = {
  paragraph: () => ({ type: 'paragraph', text: '' }),
  list: () => ({ type: 'list', title: '', items: [], style: 'check' }),
  cards: () => ({ type: 'cards', title: '', items: [{ title: '', text: '', icon: 'spark' }], columns: 2 }),
  callout: () => ({ type: 'callout', label: 'الخلاصة', text: '' }),
  image: () => ({ type: 'image', src: null, caption: '' }),
  table: () => ({ type: 'table', title: '', columns: [{ key: 'a', label: 'البند' }, { key: 'b', label: 'التفاصيل' }], rows: [{ id: rid(), a: '', b: '' }] }),
};

export const rid = () => Math.random().toString(16).slice(2, 12);
const LEVELS = ['منخفضة', 'متوسطة', 'مرتفعة'];
const IMPACTS = ['منخفض', 'متوسط', 'مرتفع'];

function move(arr, i, d) {
  const j = i + d;
  if (j < 0 || j >= arr.length) return arr;
  const out = [...arr];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

function RowTools({ list, i, onChange, min = 0 }) {
  return html`<div class="side-tools">
    <button class="btn ghost icon sm" aria-label="أعلى" disabled=${i === 0} onClick=${() => onChange(move(list, i, -1))}><${Icon} name="chevronUp" size=${15} /></button>
    <button class="btn ghost icon sm" aria-label="أسفل" disabled=${i === list.length - 1} onClick=${() => onChange(move(list, i, 1))}><${Icon} name="chevronDown" size=${15} /></button>
    <button class="btn ghost icon sm" aria-label="حذف" disabled=${list.length <= min} onClick=${() => onChange(list.filter((_, j) => j !== i))}><${Icon} name="trash" size=${15} /></button>
  </div>`;
}

function Repeater({ items = [], onChange, render, make, addLabel = 'إضافة' }) {
  return html`<div>
    ${items.map((it, i) => html`<div class="item-ed"><div class="body">${render(it, (patch) => onChange(items.map((x, j) => (j === i ? { ...x, ...patch } : x))), i)}</div><${RowTools} list=${items} i=${i} onChange=${onChange} /></div>`)}
    <div class="add-row"><button class="btn soft sm" onClick=${() => onChange([...items, make()])}><${Icon} name="plus" size=${15} />${addLabel}</button></div>
  </div>`;
}

function TableEditor({ rows = [], onChange, cols, make, addLabel }) {
  return html`<div class="table-wrap"><table class="ed-table"><thead><tr>${cols.map((c) => html`<th style=${c.w ? `width:${c.w}` : ''}>${c.label}</th>`)}<th style="width:96px"></th></tr></thead><tbody>
    ${rows.map((r, i) => html`<tr>${cols.map((c) => html`<td>${c.render ? c.render(r, (patch) => onChange(rows.map((x, j) => (j === i ? { ...x, ...patch } : x)))) : html`
      ${c.area ? html`<${TextArea} minRows=${1} value=${r[c.key]} onInput=${(v) => onChange(rows.map((x, j) => (j === i ? { ...x, [c.key]: v } : x)))} />`
        : html`<input class=${`input ${c.num ? 'num' : ''}`} type=${c.num ? 'number' : 'text'} value=${r[c.key] ?? ''} onInput=${(e) => onChange(rows.map((x, j) => (j === i ? { ...x, [c.key]: c.num ? (e.target.value === '' ? null : Number(e.target.value)) : e.target.value } : x)))} />`}`}</td>`)}
      <td><div class="inline" style="gap:0;flex-wrap:nowrap">
        <button class="btn ghost icon sm" aria-label="أعلى" disabled=${i === 0} onClick=${() => onChange(move(rows, i, -1))}><${Icon} name="chevronUp" size=${15} /></button>
        <button class="btn ghost icon sm" aria-label="أسفل" disabled=${i === rows.length - 1} onClick=${() => onChange(move(rows, i, 1))}><${Icon} name="chevronDown" size=${15} /></button>
        <button class="btn ghost icon sm" aria-label="حذف" onClick=${() => onChange(rows.filter((_, j) => j !== i))}><${Icon} name="trash" size=${15} /></button></div></td></tr>`)}
  </tbody></table>
  <div class="add-row"><button class="btn soft sm" onClick=${() => onChange([...rows, make()])}><${Icon} name="plus" size=${15} />${addLabel}</button></div></div>`;
}

export function BlockEditor({ block, onChange }) {
  const set = (patch) => onChange({ ...block, ...patch });
  const ph = JSON.stringify(block).match(/\[\[[^\]]+\]\]/g);
  const warn = ph ? html`<span class="ph-warn"><${Icon} name="alert" size=${13} />${ph.length} حقل بحاجة لتعبئة</span>` : null;
  switch (block.type) {
    case 'lead':
    case 'paragraph':
      return html`<div class="stack" style="gap:6px">${warn}<${TextArea} value=${block.text} minRows=${block.type === 'lead' ? 2 : 3} onInput=${(v) => set({ text: v })} /></div>`;
    case 'callout':
      return html`<div class="stack" style="gap:8px">${warn}<div class="row" style="grid-template-columns:180px 1fr"><${Input} value=${block.label} onInput=${(v) => set({ label: v })} placeholder="العنوان" /><${TextArea} minRows=${2} value=${block.text} onInput=${(v) => set({ text: v })} /></div></div>`;
    case 'list':
      return html`<div class="stack" style="gap:8px">${warn}<${Input} value=${block.title} onInput=${(v) => set({ title: v })} placeholder="عنوان القائمة (اختياري)" />
        <${LinesInput} value=${block.items} onChange=${(items) => set({ items })} placeholder="بند في كل سطر" minRows=${4} />
        <span class="muted" style="font-size:12px">بند واحد في كل سطر.</span></div>`;
    case 'cards':
      return html`<div class="stack" style="gap:8px">${warn}<${Input} value=${block.title} onInput=${(v) => set({ title: v })} placeholder="عنوان (اختياري)" />
        <${Repeater} items=${block.items} onChange=${(items) => set({ items })} make=${() => ({ title: '', text: '', icon: 'spark' })} addLabel="إضافة بطاقة"
          render=${(it, up) => html`<${Input} value=${it.title} onInput=${(v) => up({ title: v })} placeholder="العنوان" /><${TextArea} minRows=${2} value=${it.text} onInput=${(v) => up({ text: v })} placeholder="النص" />`} /></div>`;
    case 'stats':
      return html`<${Repeater} items=${block.items} onChange=${(items) => set({ items })} make=${() => ({ value: '', label: '' })} addLabel="إضافة رقم"
        render=${(it, up) => html`<div class="row" style="grid-template-columns:140px 1fr"><${Input} value=${it.value} onInput=${(v) => up({ value: v })} placeholder="+100" /><${Input} value=${it.label} onInput=${(v) => up({ label: v })} placeholder="الوصف" /></div>`} />`;
    case 'objectives':
      return html`<div class="stack" style="gap:6px">${warn}<${Repeater} items=${block.items} onChange=${(items) => set({ items })} make=${() => ({ title: '', text: '', measure: '', target: 'يُحدد مع العميل' })} addLabel="إضافة هدف"
        render=${(it, up) => html`<${Input} value=${it.title} onInput=${(v) => up({ title: v, suggested: false })} placeholder="الهدف" />${it.suggested && html`<span class="ph-warn" style="align-self:flex-start">هدف مقترح — أكّده أو عدّله</span>`}
          <${TextArea} minRows=${2} value=${it.text} onInput=${(v) => up({ text: v })} placeholder="الصياغة القابلة للقياس" />
          <div class="row"><${Input} value=${it.measure} onInput=${(v) => up({ measure: v })} placeholder="يُقاس بـ" /><${Input} value=${it.target} onInput=${(v) => up({ target: v })} placeholder="القيمة المستهدفة" /></div>`} /></div>`;
    case 'services':
      return html`<${Repeater} items=${block.groups} onChange=${(groups) => set({ groups })} make=${() => ({ title: 'مجموعة جديدة', icon: 'spark', items: [] })} addLabel="إضافة مجموعة"
        render=${(g, up) => html`<${Input} value=${g.title} onInput=${(v) => up({ title: v })} placeholder="اسم المجموعة" />
          <${Repeater} items=${g.items} onChange=${(items) => up({ items })} make=${() => ({ title: '', text: '' })} addLabel="إضافة خدمة"
            render=${(it, up2) => html`<${Input} value=${it.title} onInput=${(v) => up2({ title: v })} placeholder="الخدمة" /><${TextArea} minRows=${1} value=${it.text} onInput=${(v) => up2({ text: v })} placeholder="الوصف" />`} />`} />`;
    case 'phases':
      return html`<${Repeater} items=${block.items} onChange=${(items) => set({ items })} make=${() => ({ title: '', goal: '', period: '', activities: [], outputs: [] })} addLabel="إضافة مرحلة"
        render=${(p, up) => html`<div class="row" style="grid-template-columns:1fr 220px"><${Input} value=${p.title} onInput=${(v) => up({ title: v })} placeholder="اسم المرحلة" /><${Input} value=${p.period} onInput=${(v) => up({ period: v })} placeholder="الفترة" /></div>
          <${Input} value=${p.goal} onInput=${(v) => up({ goal: v })} placeholder="هدف المرحلة" />
          <div class="row"><div class="field"><span class="lbl" style="font-size:12.5px">الأنشطة (سطر لكل نشاط)</span><${LinesInput} value=${p.activities} onChange=${(v) => up({ activities: v })} minRows=${3} /></div>
          <div class="field"><span class="lbl" style="font-size:12.5px">المخرجات</span><${LinesInput} value=${p.outputs || []} onChange=${(v) => up({ outputs: v })} minRows=${3} /></div></div>`} />`;
    case 'deliverables':
      return html`<${TableEditor} rows=${block.rows} onChange=${(rows) => set({ rows })} addLabel="إضافة مخرج"
        make=${() => ({ id: rid(), title: '', description: '', qty: null, unit: '', timing: '' })}
        cols=${[{ key: 'title', label: 'المخرج', w: '22%' }, { key: 'description', label: 'الوصف', area: true }, { key: 'qty', label: 'الكمية', num: true, w: '90px' }, { key: 'unit', label: 'الوحدة', w: '90px' }, { key: 'timing', label: 'التوقيت', w: '18%' }]} />`;
    case 'kpis':
      return html`<${TableEditor} rows=${block.items} onChange=${(items) => set({ items })} addLabel="إضافة مؤشر"
        make=${() => ({ id: rid(), name: '', name_en: '', definition: '', measurement: '', frequency: 'شهري', target: 'يُحدد مع العميل' })}
        cols=${[{ key: 'name', label: 'المؤشر', w: '16%' }, { key: 'name_en', label: 'بالإنجليزية', w: '13%' }, { key: 'definition', label: 'التعريف', area: true }, { key: 'measurement', label: 'أداة القياس', w: '15%' }, { key: 'frequency', label: 'الدورية', w: '10%' }, { key: 'target', label: 'المستهدف', w: '14%' }]} />`;
    case 'risks':
      return html`<${TableEditor} rows=${block.rows} onChange=${(rows) => set({ rows })} addLabel="إضافة خطر"
        make=${() => ({ id: rid(), risk: '', likelihood: 'متوسطة', impact: 'متوسط', mitigation: '' })}
        cols=${[{ key: 'risk', label: 'الخطر', area: true, w: '26%' },
          { key: 'likelihood', label: 'الاحتمالية', w: '110px', render: (r, up) => html`<${Select} value=${r.likelihood} onChange=${(v) => up({ likelihood: v })} options=${LEVELS.map((x) => ({ value: x, label: x }))} />` },
          { key: 'impact', label: 'التأثير', w: '110px', render: (r, up) => html`<${Select} value=${r.impact} onChange=${(v) => up({ impact: v })} options=${IMPACTS.map((x) => ({ value: x, label: x }))} />` },
          { key: 'mitigation', label: 'آلية المعالجة', area: true }]} />`;
    case 'team':
      return html`<${Repeater} items=${block.members} onChange=${(members) => set({ members })} make=${() => ({ id: rid(), role: '', role_en: '', count: 1, responsibilities: [] })} addLabel="إضافة عضو"
        render=${(m, up) => html`<div class="row" style="grid-template-columns:1fr 1fr 90px"><${Input} value=${m.role} onInput=${(v) => up({ role: v })} placeholder="المسمى الوظيفي" /><input class="input ltr" value=${m.role_en} onInput=${(e) => up({ role_en: e.target.value })} placeholder="Job title" /><input class="input" type="number" min="1" value=${m.count} onInput=${(e) => up({ count: Number(e.target.value) || 1 })} aria-label="العدد" /></div>
          <${LinesInput} value=${m.responsibilities} onChange=${(v) => up({ responsibilities: v })} minRows=${2} placeholder="المسؤوليات، سطر لكل مسؤولية" />`} />`;
    case 'steps':
      return html`<${Repeater} items=${block.items} onChange=${(items) => set({ items })} make=${() => ({ title: '', text: '' })} addLabel="إضافة خطوة"
        render=${(s, up) => html`<${Input} value=${s.title} onInput=${(v) => up({ title: v })} placeholder="الخطوة" /><${TextArea} minRows=${1} value=${s.text} onInput=${(v) => up({ text: v })} />`} />`;
    case 'table':
      return html`<div class="stack" style="gap:8px"><${Input} value=${block.title} onInput=${(v) => set({ title: v })} placeholder="عنوان الجدول" />
        <div class="inline">${(block.columns || []).map((c, ci) => html`<input class="input" style="max-width:170px" value=${c.label} onInput=${(e) => set({ columns: block.columns.map((x, j) => (j === ci ? { ...x, label: e.target.value } : x)) })} aria-label="اسم العمود" />`)}</div>
        <${TableEditor} rows=${block.rows} onChange=${(rows) => set({ rows })} addLabel="إضافة صف" make=${() => ({ id: rid() })}
          cols=${(block.columns || []).map((c) => ({ key: c.key, label: c.label, area: true }))} /></div>`;
    case 'image':
      return html`<div class="stack" style="gap:8px"><${ImagePicker} value=${block.src} onChange=${(src) => set({ src })} onUpload=${api.upload} /><${Input} value=${block.caption} onInput=${(v) => set({ caption: v })} placeholder="تعليق على الصورة (اختياري)" /></div>`;
    case 'timeline':
      return html`<${TimelineEditor} block=${block} set=${set} />`;
    default:
      return html`<p class="muted">هذا العنصر لا يحتاج إلى تعديل.</p>`;
  }
}

function TimelineEditor({ block, set }) {
  const start = parseISO(block.start_date);
  const total = Number(block.total_days) || 1;
  const rowDate = (off) => (start ? toISO(addDays(start, off)) : '');
  const endFor = (r) => (start ? toISO(addDays(start, r.offset + Math.max(1, r.days) - 1)) : '');
  const updRows = (rows) => {
    const maxEnd = rows.reduce((m, r) => Math.max(m, (Number(r.offset) || 0) + (Number(r.days) || 1)), 0);
    set({ rows, total_days: Math.max(total, maxEnd) });
  };
  return html`<div class="stack" style="gap:10px">
    <div class="row" style="--n:3">
      <div class="field"><span class="lbl" style="font-size:13px">تاريخ بداية المشروع</span><input class="input" type="date" value=${block.start_date || ''} onInput=${(e) => set({ start_date: e.target.value || null })} /><span class="hint">تغييره يحرّك الجدول كاملًا.</span></div>
      <div class="field"><span class="lbl" style="font-size:13px">المدة الكلية (أيام)</span><input class="input" type="number" min="1" value=${total} onInput=${(e) => set({ total_days: Number(e.target.value) || 1 })} /><span class="hint">${start ? `ينتهي في ${fmtDate(addDays(start, total - 1))}` : 'بدون تاريخ بداية يُعرض بالأسابيع.'}</span></div>
    </div>
    <${TableEditor} rows=${block.rows} onChange=${updRows} addLabel="إضافة نشاط" make=${() => ({ id: rid(), phase: '', activity: '', offset: 0, days: 7, owner: '' })}
      cols=${[{ key: 'phase', label: 'المرحلة', w: '16%' }, { key: 'activity', label: 'النشاط', area: true },
        { key: 'offset', label: start ? 'البداية' : 'يبدأ بعد (يوم)', w: start ? '150px' : '110px', render: (r, up) => (start
          ? html`<input class="input" type="date" value=${rowDate(r.offset)} onInput=${(e) => { const d = parseISO(e.target.value); if (d) up({ offset: Math.max(0, Math.round((d - start) / 86400000)) }); }} />`
          : html`<input class="input num" type="number" min="0" value=${r.offset} onInput=${(e) => up({ offset: Math.max(0, Number(e.target.value) || 0) })} />`) },
        { key: 'end', label: start ? 'النهاية' : 'المدة (يوم)', w: start ? '150px' : '100px', render: (r, up) => (start
          ? html`<input class="input" type="date" value=${endFor(r)} onInput=${(e) => { const d = parseISO(e.target.value); if (d) up({ days: Math.max(1, Math.round((d - start) / 86400000) - r.offset + 1) }); }} />`
          : html`<input class="input num" type="number" min="1" value=${r.days} onInput=${(e) => up({ days: Math.max(1, Number(e.target.value) || 1) })} />`) },
        { key: 'owner', label: 'المسؤول', w: '16%' }]} />
    <div class="field"><span class="lbl" style="font-size:13px">المحطات الرئيسية</span>
      <${TableEditor} rows=${block.milestones || []} onChange=${(milestones) => set({ milestones })} addLabel="إضافة محطة" make=${() => ({ id: rid(), label: '', offset: 0 })}
        cols=${[{ key: 'label', label: 'المحطة' }, { key: 'offset', label: start ? 'التاريخ' : 'اليوم', w: '170px', render: (m, up) => (start
          ? html`<input class="input" type="date" value=${rowDate(m.offset)} onInput=${(e) => { const d = parseISO(e.target.value); if (d) up({ offset: Math.max(0, Math.round((d - start) / 86400000)) }); }} />`
          : html`<input class="input num" type="number" min="0" value=${m.offset} onInput=${(e) => up({ offset: Number(e.target.value) || 0 })} />`) }]} /></div>
  </div>`;
}

export function countPlaceholders(doc) {
  const m = JSON.stringify(doc || {}).match(/\[\[[^\]]+\]\]/g);
  return m ? m.length : 0;
}

export { hasPlaceholder };
