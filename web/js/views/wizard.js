import { html, useEffect, useMemo, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { navigate, toast, toastError, useStore, confirmDialog } from '../lib/store.js';
import { parseISO, addDays, toISO, fmtDate } from '../lib/format.js';
import { Btn, Icon, Field, Input, TextArea, Select, Switch, Chips, Seg, ImagePicker, setTitle, Spinner } from '../components/ui.js';
import { REUSE_KEY } from './actions.js';

const DRAFT_KEY = 'ahdaf.wizard.draft';
const STEPS = [
  { key: 'client', title: 'معلومات العميل', desc: 'لمن نكتب هذا العرض؟' },
  { key: 'project', title: 'معلومات المشروع', desc: 'ما المشروع، ولمن يتوجه؟' },
  { key: 'scope', title: 'نطاق العمل', desc: 'حدود العمل وما يشمله وما لا يشمله.' },
  { key: 'services', title: 'الخدمات', desc: 'الخدمات التي ستقدمها أهداف في هذا المشروع.' },
  { key: 'timeline', title: 'المدة والجدول الزمني', desc: 'متى يبدأ المشروع وكم يستمر.' },
  { key: 'goals', title: 'الأهداف والمخرجات', desc: 'ما الذي يجب أن يتحقق، وما الذي سيُسلَّم.' },
  { key: 'prefs', title: 'التفضيلات', desc: 'أسلوب الكتابة ومستوى التفصيل وشكل العرض.' },
];
const TONE_HINT = {
  formal: 'لغة رسمية تناسب الجهات الحكومية', corporate: 'مباشر وواضح لعروض الشركات', luxury: 'راقٍ ومنتقى للعلامات الفاخرة',
  marketing: 'حيوي ومقنع بإيقاع تسويقي', concise: 'أقصر ما يمكن دون إخلال', detailed: 'شرح أوفى لكل قسم',
};
const PLATFORM_TYPES = ['social_media', 'content', 'influencer', 'digital_ads', 'campaign'];
const EVENT_TYPES = ['event', 'exhibition'];

const empty = () => ({
  client: { name: '', sector: '', about: '', contact_name: '', website: '', logo: null },
  project: { name: '', type: '', description: '', challenge: '', audience: '', location: '', event_date: '', platforms: [] },
  scope: { description: '', out_of_scope: '' },
  services: { selected: [], custom: [] },
  timeline: { duration_value: '', duration_unit: 'month', start_date: '', end_date: '', team_size: '' },
  goals: { objectives: '', deliverables: '', kpi_targets: '', budget: '', show_budget: false },
  preferences: { tone: 'corporate', detail: 'medium', layout: 'landscape', include_about: true, include_past_projects: false,
    dividers: true, intro_template: 'auto', conclusion_template: 'auto', version: '1.0', requirements: '', notes: '' },
});

function merge(base, extra) {
  const out = { ...base };
  for (const k of Object.keys(extra || {})) {
    out[k] = typeof base[k] === 'object' && base[k] && !Array.isArray(base[k]) ? { ...base[k], ...(extra[k] || {}) } : extra[k];
  }
  return out;
}

export function Wizard({ params, query }) {
  const meta = useStore((s) => s.meta);
  const editId = params.id || null;
  const [data, setData] = useState(null);
  const [step, setStep] = useState(0);
  const [lib, setLib] = useState({ services: [], sectors: [], intro: [], conclusion: [], clients: [] });
  const [errors, setErrors] = useState({});
  const [analysis, setAnalysis] = useState(null);
  const [gen, setGen] = useState(null);
  const [origin, setOrigin] = useState('');

  // ---- load library + initial inputs
  useEffect(() => {
    setTitle(editId ? 'تعديل مدخلات العرض' : 'إنشاء عرض جديد');
    (async () => {
      try {
        const [svc, sec, intro, concl, clients, settings] = await Promise.all([
          api.get('/api/library/services'), api.get('/api/library/sectors'), api.get('/api/library/intro_templates'),
          api.get('/api/library/conclusion_templates'), api.get('/api/clients'), api.get('/api/settings')]);
        setLib({ services: svc.items.filter((s) => s.active), sectors: sec.items.filter((s) => s.active), intro: intro.items, conclusion: concl.items, clients: clients.items });
        const base = empty();
        const sv = settings.values || {};
        base.preferences = { ...base.preferences, tone: sv.default_tone || 'corporate', detail: sv.default_detail || 'medium', layout: sv.default_layout || 'landscape' };
        let initial = base;
        if (editId) {
          const p = await api.get(`/api/proposals/${editId}`);
          initial = merge(base, p.inputs);
          setOrigin(`تعديل مدخلات: ${p.project_name}`);
        } else if (query.get('template')) {
          const t = (await api.get('/api/templates')).items.find((x) => x.id === query.get('template'));
          if (t) { initial = merge(base, t.inputs); setOrigin(`من قالب: ${t.name}`); }
        } else if (query.get('reuse')) {
          try {
            const saved = JSON.parse(sessionStorage.getItem(REUSE_KEY) || 'null');
            if (saved) { initial = merge(base, saved.inputs); setOrigin(`إعادة استخدام: ${saved.from}`); sessionStorage.removeItem(REUSE_KEY); }
          } catch { /* ignore */ }
        } else if (query.get('client')) {
          const c = clients.items.find((x) => x.id === query.get('client'));
          if (c) initial = merge(base, { client: { id: c.id, name: c.name, sector: c.sector || '', about: c.about || '', contact_name: c.contact_name || '', website: c.website || '', logo: c.logo } });
        } else {
          try {
            const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null');
            if (draft && draft.client) { initial = merge(base, draft); setOrigin('استُكملت المسودة غير المكتملة'); }
          } catch { /* ignore */ }
        }
        setData(initial);
      } catch (e) { toastError(e); }
    })();
  }, [editId]);

  // ---- autosave draft (new proposals only)
  useEffect(() => {
    if (!data || editId) return;
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(data)); } catch { /* storage unavailable */ }
  }, [data]);

  if (!data) return html`<div class="content" style="display:grid;place-items:center;min-height:50vh"><${Spinner} /></div>`;

  const set = (group, key, value) => setData((d) => ({ ...d, [group]: { ...d[group], [key]: value } }));
  const type = data.project.type;
  const typeMeta = (meta?.project_types || []).find((t) => t.key === type);

  const validate = (i) => {
    const e = {};
    if (i === 0 && !data.client.name.trim()) e['client.name'] = 'اكتب اسم العميل';
    if (i === 1) {
      if (!data.project.name.trim()) e['project.name'] = 'اكتب اسم المشروع';
      if (!data.project.type) e['project.type'] = 'اختر نوع المشروع';
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };
  const go = (i) => {
    if (i > step) { for (let s = step; s < i; s++) if (!validate(s)) { setStep(s); return; } }
    setStep(i);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (i === STEPS.length - 1) runAnalysis();
  };
  const runAnalysis = () => api.post('/api/proposals/analyze', { inputs: data }).then(setAnalysis).catch(() => setAnalysis(null));

  const suggestServices = () => {
    if (!typeMeta) return;
    const avail = new Set(lib.services.map((s) => s.key));
    set('services', 'selected', typeMeta.default_services.filter((k) => avail.has(k)));
    toast('تم اختيار الخدمات المعتادة لهذا النوع من المشاريع');
  };

  const generate = async () => {
    for (let s = 0; s < 2; s++) if (!validate(s)) { setStep(s); return; }
    if (editId) {
      const ok = await confirmDialog({ title: 'إعادة توليد العرض', confirmLabel: 'إعادة التوليد',
        message: 'سيُعاد توليد جميع أقسام العرض بالمدخلات الجديدة، وستُحفظ النسخة الحالية في سجل النسخ لتتمكن من استرجاعها.' });
      if (!ok) return;
    }
    const started = Date.now();
    setGen({ stage: 0 });
    const ticker = setInterval(() => setGen((g) => (g ? { stage: Math.min(g.stage + 1, 4) } : g)), 520);
    try {
      let target;
      if (editId) {
        await api.put(`/api/proposals/${editId}`, { inputs: data });
        target = await api.post(`/api/proposals/${editId}/regenerate`, { inputs: data });
      } else {
        target = await api.post('/api/proposals/generate', { inputs: data });
        try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
      }
      const wait = Math.max(0, 2400 - (Date.now() - started));
      setTimeout(() => { clearInterval(ticker); setGen(null); navigate(`/proposals/${target.id}/edit`); toast('تم إنشاء العرض الفني'); }, wait);
    } catch (e) {
      clearInterval(ticker);
      setGen(null);
      toastError(e);
    }
  };

  const reset = async () => {
    if (!(await confirmDialog({ title: 'بدء عرض جديد من الصفر', message: 'ستُمسح كل المدخلات الحالية في هذا النموذج.', confirmLabel: 'مسح المدخلات', danger: true }))) return;
    try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
    setData(empty()); setStep(0); setOrigin('');
  };

  const progress = Math.round(((step + 1) / STEPS.length) * 100);
  const S = STEPS[step];

  return html`<div class="content">
    <div class="page-head"><div><h1>${editId ? 'تعديل مدخلات العرض' : 'إنشاء عرض فني جديد'}</h1><p>${origin || 'سبع خطوات قصيرة، ثم يكتب النظام العرض كاملًا. الحقول غير الإلزامية يمكن تركها.'}</p></div>
      <div class="actions">${!editId && html`<${Btn} kind="ghost" icon="refresh" onClick=${reset}>بدء من الصفر</${Btn}>`}</div></div>
    <div class="wiz">
      <aside class="card-ui wiz-steps" aria-label="خطوات الإنشاء">
        <div class="inline" style="justify-content:space-between;font-size:13px"><b style="color:var(--night)">الخطوة ${step + 1} من ${STEPS.length}</b><span class="muted">${progress}%</span></div>
        <div class="wiz-progress" role="progressbar" aria-valuenow=${progress} aria-valuemin="0" aria-valuemax="100"><i style=${`width:${progress}%`}></i></div>
        <ol>${STEPS.map((s, i) => html`<li class=${i === step ? 'on' : i < step ? 'done' : ''}><button onClick=${() => go(i)} aria-current=${i === step ? 'step' : null}><span class="n">${i < step ? html`<${Icon} name="check" size=${14} />` : i + 1}</span>${s.title}</button></li>`)}</ol>
      </aside>
      <section class="card-ui wiz-card">
        <div class="step-h"><div><div class="k">الخطوة ${step + 1}</div><h2>${S.title}</h2><p>${S.desc}</p></div></div>
        ${step === 0 && html`<${StepClient} data=${data} set=${set} lib=${lib} errors=${errors} setData=${setData} />`}
        ${step === 1 && html`<${StepProject} data=${data} set=${set} meta=${meta} errors=${errors} />`}
        ${step === 2 && html`<${StepScope} data=${data} set=${set} />`}
        ${step === 3 && html`<${StepServices} data=${data} set=${set} meta=${meta} lib=${lib} suggest=${suggestServices} typeMeta=${typeMeta} />`}
        ${step === 4 && html`<${StepTimeline} data=${data} set=${set} typeMeta=${typeMeta} />`}
        ${step === 5 && html`<${StepGoals} data=${data} set=${set} />`}
        ${step === 6 && html`<${StepPrefs} data=${data} set=${set} meta=${meta} lib=${lib} analysis=${analysis} goTo=${go} />`}
        <div class="wiz-nav">
          ${step > 0 && html`<${Btn} kind="light" icon="chevronRight" onClick=${() => go(step - 1)}>السابق</${Btn}>`}
          <span class="spacer"></span>
          ${step < STEPS.length - 1
            ? html`<${Btn} kind="primary" onClick=${() => go(step + 1)}>التالي <${Icon} name="chevronLeft" /></${Btn}>`
            : html`<${Btn} kind="primary" size="lg" icon="wand" onClick=${generate}>${editId ? 'إعادة توليد العرض' : 'توليد العرض الفني'}</${Btn}>`}
        </div>
      </section>
    </div>
    ${gen && html`<${Generating} stage=${gen.stage} />`}
  </div>`;
}

