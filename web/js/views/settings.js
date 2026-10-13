import { html, useEffect, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { toast, toastError, useStore } from '../lib/store.js';
import { Btn, Icon, Input, TextArea, Select, Seg, Spinner, setTitle } from '../components/ui.js';

export function Settings() {
  const meta = useStore((s) => s.meta);
  const [v, setV] = useState(null);
  const [ai, setAi] = useState(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setTitle('الإعدادات'); api.get('/api/settings').then((r) => { setV(r.values); setAi(r.ai); }).catch(toastError); }, []);
  if (!v) return html`<div class="content"><${Spinner} /></div>`;
  const set = (k, val) => setV({ ...v, [k]: val });
  const save = async () => {
    setSaving(true);
    try { const r = await api.put('/api/settings', { values: v }); setV(r.values); toast('تم حفظ الإعدادات'); } catch (e) { toastError(e); } finally { setSaving(false); }
  };
  const list = (k) => v[k] || [];
  const setItem = (k, i, patch) => set(k, list(k).map((x, j) => (j === i ? { ...x, ...patch } : x)));

  return html`<div class="content">
    <div class="page-head"><div><h1>الإعدادات</h1><p>بيانات الشركة التي تظهر في العروض، والإعدادات الافتراضية للعروض الجديدة.</p></div>
      <div class="actions"><${Btn} kind="primary" icon="check" disabled=${saving} onClick=${save}>${saving ? 'جارٍ الحفظ…' : 'حفظ الإعدادات'}</${Btn}></div></div>
    <div class="stack" style="gap:18px">
      <section class="card-ui pad stack"><h3>هوية الشركة</h3>
        <div class="row"><div class="field"><span class="lbl">اسم الشركة (يظهر في «مقدم من»)</span><${Input} value=${v.company_name} onInput=${(x) => set('company_name', x)} /></div>
          <div class="field"><span class="lbl">الاسم بالإنجليزية</span><input class="input ltr" value=${v.company_name_en || ''} onInput=${(e) => set('company_name_en', e.target.value)} /></div></div>
        <div class="row"><div class="field"><span class="lbl">الشعار اللفظي</span><${Input} value=${v.tagline} onInput=${(x) => set('tagline', x)} /></div>
          <div class="field"><span class="lbl">الموقع</span><input class="input ltr" value=${v.website || ''} onInput=${(e) => set('website', e.target.value)} /></div></div>
        <div class="row" style="--n:3"><div class="field"><span class="lbl">البريد</span><input class="input ltr" value=${v.email || ''} onInput=${(e) => set('email', e.target.value)} /></div>
          <div class="field"><span class="lbl">الهاتف</span><input class="input ltr" value=${v.phone || ''} onInput=${(e) => set('phone', e.target.value)} /></div>
          <div class="field"><span class="lbl">العنوان</span><${Input} value=${v.address} onInput=${(x) => set('address', x)} /></div></div>
      </section>
      <section class="card-ui pad stack"><h3>قسم «عن أهداف»</h3>
        <p class="sub">يظهر في بداية العروض عند تفعيله. النصوص الحالية منقولة من عرض أهداف الرسمي (متجر شادن – نسخة 4)؛ حدّثها عند تغير الأرقام.</p>
        <div class="field"><span class="lbl">النبذة</span><${TextArea} minRows=${2} value=${v.company_about} onInput=${(x) => set('company_about', x)} /></div>
        <div class="field"><span class="lbl">الأرقام</span><div class="rep">${list('company_stats').map((s, i) => html`<div class="inline" style="flex-wrap:nowrap">
          <input class="input ltr" style="max-width:140px" value=${s.value} onInput=${(e) => setItem('company_stats', i, { value: e.target.value })} /><${Input} value=${s.label} onInput=${(x) => setItem('company_stats', i, { label: x })} />
          <button class="btn ghost icon sm" aria-label="حذف" onClick=${() => set('company_stats', list('company_stats').filter((_, j) => j !== i))}><${Icon} name="trash" size=${15} /></button></div>`)}
          <div><button class="btn soft sm" onClick=${() => set('company_stats', [...list('company_stats'), { value: '', label: '' }])}><${Icon} name="plus" size=${15} />إضافة رقم</button></div></div></div>
        <div class="field"><span class="lbl">القيم / التخصصات</span><div class="rep">${list('company_pillars').map((s, i) => html`<div class="rep-item"><div class="inline" style="flex-wrap:nowrap">
          <${Input} value=${s.title} onInput=${(x) => setItem('company_pillars', i, { title: x })} />
          <button class="btn ghost icon sm" aria-label="حذف" onClick=${() => set('company_pillars', list('company_pillars').filter((_, j) => j !== i))}><${Icon} name="trash" size=${15} /></button></div>
          <${TextArea} minRows=${1} value=${s.text} onInput=${(x) => setItem('company_pillars', i, { text: x })} /></div>`)}
          <div><button class="btn soft sm" onClick=${() => set('company_pillars', [...list('company_pillars'), { title: '', text: '', icon: 'spark' }])}><${Icon} name="plus" size=${15} />إضافة</button></div></div></div>
      </section>
      <section class="card-ui pad stack"><h3>الإعدادات الافتراضية للعروض الجديدة</h3>
        <div class="row"><div class="field"><span class="lbl">الأسلوب</span><${Select} value=${v.default_tone} onChange=${(x) => set('default_tone', x)} options=${(meta?.tones || []).map((t) => ({ value: t.key, label: t.label }))} /></div>
          <div class="field"><span class="lbl">مستوى التفصيل</span><${Seg} value=${v.default_detail} onChange=${(x) => set('default_detail', x)} options=${(meta?.details || []).map((d) => ({ value: d.key, label: d.label }))} /></div></div>
        <div class="row"><div class="field"><span class="lbl">شكل الصفحات</span><${Seg} value=${v.default_layout} onChange=${(x) => set('default_layout', x)} options=${[{ value: 'landscape', label: 'أفقي 16:9' }, { value: 'portrait', label: 'مستند A4' }]} /></div>
          <div class="field"><span class="lbl">بادئة رقم العرض</span><input class="input ltr" style="max-width:160px" value=${v.proposal_prefix || ''} onInput=${(e) => set('proposal_prefix', e.target.value.toUpperCase())} /><span class="hint">مثال الرقم: ${v.proposal_prefix || 'AHD'}-2026-014</span></div></div>
        <div class="field"><span class="lbl">خط ملفات PowerPoint</span><${Select} value=${v.pptx_font} onChange=${(x) => set('pptx_font', x)} options=${[{ value: 'Saudi Serif VF', label: 'Saudi Serif VF (خط الهوية كما هو مثبت على أجهزة الفريق)' }, { value: 'Saudi Serif', label: 'Saudi Serif (النسخة الثابتة من خط الهوية)' }, { value: 'Segoe UI', label: 'Segoe UI (متوفر في Windows)' }, { value: 'Tahoma', label: 'Tahoma' }]} /></div>
      </section>
      <section class="card-ui pad stack"><h3>الكتابة بالذكاء الاصطناعي</h3>
        ${ai?.enabled ? html`<div class="notice ok"><${Icon} name="check" /><span>مفعّلة عبر Claude (${ai.model}). يحسّن النموذج صياغة النصوص بعد بنائها بالمحرك الداخلي، مع حماية تمنع إضافة أرقام أو معلومات غير موجودة في المدخلات.</span></div>`
          : html`<div class="notice info"><${Icon} name="info" /><div>يعمل النظام الآن بمحرك الكتابة الداخلي، وهو يكتب العروض كاملة دون اتصال خارجي. لتفعيل تحسين الصياغة عبر Claude أضف المفتاح في ملف <b class="ltr">.env</b> على الخادم:
            <pre class="ltr" style="background:#fff;border-radius:8px;padding:8px 12px;margin:8px 0 0;text-align:left">ANTHROPIC_API_KEY=sk-ant-...</pre><span style="font-size:13px">لا يُدخل المفتاح من هذه الصفحة حمايةً له؛ يبقى على الخادم ولا يصل إلى المتصفح.</span></div></div>`}
      </section>
    </div>
  </div>`;
}
