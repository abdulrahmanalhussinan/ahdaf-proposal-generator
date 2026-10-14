// New proposal: three short steps. The user gives the essentials; the system proposes the rest
// (idea, audience, objectives, services, timeline...) and everything stays editable afterwards.
import { html, useEffect, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { navigate, toast, toastError, useStore, confirmDialog } from '../lib/store.js';
import { Btn, Icon, Field, Input, TextArea, Select, Seg, ImagePicker, setTitle, Spinner } from '../components/ui.js';
import { DesignPicker, DESIGN_KEYS } from '../components/designs.js';
import { REUSE_KEY } from './actions.js';

const DRAFT_KEY = 'ahdaf.wizard.draft.v2';
const STEPS = [
  { title: 'التصميم', desc: 'اختر شكل العرض الفني. تقدر تغيّره لاحقًا من المحرر.' },
  { title: 'المشروع', desc: 'المعلومات الأساسية فقط، والنظام يكمل الباقي.' },
  { title: 'اقتراحاتك', desc: 'كلها اختيارية: ما تتركه يقترحه النظام بنفسه.' },
];
const PLATFORM_TYPES = ['social_media', 'content', 'influencer', 'digital_ads', 'campaign'];
const EVENT_TYPES = ['event', 'exhibition'];
const DURATIONS = [
  { value: '2w', label: 'أسبوعان', v: 2, u: 'week' }, { value: '1m', label: 'شهر', v: 1, u: 'month' },
  { value: '2m', label: 'شهران', v: 2, u: 'month' }, { value: '3m', label: '3 أشهر', v: 3, u: 'month' },
  { value: '6m', label: '6 أشهر', v: 6, u: 'month' }, { value: '12m', label: 'سنة', v: 12, u: 'month' },
];

const empty = () => ({
  client: { name: '', sector: '', logo: null },
  project: { name: '', type: '', type_other: '', description: '', audience: [], audience_other: '', platforms: [], platforms_other: '', event_date: '' },
  services: { selected: [], other: '' },
  timeline: { duration_value: '', duration_unit: 'month', start_date: '' },
  goals: { objective_keys: [], objectives: '' },
  preferences: { design: 'ahdaf', tone: 'corporate', tone_other: '', detail: 'medium', layout: 'landscape', include_about: true, dividers: true, requirements: '' },
});

function merge(base, extra) {
  const out = { ...base };
  for (const k of Object.keys(extra || {})) {
    out[k] = typeof base[k] === 'object' && base[k] && !Array.isArray(base[k]) ? { ...base[k], ...(extra[k] || {}) } : extra[k];
  }
  // older proposals stored the audience as free text
  if (typeof out.project.audience === 'string') {
    out.project.audience_other = [out.project.audience_other, out.project.audience].filter(Boolean).join('، ');
    out.project.audience = [];
  }
  return out;
}

// Chips with a trailing «أخرى» that opens a free-text field
function ChipsOther({ options, value, onChange, other, onOther, multi = true, placeholder = 'اكتب ما تريد…' }) {
  const [open, setOpen] = useState(!!other);
  const sel = multi ? (value || []) : value;
  const isOn = (k) => (multi ? sel.includes(k) : sel === k);
  const toggle = (k) => {
    if (!multi) { onChange(sel === k ? '' : k); if (sel !== k) { setOpen(false); onOther && onOther(''); } return; }
    onChange(sel.includes(k) ? sel.filter((x) => x !== k) : [...sel, k]);
  };
  return html`<div class="stack" style="gap:8px">
    <div class="chips">
      ${options.map((o) => html`<button type="button" class=${`chip ${isOn(o.value) ? 'on' : ''}`} aria-pressed=${isOn(o.value)} onClick=${() => toggle(o.value)}>${isOn(o.value) && multi ? html`<${Icon} name="check" size=${14} />` : null}${o.label}</button>`)}
      <button type="button" class=${`chip ${open ? 'on' : ''}`} aria-pressed=${open} onClick=${() => { const n = !open; setOpen(n); if (!n) onOther(''); if (n && !multi) onChange(''); }}><${Icon} name=${open ? 'check' : 'plus'} size=${14} />أخرى</button>
    </div>
    ${open && html`<input class="input" value=${other || ''} placeholder=${placeholder} onInput=${(e) => onOther(e.target.value)} />`}
  </div>`;
}

export function Wizard({ params, query }) {
  const meta = useStore((s) => s.meta);
  const editId = params.id || null;
  const [data, setData] = useState(null);
  const [step, setStep] = useState(0);
  const [lib, setLib] = useState({ services: [], sectors: [], clients: [] });
  const [errors, setErrors] = useState({});
  const [gen, setGen] = useState(null);
  const [origin, setOrigin] = useState('');

  useEffect(() => {
    setTitle(editId ? 'تعديل مدخلات العرض' : 'إنشاء عرض جديد');
    (async () => {
      try {
        const [svc, sec, clients, settings] = await Promise.all([
          api.get('/api/library/services'), api.get('/api/library/sectors'), api.get('/api/clients'), api.get('/api/settings')]);
        setLib({ services: svc.items.filter((s) => s.active), sectors: sec.items.filter((s) => s.active), clients: clients.items });
        const base = empty();
        const sv = settings.values || {};
        base.preferences = { ...base.preferences, tone: sv.default_tone || 'corporate', detail: sv.default_detail || 'medium', layout: sv.default_layout || 'landscape' };
        let initial = base;
        if (editId) {
          const p = await api.get(`/api/proposals/${editId}`);
          initial = merge(base, p.inputs);
          if (!initial.preferences.design) initial.preferences.design = p.doc?.theme || 'ahdaf';
          setOrigin(`تعديل مدخلات: ${p.project_name}`);
          setStep(1);
        } else if (query.get('reuse')) {
          try {
            const saved = JSON.parse(sessionStorage.getItem(REUSE_KEY) || 'null');
            if (saved) { initial = merge(base, saved.inputs); setOrigin(`إعادة استخدام: ${saved.from}`); sessionStorage.removeItem(REUSE_KEY); }
          } catch { /* ignore */ }
        } else if (query.get('client')) {
          const c = clients.items.find((x) => x.id === query.get('client'));
          if (c) initial = merge(base, { client: { id: c.id, name: c.name, sector: c.sector || '', logo: c.logo } });
        } else {
          try {
            const draft = JSON.parse(localStorage.getItem(DRAFT_KEY) || 'null');
            if (draft && draft.client && (draft.client.name || draft.project?.name)) { initial = merge(base, draft); setOrigin('استُكملت المسودة غير المكتملة'); }
          } catch { /* ignore */ }
        }
        if (query.get('design') && DESIGN_KEYS.includes(query.get('design'))) {
          initial.preferences = { ...initial.preferences, design: query.get('design') };
          if (!editId) setStep(1);
        }
        setData(initial);
      } catch (e) { toastError(e); }
    })();
  }, [editId]);

  useEffect(() => {
    if (!data || editId) return;
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(data)); } catch { /* storage unavailable */ }
  }, [data]);

  if (!data) return html`<div class="content" style="display:grid;place-items:center;min-height:50vh"><${Spinner} /></div>`;

  const set = (group, key, value) => setData((d) => ({ ...d, [group]: { ...d[group], [key]: value } }));
  const validate = () => {
    const e = {};
    if (!data.client.name.trim()) e.client = 'اكتب اسم العميل';
    if (!data.project.name.trim()) e.project = 'اكتب اسم المشروع';
    if (!data.project.type) e.type = 'اختر نوع المشروع';
    if (data.project.type === 'other' && !data.project.type_other.trim()) e.type = 'اكتب نوع المشروع';
    setErrors(e);
    return Object.keys(e).length === 0;
  };
  const go = (i) => {
    if (i === 2 && step < 2 && !validate()) { setStep(1); return; }
    setStep(i);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const generate = async () => {
    if (!validate()) { setStep(1); return; }
    if (editId) {
      const ok = await confirmDialog({ title: 'إعادة توليد العرض', confirmLabel: 'إعادة التوليد',
        message: 'سيُعاد توليد العرض بالمدخلات الجديدة، وتُحفظ النسخة الحالية في سجل النسخ لتتمكن من استرجاعها.' });
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
    if (!(await confirmDialog({ title: 'البدء من جديد', message: 'ستُمسح المدخلات الحالية في هذا النموذج.', confirmLabel: 'مسح المدخلات', danger: true }))) return;
    try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
    setData(empty()); setStep(0); setOrigin('');
  };

  const progress = Math.round(((step + 1) / STEPS.length) * 100);
  const S = STEPS[step];
  return html`<div class="content">
    <div class="page-head"><div><h1>${editId ? 'تعديل مدخلات العرض' : 'إنشاء عرض فني جديد'}</h1><p>${origin || 'ثلاث خطوات قصيرة. أعطنا الأساسيات، والنظام يقترح الفكرة والأهداف والجمهور والخطة كاملة.'}</p></div>
      <div class="actions">${!editId && html`<${Btn} kind="ghost" icon="refresh" onClick=${reset}>البدء من جديد</${Btn}>`}</div></div>
    <div class="wiz">
      <aside class="card-ui wiz-steps" aria-label="خطوات الإنشاء">
        <div class="inline" style="justify-content:space-between;font-size:13px"><b style="color:var(--night)">الخطوة ${step + 1} من ${STEPS.length}</b><span class="muted">${progress}%</span></div>
        <div class="wiz-progress" role="progressbar" aria-valuenow=${progress} aria-valuemin="0" aria-valuemax="100"><i style=${`width:${progress}%`}></i></div>
        <ol>${STEPS.map((s, i) => html`<li class=${i === step ? 'on' : i < step ? 'done' : ''}><button onClick=${() => go(i)} aria-current=${i === step ? 'step' : null}><span class="n">${i < step ? html`<${Icon} name="check" size=${14} />` : i + 1}</span>${s.title}</button></li>`)}</ol>
      </aside>
      <section class="card-ui wiz-card">
        <div class="step-h"><div><div class="k">الخطوة ${step + 1}</div><h2>${S.title}</h2><p>${S.desc}</p></div></div>
        ${step === 0 && html`<${DesignPicker} value=${data.preferences.design} onChange=${(k) => set('preferences', 'design', k)} />`}
        ${step === 1 && html`<${StepProject} data=${data} set=${set} meta=${meta} lib=${lib} errors=${errors} setData=${setData} />`}
        ${step === 2 && html`<${StepSuggest} data=${data} set=${set} meta=${meta} lib=${lib} />`}
        <div class="wiz-nav">
          ${step > 0 && html`<${Btn} kind="light" icon="chevronRight" onClick=${() => go(step - 1)}>السابق</${Btn}>`}
          <span class="spacer"></span>
          ${step === 1 && html`<${Btn} kind="ghost" icon="wand" onClick=${generate}>ولّد الآن بالاقتراحات التلقائية</${Btn}>`}
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
  const steps = ['قراءة المشروع والقطاع', 'ابتكار الفكرة والرسالة', 'اقتراح الأفكار التفعيلية والمحتوى', 'بناء المنهجية والجدول والفريق', 'تنسيق الصفحات بالتصميم المختار'];
  return html`<div class="gen-overlay" role="alert" aria-busy="true"><div class="gen-box">
    <div class="gen-stairs" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
    <h2>نجهّز العرض الفني</h2><p>نقرأ المشروع ونقترح الفكرة والخطة كاملة.</p>
    <ul class="gen-steps">${steps.map((s, i) => html`<li class=${i < stage ? 'done' : i === stage ? 'now' : ''}><span class="s">${i < stage ? html`<${Icon} name="check" size=${13} />` : ''}</span>${s}</li>`)}</ul>
  </div></div>`;
}

function StepProject({ data, set, meta, lib, errors, setData }) {
  const c = data.client;
  const p = data.project;
  const known = lib.sectors.some((s) => s.key === c.sector);
  const [customSector, setCustomSector] = useState(!!c.sector && !known);
  const pickClient = (name) => {
    const found = lib.clients.find((x) => x.name === name);
    setData((d) => ({ ...d, client: found ? { ...d.client, id: found.id, name: found.name, sector: found.sector || d.client.sector, logo: found.logo || d.client.logo } : { ...d.client, id: undefined, name } }));
  };
  const types = [...(meta?.project_types || []).filter((t) => t.key !== 'other')];
  return html`<div class="stack">
    <div class="row">
      <${Field} label="اسم العميل" required id="c-name" error=${errors.client}>
        <input id="c-name" class=${`input ${errors.client ? 'invalid' : ''}`} list="clients-list" value=${c.name} onInput=${(e) => set('client', 'name', e.target.value)} onChange=${(e) => pickClient(e.target.value)} placeholder="مثال: شركة … للتطوير العقاري" />
        <datalist id="clients-list">${lib.clients.map((x) => html`<option value=${x.name} />`)}</datalist>
      </${Field}>
      <${Field} label="القطاع" id="c-sector" hint="إن تركته، يستنتجه النظام من اسم المشروع ووصفه.">
        ${customSector
          ? html`<div class="inline" style="flex-wrap:nowrap"><input id="c-sector" class="input" value=${c.sector} onInput=${(e) => set('client', 'sector', e.target.value)} placeholder="اكتب القطاع" /><${Btn} kind="ghost" size="sm" onClick=${() => { setCustomSector(false); set('client', 'sector', ''); }}>القائمة</${Btn}></div>`
          : html`<${Select} id="c-sector" value=${c.sector} placeholder="اختر القطاع" options=${[...lib.sectors.filter((s) => s.key !== 'general').map((s) => ({ value: s.key, label: s.title })), { value: '__other', label: 'أخرى…' }]}
              onChange=${(v) => { if (v === '__other') { setCustomSector(true); set('client', 'sector', ''); } else set('client', 'sector', v); }} />`}
      </${Field}>
    </div>
    <${Field} label="اسم المشروع" required id="p-name" error=${errors.project}>
      <input id="p-name" class=${`input ${errors.project ? 'invalid' : ''}`} value=${p.name} onInput=${(e) => set('project', 'name', e.target.value)} placeholder="مثال: إدارة حساب تيك توك، حفل تدشين، حملة رمضان…" />
    </${Field}>
    <div class="field"><span class="lbl">نوع المشروع<span class="req">*</span></span>
      <div class="type-grid" role="radiogroup">
        ${types.map((t) => html`<button type="button" role="radio" aria-checked=${p.type === t.key} class=${`type-opt ${p.type === t.key ? 'on' : ''}`} onClick=${() => set('project', 'type', t.key)}><span class="ti"><${Icon} name=${t.icon} /></span>${t.label}</button>`)}
        <button type="button" role="radio" aria-checked=${p.type === 'other'} class=${`type-opt ${p.type === 'other' ? 'on' : ''}`} onClick=${() => set('project', 'type', 'other')}><span class="ti"><${Icon} name="plus" /></span>أخرى</button>
      </div>
      ${p.type === 'other' && html`<input class="input" style="margin-top:8px" value=${p.type_other} onInput=${(e) => set('project', 'type_other', e.target.value)} placeholder="اكتب نوع المشروع، مثل: رحلة تعريفية للإعلاميين" />`}
      ${errors.type && html`<span class="err">${errors.type}</span>`}
    </div>
    <${Field} label="وصف مختصر" optional hint="سطر أو سطران يكفيان. النظام يقترح الفكرة والأهداف والجمهور والخطة.">
      <${TextArea} value=${p.description} onInput=${(v) => set('project', 'description', v)} minRows=${2} placeholder="مثال: نبي نرفع حضور الشركة على تيك توك ونزيد الحجوزات." />
    </${Field}>
    <${Field} label="شعار العميل" optional><${ImagePicker} value=${c.logo} onChange=${(v) => set('client', 'logo', v)} onUpload=${api.upload} label="رفع الشعار" /></${Field}>
  </div>`;
}

function StepSuggest({ data, set, meta, lib }) {
  const p = data.project;
  const sectorKey = data.client.sector;
  const segments = (meta?.segments || {})[sectorKey] || (meta?.segments || {}).general || [];
  const defaultsObj = (meta?.default_objectives || {})[p.type] || [];
  const objOptions = [...(meta?.objectives || [])].sort((a, b) => (defaultsObj.includes(b.key) ? 1 : 0) - (defaultsObj.includes(a.key) ? 1 : 0)).slice(0, 10);
  const typeMeta = (meta?.project_types || []).find((t) => t.key === p.type);
  const relevant = lib.services.filter((s) => {
    const types = s.data?.types || [];
    return types.includes('*') || types.includes(p.type) || (typeMeta?.default_services || []).includes(s.key);
  });
  const t = data.timeline;
  const durKey = (DURATIONS.find((d) => String(d.v) === String(t.duration_value) && d.u === t.duration_unit) || {}).value || '';
  const [customDur, setCustomDur] = useState(!!t.duration_value && !durKey);
  const pr = data.preferences;
  return html`<div class="stack" style="gap:20px">
    <div class="notice info"><${Icon} name="wand" /><span>كل ما في هذه الخطوة اختياري. ما تتركه فارغًا يقترحه النظام بنفسه، وكل شيء قابل للتعديل بعد التوليد.</span></div>
    <${Field} label="الجمهور المستهدف">
      <${ChipsOther} options=${segments.map((s) => ({ value: s, label: s }))} value=${p.audience || []} onChange=${(v) => set('project', 'audience', v)}
        other=${p.audience_other} onOther=${(v) => set('project', 'audience_other', v)} placeholder="اكتب شريحة أخرى" />
    </${Field}>
    <${Field} label="الأهداف" hint="اكتب رقمًا في «أخرى» إن كان عندك هدف رقمي، مثل: نمو المتابعين 30%.">
      <${ChipsOther} options=${objOptions.map((o) => ({ value: o.key, label: o.label }))} value=${data.goals.objective_keys || []} onChange=${(v) => set('goals', 'objective_keys', v)}
        other=${data.goals.objectives} onOther=${(v) => set('goals', 'objectives', v)} placeholder="هدف آخر" />
    </${Field}>
    ${PLATFORM_TYPES.includes(p.type) && html`<${Field} label="المنصات">
      <${ChipsOther} options=${(meta?.platforms || []).map((x) => ({ value: x.key, label: x.label }))} value=${p.platforms || []} onChange=${(v) => set('project', 'platforms', v)}
        other=${p.platforms_other} onOther=${(v) => set('project', 'platforms_other', v)} placeholder="منصة أخرى" />
    </${Field}>`}
    <${Field} label="الخدمات" hint="إن لم تختر، يقترح النظام الخدمات المناسبة لنوع المشروع.">
      <${ChipsOther} options=${relevant.map((s) => ({ value: s.key, label: s.title }))} value=${data.services.selected || []} onChange=${(v) => set('services', 'selected', v)}
        other=${data.services.other} onOther=${(v) => set('services', 'other', v)} placeholder="خدمة أخرى" />
    </${Field}>
    <div class="row">
      <div class="field"><span class="lbl">المدة</span>
        <div class="chips">${DURATIONS.map((d) => html`<button type="button" class=${`chip ${!customDur && durKey === d.value ? 'on' : ''}`} onClick=${() => { setCustomDur(false); set('timeline', 'duration_value', durKey === d.value ? '' : d.v); set('timeline', 'duration_unit', d.u); }}>${d.label}</button>`)}
          <button type="button" class=${`chip ${customDur ? 'on' : ''}`} onClick=${() => setCustomDur(!customDur)}><${Icon} name=${customDur ? 'check' : 'plus'} size=${14} />أخرى</button></div>
        ${customDur && html`<div class="inline" style="flex-wrap:nowrap;margin-top:8px"><input class="input" type="number" min="1" style="max-width:110px" value=${t.duration_value} onInput=${(e) => set('timeline', 'duration_value', e.target.value)} />
          <${Seg} value=${t.duration_unit || 'month'} onChange=${(v) => set('timeline', 'duration_unit', v)} options=${[{ value: 'day', label: 'يوم' }, { value: 'week', label: 'أسبوع' }, { value: 'month', label: 'شهر' }]} /></div>`}
      </div>
      <${Field} label=${EVENT_TYPES.includes(p.type) ? 'تاريخ البداية / تاريخ الفعالية' : 'تاريخ البداية'} optional>
        <div class="inline" style="flex-wrap:nowrap"><input class="input" type="date" value=${t.start_date} onInput=${(e) => set('timeline', 'start_date', e.target.value)} aria-label="تاريخ البداية" />
        ${EVENT_TYPES.includes(p.type) && html`<input class="input" type="date" value=${p.event_date} onInput=${(e) => set('project', 'event_date', e.target.value)} aria-label="تاريخ الفعالية" />`}</div>
      </${Field}>
    </div>
    <div class="row">
      <${Field} label="أسلوب الكتابة">
        <${ChipsOther} multi=${false} options=${(meta?.tones || []).map((x) => ({ value: x.key, label: x.label }))} value=${pr.tone_other ? '' : pr.tone}
          onChange=${(v) => set('preferences', 'tone', v || 'corporate')} other=${pr.tone_other} onOther=${(v) => set('preferences', 'tone_other', v)} placeholder="صف الأسلوب الذي تريده" />
      </${Field}>
      <div class="field"><span class="lbl">مستوى التفصيل</span><${Seg} value=${pr.detail} onChange=${(v) => set('preferences', 'detail', v)} options=${(meta?.details || []).map((d) => ({ value: d.key, label: d.label }))} /></div>
    </div>
    <${Field} label="ملاحظات أخرى" optional hint="أي شيء تريد أن يراعيه العرض، يظهر ضمن «فهمنا للمشروع».">
      <${TextArea} value=${pr.requirements} onInput=${(v) => set('preferences', 'requirements', v)} minRows=${2} placeholder="مثال: التسليم قبل رمضان، التركيز على مدينة الرياض…" />
    </${Field}>
  </div>`;
}