function Generating({ stage }) {
  const steps = ['تحليل معلومات المشروع والقطاع', 'صياغة المقدمة وفهم المشروع والأهداف', 'بناء المنهجية والجدول الزمني', 'تجهيز المخرجات والفريق والمؤشرات', 'مراجعة الصياغة وتنسيق الصفحات'];
  return html`<div class="gen-overlay" role="alert" aria-busy="true"><div class="gen-box">
    <div class="gen-stairs" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
    <h2>نكتب العرض الفني الآن</h2><p>نحلل المدخلات ونصوغ كل قسم بحسب المشروع.</p>
    <ul class="gen-steps">${steps.map((s, i) => html`<li class=${i < stage ? 'done' : i === stage ? 'now' : ''}><span class="s">${i < stage ? html`<${Icon} name="check" size=${13} />` : ''}</span>${s}</li>`)}</ul>
  </div></div>`;
}

// ---------------------------------------------------------------- steps
function StepClient({ data, set, lib, errors, setData }) {
  const c = data.client;
  const sectorOptions = lib.sectors.map((s) => ({ value: s.key, label: s.title }));
  const known = lib.sectors.some((s) => s.key === c.sector);
  const [custom, setCustom] = useState(c.sector && !known);
  const pickClient = (name) => {
    set('client', 'name', name);
    const found = lib.clients.find((x) => x.name === name);
    if (found) {
      setData((d) => ({ ...d, client: { ...d.client, id: found.id, name: found.name, sector: found.sector || d.client.sector, about: found.about || d.client.about, contact_name: found.contact_name || d.client.contact_name, website: found.website || d.client.website, logo: found.logo || d.client.logo } }));
      toast('تم استكمال بيانات العميل من سجل العملاء');
    } else {
      setData((d) => ({ ...d, client: { ...d.client, id: undefined, name } }));
    }
  };
  return html`<div class="stack">
    <div class="row">
      <${Field} label="اسم العميل" required id="c-name" error=${errors['client.name']} hint="اكتب الاسم كما يجب أن يظهر في العرض. يمكنك الاختيار من العملاء السابقين.">
        <input id="c-name" class=${`input ${errors['client.name'] ? 'invalid' : ''}`} list="clients-list" value=${c.name} onInput=${(e) => set('client', 'name', e.target.value)} onChange=${(e) => pickClient(e.target.value)} placeholder="مثال: شركة ... للتطوير العقاري" />
        <datalist id="clients-list">${lib.clients.map((x) => html`<option value=${x.name} />`)}</datalist>
      </${Field}>
      <${Field} label="القطاع" id="c-sector" hint="يُستخدم لفهم قرار العميل وزوايا المحتوى والاعتبارات التنظيمية.">
        ${custom
          ? html`<div class="inline" style="flex-wrap:nowrap"><input id="c-sector" class="input" value=${c.sector} onInput=${(e) => set('client', 'sector', e.target.value)} placeholder="اكتب القطاع" /><${Btn} kind="ghost" size="sm" onClick=${() => { setCustom(false); set('client', 'sector', ''); }}>من القائمة</${Btn}></div>`
          : html`<${Select} id="c-sector" value=${c.sector} placeholder="اختر القطاع" options=${[...sectorOptions, { value: '__custom', label: 'قطاع آخر…' }]} onChange=${(v) => { if (v === '__custom') { setCustom(true); set('client', 'sector', ''); } else set('client', 'sector', v); }} />`}
      </${Field}>
    </div>
    <${Field} label="نبذة عن العميل" optional hint="سطر أو سطران عن نشاط العميل. تظهر في قسم «فهمنا للمشروع» كما كتبتها.">
      <${TextArea} value=${c.about} onInput=${(v) => set('client', 'about', v)} minRows=${2} placeholder="مثال: مطور عقاري يطلق مشروعًا سكنيًا جديدًا في شمال الرياض." />
    </${Field}>
    <div class="row">
      <${Field} label="جهة التواصل لدى العميل" optional><${Input} value=${c.contact_name} onInput=${(v) => set('client', 'contact_name', v)} placeholder="الاسم أو الإدارة" /></${Field}>
      <${Field} label="الموقع أو الحساب الرئيسي" optional><${Input} class="input ltr" value=${c.website} onInput=${(v) => set('client', 'website', v)} placeholder="www.example.com" /></${Field}>
    </div>
    <${Field} label="شعار العميل" optional hint="يظهر على الغلاف وبجانب شعار أهداف في رأس الصفحات. يفضّل PNG بخلفية شفافة.">
      <${ImagePicker} value=${c.logo} onChange=${(v) => set('client', 'logo', v)} onUpload=${api.upload} label="رفع الشعار" />
    </${Field}>
  </div>`;
}

