import { html, useEffect, useMemo, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { navigate, toast, toastError, confirmDialog, useStore } from '../lib/store.js';
import { Btn, Icon, Modal, Input, TextArea, Select, Switch, Chips, LinesInput, Empty, Spinner, Tabs, setTitle } from '../components/ui.js';

const PHASE_ROLES = [{ value: 'plan', label: 'التخطيط' }, { value: 'prepare', label: 'الإعداد' }, { value: 'execute', label: 'التنفيذ' }, { value: 'optimize', label: 'التحسين' }, { value: 'report', label: 'القياس والتقرير' }];
const MODES = [{ value: 'fixed', label: 'كمية ثابتة' }, { value: 'monthly', label: 'شهريًا × مدة المشروع' }, { value: 'per_platform', label: 'لكل منصة' }];
const TONES = [{ value: 'formal', label: 'رسمي' }, { value: 'corporate', label: 'Corporate' }, { value: 'luxury', label: 'فاخر' }, { value: 'marketing', label: 'تسويقي' }, { value: 'concise', label: 'مختصر' }, { value: 'detailed', label: 'تفصيلي' }, { value: 'any', label: 'أي أسلوب' }];

const KIND_HELP = {
  services: 'كل خدمة تضيف إلى العرض وصفها في نطاق العمل، ومخرجاتها بكمياتها، وأنشطتها في المنهجية، والأدوار اللازمة في فريق العمل.',
  deliverables: 'مخرجات متكررة بوحداتها وكمياتها المعتادة، مرجعًا للفريق عند تعديل جداول المخرجات.',
  methodologies: 'مراحل التنفيذ لكل نوع مشروع. يبني النظام المنهجية والجدول الزمني من هذه المراحل وأوزانها.',
  kpis: 'تعريف كل مؤشر وطريقة قياسه. يختار النظام المؤشرات حسب نوع المشروع والأهداف، دون أرقام مستهدفة مخترعة.',
  intro_templates: 'نصوص مقدمة جاهزة يمكن اختيارها بدل الكتابة التلقائية. المتغيرات: {العميل} {المشروع} {القطاع} {المدة}.',
  conclusion_templates: 'نصوص خاتمة جاهزة. المتغيرات: {العميل} {المشروع} {القطاع} {المدة}.',
  roles: 'المسميات الوظيفية ومسؤولياتها. «الأولوية» تحدد من يبقى في الفريق عند تحديد عدد صغير من الأعضاء.',
  past_projects: 'أعمال سابقة تُعرض في قسم «أعمال ذات صلة» عند تفعيله. أدخل النتائج الحقيقية فقط.',
  sectors: 'معرفة القطاع: ما يحسم قرار العميل، وزوايا المحتوى، والمواسم، والاعتبارات التنظيمية.',
};

function schema(kind, ctx) {
  const types = ctx.types.map((t) => ({ value: t.key, label: t.label }));
  const roles = ctx.roles.map((r) => ({ value: r.key, label: r.title }));
  switch (kind) {
    case 'services': return [
      { key: 'title_en', label: 'الاسم بالإنجليزية', ltr: true },
      { key: 'category', label: 'التصنيف', type: 'select', options: ctx.categories.map((c) => ({ value: c.key, label: c.label })) },
      { key: 'description', label: 'الوصف', type: 'textarea' },
      { key: 'types', label: 'أنواع المشاريع المرتبطة', type: 'multi', options: [{ value: '*', label: 'كل الأنواع' }, ...types] },
      { key: 'roles', label: 'الأدوار المطلوبة', type: 'multi', options: roles },
      { key: 'deliverables', label: 'المخرجات', type: 'repeater', make: () => ({ title: '', description: '', qty: 1, unit: '', mode: 'fixed', phase: 'execute' }), fields: [
        { key: 'title', label: 'المخرج' }, { key: 'description', label: 'الوصف' }, { key: 'qty', label: 'الكمية', type: 'number' }, { key: 'unit', label: 'الوحدة' },
        { key: 'mode', label: 'طريقة الحساب', type: 'select', options: MODES }, { key: 'phase', label: 'المرحلة', type: 'select', options: PHASE_ROLES }] },
      ...PHASE_ROLES.map((p) => ({ key: `activities.${p.value}`, label: `أنشطة مرحلة ${p.label}`, type: 'lines' })),
    ];
    case 'deliverables': return [
      { key: 'description', label: 'الوصف', type: 'textarea' }, { key: 'unit', label: 'الوحدة' }, { key: 'qty', label: 'الكمية المعتادة', type: 'number' },
      { key: 'mode', label: 'طريقة الحساب', type: 'select', options: MODES }];
    case 'methodologies': return [
      { key: 'project_type', label: 'نوع المشروع', type: 'select', options: types },
      { key: 'phases', label: 'المراحل', type: 'repeater', make: () => ({ key: `p${Date.now()}`, name: '', role: 'execute', weight: 0.2, owner: 'project_manager', goal: '', activities: [], outputs: [] }), fields: [
        { key: 'name', label: 'اسم المرحلة' }, { key: 'role', label: 'دورها', type: 'select', options: PHASE_ROLES }, { key: 'weight', label: 'الوزن من المدة (0–1)', type: 'number', step: 0.01 },
        { key: 'owner', label: 'المسؤول', type: 'select', options: roles }, { key: 'goal', label: 'الهدف', type: 'textarea' },
        { key: 'activities', label: 'الأنشطة', type: 'lines' }, { key: 'outputs', label: 'المخرجات', type: 'lines' }] }];
    case 'kpis': return [
      { key: 'name_en', label: 'الاسم بالإنجليزية', ltr: true }, { key: 'definition', label: 'التعريف', type: 'textarea' },
      { key: 'measurement', label: 'أداة القياس' }, { key: 'frequency', label: 'الدورية' }, { key: 'types', label: 'أنواع المشاريع', type: 'multi', options: types }];
    case 'intro_templates':
    case 'conclusion_templates': return [
      { key: 'tone', label: 'الأسلوب المناسب', type: 'select', options: TONES }, { key: 'text', label: 'النص', type: 'textarea', rows: 5, hint: 'المتغيرات: {العميل} {المشروع} {القطاع} {المدة}' }];
    case 'roles': return [
      { key: 'title_en', label: 'المسمى بالإنجليزية', ltr: true }, { key: 'weight', label: 'الأولوية (0–100)', type: 'number' },
      { key: 'responsibilities', label: 'المسؤوليات', type: 'lines' }];
    case 'past_projects': return [
      { key: 'client', label: 'العميل' }, { key: 'year', label: 'السنة' },
      { key: 'sector', label: 'القطاع', type: 'select', options: ctx.sectors.map((s) => ({ value: s.key, label: s.title })) },
      { key: 'project_type', label: 'نوع المشروع', type: 'select', options: types },
      { key: 'summary', label: 'وصف مختصر', type: 'textarea' }, { key: 'results', label: 'النتائج الموثقة', type: 'textarea', hint: 'أرقام حقيقية فقط من تقارير المشروع.' }];
    case 'sectors': return [
      { key: 'aliases', label: 'كلمات دالة (لاكتشاف القطاع من الوصف)', type: 'lines' }, { key: 'audience', label: 'الجمهور المعتاد', type: 'textarea' },
      { key: 'drivers', label: 'ما يحسم قرار العميل', type: 'lines' }, { key: 'angles', label: 'زوايا المحتوى المناسبة', type: 'lines' },
      { key: 'seasons', label: 'المواسم', type: 'lines' }, { key: 'considerations', label: 'اعتبارات تنظيمية', type: 'lines' }];
    default: return [];
  }
}

const getPath = (obj, path) => path.split('.').reduce((o, k) => (o ? o[k] : undefined), obj);
function setPath(obj, path, value) {
  const keys = path.split('.');
  const out = { ...obj };
  let cur = out;
  keys.slice(0, -1).forEach((k) => { cur[k] = { ...(cur[k] || {}) }; cur = cur[k]; });
  cur[keys[keys.length - 1]] = value;
  return out;
}

function FieldInput({ f, value, onChange }) {
  switch (f.type) {
    case 'textarea': return html`<${TextArea} minRows=${f.rows || 2} value=${value} onInput=${onChange} />`;
    case 'lines': return html`<${LinesInput} value=${value || []} onChange=${onChange} minRows=${3} placeholder="سطر لكل بند" />`;
    case 'number': return html`<input class="input" type="number" step=${f.step || 1} value=${value ?? ''} onInput=${(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />`;
    case 'select': return html`<${Select} value=${value} onChange=${onChange} placeholder="—" options=${f.options} />`;
    case 'multi': return html`<${Chips} options=${f.options} value=${value || []} onChange=${onChange} />`;
    case 'repeater': return html`<div class="rep">${(value || []).map((it, i) => html`<div class="rep-item">
        <div class="rh"><b>${it.title || it.name || `عنصر ${i + 1}`}</b><span class="grow"></span>
          <button class="btn ghost icon sm" aria-label="أعلى" disabled=${i === 0} onClick=${() => { const a = [...value]; [a[i - 1], a[i]] = [a[i], a[i - 1]]; onChange(a); }}><${Icon} name="chevronUp" size=${15} /></button>
          <button class="btn ghost icon sm" aria-label="حذف" onClick=${() => onChange(value.filter((_, j) => j !== i))}><${Icon} name="trash" size=${15} /></button></div>
        <div class="row">${f.fields.map((sf) => html`<div class="field" style=${['textarea', 'lines'].includes(sf.type) ? 'grid-column:1/-1' : ''}><span class="lbl" style="font-size:12.5px">${sf.label}</span>
          <${FieldInput} f=${sf} value=${it[sf.key]} onChange=${(v) => onChange(value.map((x, j) => (j === i ? { ...x, [sf.key]: v } : x)))} /></div>`)}</div></div>`)}
      <div><button class="btn soft sm" onClick=${() => onChange([...(value || []), f.make()])}><${Icon} name="plus" size=${15} />إضافة</button></div></div>`;
    default: return html`<input class=${`input ${f.ltr ? 'ltr' : ''}`} value=${value ?? ''} onInput=${(e) => onChange(e.target.value)} />`;
  }
}

function summary(kind, it) {
  const d = it.data || {};
  return d.description || d.definition || d.text || d.summary || d.audience || (d.responsibilities || []).join('، ') || (d.phases || []).map((p) => p.name).join(' ← ') || '';
}

export function Library({ params }) {
  const meta = useStore((s) => s.meta);
  const kinds = meta?.library_kinds || [];
  const kind = params.kind || 'services';
  const [counts, setCounts] = useState({});
  const [items, setItems] = useState(null);
  const [ctx, setCtx] = useState({ roles: [], sectors: [] });
  const [edit, setEdit] = useState(null);
  const [q, setQ] = useState('');

  const loadCounts = () => api.get('/api/library').then((r) => setCounts(Object.fromEntries(r.kinds.map((k) => [k.key, k.count])))).catch(() => {});
  const load = () => { setItems(null); api.get(`/api/library/${kind}`).then((r) => setItems(r.items)).catch(toastError); };
  useEffect(() => { setTitle('مكتبة المحتوى'); loadCounts(); Promise.all([api.get('/api/library/roles'), api.get('/api/library/sectors')]).then(([r, s]) => setCtx({ roles: r.items, sectors: s.items })).catch(() => {}); }, []);
  useEffect(() => { load(); setQ(''); }, [kind]);

  const fields = useMemo(() => schema(kind, { ...ctx, types: meta?.project_types || [], categories: meta?.categories || [] }), [kind, ctx, meta]);
  const label = kinds.find((k) => k.key === kind)?.label || '';
  const shown = (items || []).filter((it) => !q || `${it.title} ${summary(kind, it)}`.includes(q));

  const save = async () => {
    try {
      const body = { title: edit.title, data: edit.data, active: edit.active !== false };
      if (edit.id) await api.put(`/api/library/${kind}/${edit.id}`, body); else await api.post(`/api/library/${kind}`, body);
      toast('تم الحفظ في المكتبة'); setEdit(null); load(); loadCounts();
    } catch (e) { toastError(e); }
  };
  const del = async (it) => {
    if (!(await confirmDialog({ title: 'حذف من المكتبة', danger: true, confirmLabel: 'حذف', message: `سيُحذف «${it.title}». العروض السابقة لن تتأثر، لكن العروض الجديدة لن تستخدمه. يمكنك تعطيله بدل حذفه.` }))) return;
    try { await api.del(`/api/library/${kind}/${it.id}`); toast('تم الحذف'); setEdit(null); load(); loadCounts(); } catch (e) { toastError(e); }
  };

  return html`<div class="content">
    <div class="page-head"><div><h1>مكتبة المحتوى</h1><p>المعرفة التي يكتب بها النظام العروض. أي تعديل هنا يظهر في العروض الجديدة مباشرة.</p></div>
      <div class="actions"><${Btn} kind="primary" icon="plus" onClick=${() => setEdit({ title: '', data: kind === 'intro_templates' || kind === 'conclusion_templates' ? { tone: 'any', text: '' } : {}, active: true })}>إضافة إلى «${label}»</${Btn}></div></div>
    <${Tabs} tabs=${kinds.map((k) => ({ key: k.key, label: k.label, count: counts[k.key] }))} value=${kind} onChange=${(k) => navigate(`/library/${k}`)} />
    <div class="notice info" style="margin-bottom:14px"><${Icon} name="info" /><span>${KIND_HELP[kind]}</span></div>
    <div class="filters"><div class="search-in"><${Icon} name="search" /><input class="input" type="search" placeholder=${`بحث في ${label}…`} value=${q} onInput=${(e) => setQ(e.target.value)} /></div></div>
    ${!items ? html`<${Spinner} />` : shown.length === 0 ? html`<${Empty} icon="book" title="لا توجد عناصر" text="أضف أول عنصر لهذا القسم." />` : html`
    <div class="lib-grid">${shown.map((it) => html`<div class="card-ui lib-item" role="button" tabIndex="0" onClick=${() => setEdit(JSON.parse(JSON.stringify(it)))} onKeyDown=${(e) => e.key === 'Enter' && setEdit(JSON.parse(JSON.stringify(it)))}>
      <div class="h"><b>${it.title}</b>${!it.active && html`<span class="badge gray plain">معطّل</span>`}${it.is_demo && html`<span class="tag-demo">Demo</span>`}</div>
      <p>${summary(kind, it)}</p>
      <div class="meta">${it.data?.category && html`<span class="badge violet plain">${(meta?.categories || []).find((c) => c.key === it.data.category)?.label}</span>`}
        ${it.data?.deliverables && html`<span class="badge gray plain">${it.data.deliverables.length} مخرجات</span>`}
        ${it.data?.phases && html`<span class="badge gray plain">${it.data.phases.length} مراحل</span>`}
        ${it.data?.name_en && html`<span class="badge gray plain ltr">${it.data.name_en}</span>`}
        ${it.data?.title_en && html`<span class="badge gray plain ltr">${it.data.title_en}</span>`}</div>
    </div>`)}</div>`}
    ${edit && html`<${Modal} size="wide" title=${edit.id ? `تعديل: ${edit.title}` : `إضافة إلى ${label}`} onClose=${() => setEdit(null)}
      footer=${html`<${Btn} kind="primary" disabled=${!edit.title.trim()} onClick=${save}>حفظ</${Btn}><${Btn} kind="ghost" onClick=${() => setEdit(null)}>إلغاء</${Btn}>${edit.id && html`<span style="flex:1"></span><${Btn} kind="ghost" icon="trash" onClick=${() => del(edit)}>حذف</${Btn}>`}`}>
      <div class="stack">
        <div class="row"><div class="field"><span class="lbl">الاسم</span><${Input} value=${edit.title} onInput=${(v) => setEdit({ ...edit, title: v })} /></div>
          <div class="field" style="justify-content:flex-end"><${Switch} checked=${edit.active !== false} onChange=${(v) => setEdit({ ...edit, active: v })} label="مفعّل (يستخدمه النظام في العروض الجديدة)" /></div></div>
        ${fields.map((f) => html`<div class="field"><span class="lbl">${f.label}</span><${FieldInput} f=${f} value=${getPath(edit.data, f.key)} onChange=${(v) => setEdit({ ...edit, data: setPath(edit.data || {}, f.key, v) })} />${f.hint && html`<span class="hint">${f.hint}</span>`}</div>`)}
      </div></${Modal}>`}
  </div>`;
}