function StepProject({ data, set, meta, errors }) {
  const p = data.project;
  return html`<div class="stack">
    <${Field} label="اسم المشروع" required id="p-name" error=${errors['project.name']}>
      <input id="p-name" class=${`input ${errors['project.name'] ? 'invalid' : ''}`} value=${p.name} onInput=${(e) => set('project', 'name', e.target.value)} placeholder="مثال: إدارة حساب تيك توك، حفل تدشين مشروع…" />
    </${Field}>
    <div class="field"><span class="lbl">نوع المشروع<span class="req">*</span></span>
      <div class="type-grid" role="radiogroup">${(meta?.project_types || []).map((t) => html`<button type="button" role="radio" aria-checked=${p.type === t.key} class=${`type-opt ${p.type === t.key ? 'on' : ''}`} onClick=${() => set('project', 'type', t.key)}><span class="ti"><${Icon} name=${t.icon} /></span>${t.label}</button>`)}</div>
      ${errors['project.type'] && html`<span class="err">${errors['project.type']}</span>`}
    </div>
    <${Field} label="وصف المشروع" hint="ما المطلوب تحديدًا؟ كلما كان الوصف أوضح، كان العرض أدق.">
      <${TextArea} value=${p.description} onInput=${(v) => set('project', 'description', v)} minRows=${3} placeholder="مثال: إدارة حساب الشركة على تيك توك وصناعة محتوى قصير يعرض الأسطول وتجربة الحجز والاستلام." />
    </${Field}>
    <div class="row">
      <${Field} label="الجمهور المستهدف" optional hint="الفئة، المدينة، الاهتمامات. لن يُخترع إن تُرك فارغًا.">
        <${TextArea} value=${p.audience} onInput=${(v) => set('project', 'audience', v)} minRows=${2} placeholder="مثال: العائلات والمسافرون بين المدن" />
      </${Field}>
      <${Field} label="التحدي أو الوضع الحالي" optional hint="ما المشكلة التي يريد العميل حلها؟">
        <${TextArea} value=${p.challenge} onInput=${(v) => set('project', 'challenge', v)} minRows=${2} placeholder="مثال: الحساب ينشر عروضًا فقط والتفاعل منخفض." />
      </${Field}>
    </div>
    ${PLATFORM_TYPES.includes(p.type) && html`<${Field} label="المنصات المستهدفة" optional hint="يكتشفها النظام أيضًا من الوصف إن لم تحددها.">
      <${Chips} options=${(meta?.platforms || []).map((x) => ({ value: x.key, label: x.label }))} value=${p.platforms || []} onChange=${(v) => set('project', 'platforms', v)} />
    </${Field}>`}
    ${EVENT_TYPES.includes(p.type) && html`<div class="row">
      <${Field} label=${p.type === 'exhibition' ? 'تاريخ افتتاح المعرض' : 'تاريخ الفعالية'} optional><input class="input" type="date" value=${p.event_date} onInput=${(e) => set('project', 'event_date', e.target.value)} /></${Field}>
      <${Field} label="الموقع / المدينة" optional><${Input} value=${p.location} onInput=${(v) => set('project', 'location', v)} placeholder="مثال: الرياض" /></${Field}>
    </div>`}
    ${!EVENT_TYPES.includes(p.type) && html`<${Field} label="المدينة أو النطاق الجغرافي" optional><${Input} value=${p.location} onInput=${(v) => set('project', 'location', v)} placeholder="مثال: الرياض وجدة" /></${Field}>`}
  </div>`;
}

function StepScope({ data, set }) {
  return html`<div class="stack">
    <${Field} label="نطاق العمل" hint="ما الذي سيشمله العمل تحديدًا؟ يُستخدم في قسم «نطاق العمل».">
      <${TextArea} value=${data.scope.description} onInput=${(v) => set('scope', 'description', v)} minRows=${4} placeholder="مثال: إدارة الحساب يوميًا، وإنتاج الفيديوهات القصيرة، والرد على التعليقات، والتقارير الشهرية." />
    </${Field}>
    <${Field} label="خارج نطاق العمل" optional hint="سطر لكل بند. يظهر كقائمة واضحة لتجنب سوء الفهم لاحقًا.">
      <${TextArea} value=${data.scope.out_of_scope} onInput=${(v) => set('scope', 'out_of_scope', v)} minRows=${2} placeholder="مثال: ميزانية الإعلانات الممولة" />
    </${Field}>
    <${Field} label="متطلبات خاصة من العميل" optional hint="تظهر في العرض تحت «متطلبات خاصة أكد عليها العميل». سطر لكل متطلب.">
      <${TextArea} value=${data.preferences.requirements} onInput=${(v) => set('preferences', 'requirements', v)} minRows=${2} placeholder="مثال: تسليم المحتوى قبل رمضان بأسبوعين" />
    </${Field}>
    <${Field} label="ملاحظات داخلية" optional hint="للفريق فقط، لا تظهر في العرض.">
      <${TextArea} value=${data.preferences.notes} onInput=${(v) => set('preferences', 'notes', v)} minRows=${2} />
    </${Field}>
  </div>`;
}

function StepServices({ data, set, meta, lib, suggest, typeMeta }) {
  const selected = data.services.selected || [];
  const toggle = (k) => set('services', 'selected', selected.includes(k) ? selected.filter((x) => x !== k) : [...selected, k]);
  const groups = (meta?.categories || []).map((c) => ({ ...c, items: lib.services.filter((s) => (s.data?.category || 'pm') === c.key) })).filter((g) => g.items.length);
  const custom = data.services.custom || [];
  const setCustom = (arr) => set('services', 'custom', arr);
  return html`<div class="stack">
    <div class="notice info"><${Icon} name="info" /><div>اختر الخدمات المطلوبة. كل خدمة تضيف مخرجاتها وأنشطتها ومؤشراتها والأدوار اللازمة لها إلى العرض تلقائيًا.
      ${typeMeta && html` <button class="btn soft sm" style="margin-inline-start:6px" onClick=${suggest}><${Icon} name="wand" size=${15} />اقتراح خدمات «${typeMeta.label}»</button>`}</div></div>
    <div class="svc-groups">${groups.map((g) => html`<div class="svc-group"><h4><${Icon} name=${g.icon} size=${17} />${g.label}</h4>
      ${g.items.map((s) => html`<label class="check"><input type="checkbox" checked=${selected.includes(s.key)} onChange=${() => toggle(s.key)} /><span>${s.title}<small>${s.data?.description || ''}</small></span></label>`)}</div>`)}</div>
    <div class="field"><span class="lbl">خدمات مخصصة <span class="opt">(اختياري)</span></span>
      <div class="rep">${custom.map((c, i) => html`<div class="rep-item"><div class="rh"><span>خدمة مخصصة ${i + 1}</span><span class="grow"></span><button class="btn ghost icon sm" aria-label="حذف" onClick=${() => setCustom(custom.filter((_, j) => j !== i))}><${Icon} name="trash" size=${16} /></button></div>
        <div class="row"><${Input} value=${c.title} placeholder="اسم الخدمة" onInput=${(v) => setCustom(custom.map((x, j) => (j === i ? { ...x, title: v } : x)))} /><${Input} value=${c.description} placeholder="وصف مختصر" onInput=${(v) => setCustom(custom.map((x, j) => (j === i ? { ...x, description: v } : x)))} /></div></div>`)}
        <div><${Btn} kind="soft" size="sm" icon="plus" onClick=${() => setCustom([...custom, { title: '', description: '' }])}>إضافة خدمة مخصصة</${Btn}></div></div>
    </div>
    <p class="muted" style="font-size:13px">${selected.length ? `${selected.length} خدمة مختارة` : 'إن لم تختر أي خدمة، سيقترح النظام الخدمات المعتادة لنوع المشروع.'}</p>
  </div>`;
}

function StepTimeline({ data, set, typeMeta }) {
  const t = data.timeline;
  const unitDays = { day: 1, week: 7, month: 30.4 };
  const start = parseISO(t.start_date);
  const days = t.duration_value ? Math.round(Number(t.duration_value) * unitDays[t.duration_unit || 'month']) : 0;
  const computedEnd = start && days ? addDays(start, days - 1) : null;
  const setEnd = (iso) => {
    set('timeline', 'end_date', iso);
    const e = parseISO(iso);
    if (start && e && e > start) {
      const d = Math.round((e - start) / 86400000) + 1;
      if (d % 7 === 0 && d < 70) { set('timeline', 'duration_value', d / 7); set('timeline', 'duration_unit', 'week'); }
      else if (d >= 56) { set('timeline', 'duration_value', Math.round(d / 30.4)); set('timeline', 'duration_unit', 'month'); }
      else { set('timeline', 'duration_value', d); set('timeline', 'duration_unit', 'day'); }
    }
  };
  return html`<div class="stack">
    <div class="row">
      <${Field} label="مدة المشروع" hint=${typeMeta ? `إن تُركت فارغة تُستخدم مدة افتراضية مناسبة لـ«${typeMeta.label}» ويُنبَّه إليها.` : ''}>
        <div class="inline" style="flex-wrap:nowrap"><input class="input" type="number" min="1" style="max-width:120px" value=${t.duration_value} onInput=${(e) => { set('timeline', 'duration_value', e.target.value); set('timeline', 'end_date', ''); }} placeholder="6" />
        <${Seg} value=${t.duration_unit || 'month'} onChange=${(v) => { set('timeline', 'duration_unit', v); set('timeline', 'end_date', ''); }} options=${[{ value: 'day', label: 'يوم' }, { value: 'week', label: 'أسبوع' }, { value: 'month', label: 'شهر' }]} /></div>
      </${Field}>
      <${Field} label="عدد أعضاء الفريق" optional hint="يُبنى الفريق المقترح على هذا العدد وعلى الخدمات المختارة.">
        <input class="input" type="number" min="1" max="30" value=${t.team_size} onInput=${(e) => set('timeline', 'team_size', e.target.value)} placeholder="مثال: 5" />
      </${Field}>
    </div>
    <div class="row">
      <${Field} label="تاريخ البداية" optional hint="بدونه يُعرض الجدول الزمني بالأسابيع."><input class="input" type="date" value=${t.start_date} onInput=${(e) => set('timeline', 'start_date', e.target.value)} /></${Field}>
      <${Field} label="تاريخ النهاية" optional hint=${computedEnd && !t.end_date ? `محسوب تلقائيًا: ${fmtDate(computedEnd)}` : 'يُحسب من المدة، أو حدده لتُحسب المدة منه.'}>
        <input class="input" type="date" value=${t.end_date || (computedEnd ? toISO(computedEnd) : '')} onInput=${(e) => setEnd(e.target.value)} />
      </${Field}>
    </div>
  </div>`;
}

function StepGoals({ data, set }) {
  const g = data.goals;
  return html`<div class="stack">
    <${Field} label="أهداف المشروع" hint="سطر لكل هدف. أي رقم تكتبه (مثل 30%) يصبح القيمة المستهدفة للمؤشر؛ وبدون أرقام يُكتب «يُحدد بعد قياس خط الأساس».">
      <${TextArea} value=${g.objectives} onInput=${(v) => set('goals', 'objectives', v)} minRows=${4} placeholder=${'رفع الوعي بالعلامة في الرياض\nزيادة الحجوزات من المنصات الرقمية\nنمو المتابعين 30%'} />
    </${Field}>
    <${Field} label="المخرجات المطلوبة" optional hint="سطر لكل مخرج مع الكمية إن وُجدت، مثل «12 فيديو شهريًا». تُضاف مخرجات الخدمات المختارة تلقائيًا، والكميات قابلة للتعديل لاحقًا.">
      <${TextArea} value=${g.deliverables} onInput=${(v) => set('goals', 'deliverables', v)} minRows=${3} placeholder=${'12 فيديو شهريًا\n20 قصة شهريًا'} />
    </${Field}>
    <${Field} label="قيم مستهدفة معروفة لمؤشرات الأداء" optional hint="بصيغة «المؤشر: القيمة»، مثل «معدل التفاعل: 5%». اتركه فارغًا إن لم تُتفق بعد.">
      <${TextArea} value=${g.kpi_targets} onInput=${(v) => set('goals', 'kpi_targets', v)} minRows=${2} />
    </${Field}>
    <div class="row">
      <${Field} label="الميزانية" optional hint="لا تظهر في العرض إلا إذا فعّلت الخيار.">
        <${Input} value=${g.budget} onInput=${(v) => set('goals', 'budget', v)} placeholder="مثال: 250,000 ريال" />
      </${Field}>
      <div class="field" style="justify-content:flex-end"><${Switch} checked=${g.show_budget} onChange=${(v) => set('goals', 'show_budget', v)} label="إظهار الميزانية في العرض (قسم الإطار المالي)" /></div>
    </div>
  </div>`;
}

function StepPrefs({ data, set, meta, lib, analysis, goTo }) {
  const p = data.preferences;
  const missing = analysis?.missing || [];
  const a = analysis?.analysis;
  return html`<div class="stack">
    <div class="field"><span class="lbl">أسلوب العرض</span>
      <div class="tone-grid">${(meta?.tones || []).map((t) => html`<button type="button" class=${`tone-opt ${p.tone === t.key ? 'on' : ''}`} aria-pressed=${p.tone === t.key} onClick=${() => set('preferences', 'tone', t.key)}><b>${t.label}</b><span>${TONE_HINT[t.key]}</span></button>`)}</div></div>
    <div class="row">
      <div class="field"><span class="lbl">مستوى التفصيل</span><${Seg} value=${p.detail} onChange=${(v) => set('preferences', 'detail', v)} options=${(meta?.details || []).map((d) => ({ value: d.key, label: d.label }))} /></div>
      <div class="field"><span class="lbl">شكل الصفحات</span><${Seg} value=${p.layout} onChange=${(v) => set('preferences', 'layout', v)} options=${[{ value: 'landscape', label: 'أفقي 16:9 (عروض أهداف)' }, { value: 'portrait', label: 'مستند A4 عمودي' }]} /></div>
    </div>
    <div class="row">
      <${Field} label="المقدمة"><${Select} value=${p.intro_template} onChange=${(v) => set('preferences', 'intro_template', v)} options=${[{ value: 'auto', label: 'تُكتب تلقائيًا حسب المشروع (موصى به)' }, ...lib.intro.map((t) => ({ value: t.id, label: `قالب: ${t.title}` }))]} /></${Field}>
      <${Field} label="الخاتمة"><${Select} value=${p.conclusion_template} onChange=${(v) => set('preferences', 'conclusion_template', v)} options=${[{ value: 'auto', label: 'تُكتب تلقائيًا حسب المشروع (موصى به)' }, ...lib.conclusion.map((t) => ({ value: t.id, label: `قالب: ${t.title}` }))]} /></${Field}>
    </div>
    <div class="inline" style="gap:22px">
      <${Switch} checked=${p.include_about} onChange=${(v) => set('preferences', 'include_about', v)} label="تضمين «عن أهداف»" />
      <${Switch} checked=${p.dividers} onChange=${(v) => set('preferences', 'dividers', v)} label="صفحات فاصلة بين الأقسام الرئيسية" />
      <${Switch} checked=${p.include_past_projects} onChange=${(v) => set('preferences', 'include_past_projects', v)} label="أعمال سابقة ذات صلة من المكتبة" />
    </div>
    <div class="row" style="--n:3"><${Field} label="نسخة العرض"><${Input} value=${p.version} onInput=${(v) => set('preferences', 'version', v)} /></${Field}></div>

    <div class="card-ui pad" style="background:#FCFBFE">
      <h3 style="font-size:16px">ما فهمه النظام من المدخلات</h3>
      ${!analysis ? html`<div class="skeleton" style="height:60px;margin-top:10px"></div>` : html`
        <div class="analysis" style="margin-top:12px">
          <div><span>نوع المشروع</span><b>${a.type}</b></div><div><span>القطاع</span><b>${a.sector}</b></div>
          <div><span>المدة</span><b>${a.duration}</b></div><div><span>المنصات</span><b>${a.platforms.length ? a.platforms.join('، ') : '—'}</b></div>
          <div><span>الأهداف</span><b>${a.objectives.length} ${analysis.objectives_suggested ? '(مقترحة)' : ''}</b></div><div><span>الخدمات</span><b>${analysis.service_labels.length}</b></div>
        </div>
        ${missing.length ? html`<div class="notice warn" style="margin-top:14px"><${Icon} name="alert" /><div><b>معلومات لم تُدخل (لن يخترعها النظام):</b>
          <div class="missing-list">${missing.map((m) => html`<div><b>${m.label}:</b><span>${m.hint}</span>${m.step && html`<button class="btn ghost sm" style="padding:0 6px" onClick=${() => goTo(m.step - 1)}>إكمال</button>`}</div>`)}</div></div></div>`
          : html`<div class="notice ok" style="margin-top:14px"><${Icon} name="check" />كل المعلومات الأساسية مكتملة.</div>`}`}
    </div>
  </div>`;
}
