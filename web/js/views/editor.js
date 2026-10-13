import { html, useEffect, useRef, useState } from '../vendor/preact-htm.js';
import { api } from '../lib/api.js';
import { navigate, toast, toastError, confirmDialog, useStore, link } from '../lib/store.js';
import { relTime, STATUS } from '../lib/format.js';
import { Btn, Icon, Input, TextArea, Select, Switch, Seg, Menu, Modal, ImagePicker, Spinner, Empty, setTitle } from '../components/ui.js';
import { BlockEditor, BLOCK_LABELS, BLOCK_ICONS, NEW_BLOCKS, rid, countPlaceholders } from '../components/block-editors.js';
import { renderDocument } from '../document/render.js';
import { exportFile, duplicate, remove } from './actions.js';

const SAVE_DELAY = 800;

export function Editor({ params }) {
  const meta = useStore((s) => s.meta);
  const [p, setP] = useState(null);
  const [settings, setSettings] = useState({});
  const [sel, setSel] = useState('__cover');
  const [save, setSave] = useState('saved');
  const [showPrev, setShowPrev] = useState(false);
  const [busy, setBusy] = useState('');
  const [undo, setUndo] = useState(null);
  const [revs, setRevs] = useState(null);
  const [tplModal, setTplModal] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const timer = useRef(null);
  const pending = useRef(null);
  const latest = useRef(null);
  latest.current = p;

  useEffect(() => {
    api.get(`/api/proposals/${params.id}`).then((data) => {
      setP(data);
      setTitle(data.project_name);
      const first = (data.doc.sections || []).find((x) => x.type !== 'about') || (data.doc.sections || [])[0];
      setSel(first ? first.id : '__cover');
    }).catch((e) => { if (e.status === 404) setNotFound(true); else toastError(e); });
    api.get('/api/settings').then((s) => setSettings(s.values || {})).catch(() => {});
    const before = (e) => { if (pending.current) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', before);
    return () => { window.removeEventListener('beforeunload', before); clearTimeout(timer.current); if (pending.current) flush(); };
  }, [params.id]);

  // ---------------------------------------------------------------- saving
  const flush = async () => {
    clearTimeout(timer.current);
    const doc = pending.current;
    if (!doc) return;
    pending.current = null;
    setSave('saving');
    try {
      await api.put(`/api/proposals/${params.id}`, { doc });
      setSave(pending.current ? 'dirty' : 'saved');
    } catch (e) {
      pending.current = pending.current || doc;
      setSave('error');
      toastError(e);
    }
  };
  const updateDoc = (fn) => {
    setP((cur) => {
      const doc = fn(cur.doc);
      pending.current = doc;
      return { ...cur, doc };
    });
    setSave('dirty');
    clearTimeout(timer.current);
    timer.current = setTimeout(flush, SAVE_DELAY);
  };
  const updateSection = (id, patch) => updateDoc((d) => ({ ...d, sections: d.sections.map((s) => (s.id === id ? { ...s, ...patch } : s)) }));

  if (notFound) return html`<div class="content"><${Empty} icon="search" title="العرض غير موجود" text="ربما حُذف. عُد إلى قائمة العروض." action=${html`<${Btn} kind="primary" href="/proposals">العروض السابقة</${Btn}>`} /></div>`;
  if (!p) return html`<div style="min-height:60vh;display:grid;place-items:center"><${Spinner} /></div>`;

  const doc = p.doc;
  const sections = doc.sections || [];
  const section = sections.find((s) => s.id === sel);
  const placeholders = countPlaceholders(doc);
  const missing = p.meta?.missing || [];

  // ---------------------------------------------------------------- actions
  const setStatus = async (status) => {
    try { const r = await api.put(`/api/proposals/${p.id}`, { status }); setP((c) => ({ ...c, status: r.status })); toast(`الحالة: ${STATUS[status].label}`); } catch (e) { toastError(e); }
  };
  const regenerate = async (tone) => {
    if (!section) return;
    await flush();
    setBusy('regen');
    const prev = section;
    try {
      const fresh = await api.post(`/api/proposals/${p.id}/sections/${section.id}/regenerate`, { tone: tone || null });
      setP((c) => ({ ...c, doc: { ...c.doc, sections: c.doc.sections.map((s) => (s.id === fresh.id ? fresh : s)) } }));
      setUndo({ id: fresh.id, prev });
      toast(`تمت إعادة صياغة «${fresh.title}»`);
    } catch (e) { toastError(e); } finally { setBusy(''); }
  };
  const undoRegen = () => {
    if (!undo) return;
    updateDoc((d) => ({ ...d, sections: d.sections.map((s) => (s.id === undo.id ? undo.prev : s)) }));
    setUndo(null);
    toast('تمت استعادة الصياغة السابقة');
  };
  const doExport = async (kind) => {
    await flush();
    if (placeholders > 0) {
      const ok = await confirmDialog({ title: 'حقول لم تُعبأ', confirmLabel: 'تصدير على أي حال',
        message: `يحتوي العرض على ${placeholders} حقل بحاجة إلى تعبئة (مظللة بالأصفر في المعاينة). ستظهر هذه الحقول في الملف كما هي. هل تريد التصدير الآن؟` });
      if (!ok) return;
    }
    setBusy(kind);
    await exportFile(p, kind);
    setBusy('');
  };
  const newVersion = async () => {
    await flush();
    try { const r = await api.post(`/api/proposals/${p.id}/versions`, { note: '' }); setP(r); toast(`أصبحت نسخة العرض ${r.version}، وحُفظت النسخة السابقة في السجل`); } catch (e) { toastError(e); }
  };
  const openRevisions = async () => {
    try { const r = await api.get(`/api/proposals/${p.id}/revisions`); setRevs(r.items); } catch (e) { toastError(e); }
  };
  const restore = async (rev) => {
    if (!(await confirmDialog({ title: 'استرجاع نسخة', message: `سيُستبدل المحتوى الحالي بالنسخة المحفوظة (${rev.note || rev.version}). يُحفظ المحتوى الحالي أولًا في السجل.`, confirmLabel: 'استرجاع' }))) return;
    try { const r = await api.post(`/api/proposals/${p.id}/revisions/${rev.id}/restore`); setP(r); setRevs(null); toast('تم استرجاع النسخة'); } catch (e) { toastError(e); }
  };
  const addSection = () => {
    const id = `custom_${rid()}`;
    updateDoc((d) => ({ ...d, sections: [...d.sections, { id, type: 'custom', title: 'قسم جديد', title_en: '', subtitle: '', visible: true, divider: false, blocks: [{ id: rid(), type: 'paragraph', text: '' }] }] }));
    setSel(id);
  };
  const deleteSection = async (s) => {
    if (!(await confirmDialog({ title: 'حذف القسم', danger: true, confirmLabel: 'حذف', message: `سيُحذف قسم «${s.title}» من العرض. يمكنك إخفاؤه بدلًا من حذفه.` }))) return;
    updateDoc((d) => ({ ...d, sections: d.sections.filter((x) => x.id !== s.id) }));
    setSel('__cover');
  };
  const moveSection = (from, to) => {
    if (from === to || to < 0 || to >= sections.length) return;
    updateDoc((d) => {
      const arr = [...d.sections];
      const [it] = arr.splice(from, 1);
      arr.splice(to, 0, it);
      return { ...d, sections: arr };
    });
  };
  const blockOps = (bi) => ({
    up: () => updateSection(section.id, { blocks: swap(section.blocks, bi, bi - 1) }),
    down: () => updateSection(section.id, { blocks: swap(section.blocks, bi, bi + 1) }),
    del: () => updateSection(section.id, { blocks: section.blocks.filter((_, j) => j !== bi) }),
  });
  const addBlock = (type) => updateSection(section.id, { blocks: [...section.blocks, { id: rid(), ...NEW_BLOCKS[type]() }] });

  const saveLabel = { saved: 'تم الحفظ', dirty: 'تعديلات غير محفوظة', saving: 'جارٍ الحفظ…', error: 'تعذر الحفظ' }[save];

  return html`<div>
    <div class="ed-bar">
      <a class="btn ghost icon" href="/proposals" onClick=${(e) => link(e, '/proposals')} aria-label="رجوع"><${Icon} name="arrowRight" /></a>
      <div class="ttl"><b title=${p.project_name}>${doc.cover?.title || p.project_name}</b><span>${p.client_name} · <span class="ltr">${p.number}</span> · نسخة ${doc.cover?.version || p.version}</span></div>
      <${Select} value=${p.status} onChange=${setStatus} options=${Object.entries(STATUS).map(([k, v]) => ({ value: k, label: v.label }))} style="width:auto;padding-top:6px;padding-bottom:6px" aria-label="حالة العرض" />
      <span class="save-state" aria-live="polite">${save === 'saving' ? html`<span class="spinner" style="width:12px;height:12px"></span>` : html`<${Icon} name=${save === 'error' ? 'alert' : save === 'saved' ? 'check' : 'clock'} size=${15} />`}${saveLabel}</span>
      <span class="grow"></span>
      <${Btn} kind="ghost" size="sm" icon="eye" class="btn ghost sm prev-toggle" onClick=${() => setShowPrev(!showPrev)}>${showPrev ? 'إخفاء المعاينة' : 'معاينة'}</${Btn}>
      <${Btn} kind="light" size="sm" icon="pdf" disabled=${busy === 'pdf'} onClick=${() => doExport('pdf')}>${busy === 'pdf' ? 'جارٍ التصدير…' : 'تصدير PDF'}</${Btn}>
      <${Btn} kind="light" size="sm" icon="presentation" class="btn light sm hide-m" disabled=${busy === 'pptx'} onClick=${() => doExport('pptx')}>PowerPoint</${Btn}>
      <${Menu} align="left" trigger=${(t) => html`<button class="btn light icon sm" aria-label="المزيد" onClick=${t}><${Icon} name="more" /></button>`} items=${[
        { label: 'تعديل مدخلات المشروع', icon: 'edit', onClick: async () => { await flush(); navigate(`/proposals/${p.id}/inputs`); } },
        { label: 'إصدار نسخة جديدة من العرض', icon: 'layers', onClick: newVersion },
        { label: 'سجل النسخ', icon: 'history', onClick: openRevisions },
        { label: 'عرض للقراءة', icon: 'eye', onClick: async () => { await flush(); navigate(`/proposals/${p.id}`); } },
        '-',
        { label: 'نسخ العرض', icon: 'copy', onClick: async () => { await flush(); duplicate(p); } },
        { label: 'حفظ كقالب', icon: 'layout', onClick: () => setTplModal(true) },
        '-',
        { label: 'حذف العرض', icon: 'trash', danger: true, onClick: () => remove(p, () => navigate('/proposals')) },
      ]} />
    </div>
    <div class=${`ed ${showPrev ? 'show-prev' : ''}`}>
      <nav class="ed-nav" aria-label="أقسام العرض">
        <h4>الأقسام — اسحب لإعادة الترتيب</h4>
        <div class=${`sec-item ${sel === '__cover' ? 'on' : ''}`} onClick=${() => setSel('__cover')}><span class="grip"><${Icon} name="image" size=${15} /></span><span class="t">الغلاف وإعدادات العرض</span></div>
        ${sections.map((s, i) => html`<${SectionItem} key=${s.id} s=${s} i=${i} on=${sel === s.id} onSelect=${() => setSel(s.id)} onMove=${moveSection}
          onToggle=${() => updateSection(s.id, { visible: s.visible === false })} />`)}
        <div style="margin-top:10px"><${Btn} kind="soft" size="sm" icon="plus" block onClick=${addSection}>إضافة قسم</${Btn}></div>
      </nav>

      <main class="ed-main">
        ${(placeholders > 0 || missing.length > 0) && html`<${MissingBanner} placeholders=${placeholders} missing=${missing} id=${p.id} />`}
        ${sel === '__cover' ? html`<${CoverEditor} doc=${doc} updateDoc=${updateDoc} />` : section ? html`
          <div class="sec-head">
            <div class="fields">
              <input class="title-in" value=${section.title} onInput=${(e) => updateSection(section.id, { title: e.target.value })} aria-label="عنوان القسم" />
              <input class="sub-in" value=${section.subtitle || ''} placeholder="سطر تعريفي تحت العنوان (اختياري)" onInput=${(e) => updateSection(section.id, { subtitle: e.target.value })} aria-label="السطر التعريفي" />
            </div>
            ${section.type !== 'custom' && html`<div class="regen">
              ${undo && undo.id === section.id && html`<${Btn} kind="ghost" size="sm" icon="history" onClick=${undoRegen}>تراجع</${Btn}>`}
              <${Menu} align="left" trigger=${(t) => html`<button class="btn soft sm" disabled=${busy === 'regen'} onClick=${t}>${busy === 'regen' ? html`<span class="spinner" style="width:14px;height:14px"></span>` : html`<${Icon} name="refresh" size=${16} />`}إعادة توليد القسم</button>`}
                items=${[{ label: 'صياغة جديدة بنفس الأسلوب', icon: 'refresh', onClick: () => regenerate(null) }, '-',
                  ...(meta?.tones || []).map((t) => ({ label: `بأسلوب: ${t.label}`, icon: 'pen', onClick: () => regenerate(t.key) }))]} />
            </div>`}
          </div>
          <div class="inline" style="margin:-4px 0 16px;gap:18px">
            <${Switch} checked=${section.visible !== false} onChange=${(v) => updateSection(section.id, { visible: v })} label="يظهر في العرض" />
            <${Switch} checked=${!!section.divider} onChange=${(v) => updateSection(section.id, { divider: v })} label="صفحة فاصلة قبله" />
            <div class="inline" style="gap:8px"><span class="muted" style="font-size:13.5px">صورة القسم</span><${ImagePicker} value=${section.image} onChange=${(v) => updateSection(section.id, { image: v })} onUpload=${api.upload} label="إضافة" /></div>
            <span style="margin-inline-start:auto" class="inline">
              <button class="btn ghost sm" disabled=${sections.indexOf(section) === 0} onClick=${() => moveSection(sections.indexOf(section), sections.indexOf(section) - 1)}><${Icon} name="chevronUp" size=${15} />للأعلى</button>
              <button class="btn ghost sm" disabled=${sections.indexOf(section) === sections.length - 1} onClick=${() => moveSection(sections.indexOf(section), sections.indexOf(section) + 1)}><${Icon} name="chevronDown" size=${15} />للأسفل</button>
              <button class="btn ghost sm" onClick=${() => deleteSection(section)}><${Icon} name="trash" size=${15} />حذف</button>
            </span>
          </div>
          ${section.blocks.map((b, bi) => html`<div class="blk-ed" key=${b.id}>
            <div class="bh"><span class="kind"><${Icon} name=${BLOCK_ICONS[b.type] || 'text'} size=${15} />${BLOCK_LABELS[b.type] || b.type}</span>
              <span class="tools">
                <button class="btn ghost icon sm" aria-label="تحريك لأعلى" disabled=${bi === 0} onClick=${blockOps(bi).up}><${Icon} name="chevronUp" size=${15} /></button>
                <button class="btn ghost icon sm" aria-label="تحريك لأسفل" disabled=${bi === section.blocks.length - 1} onClick=${blockOps(bi).down}><${Icon} name="chevronDown" size=${15} /></button>
                <button class="btn ghost icon sm" aria-label="حذف العنصر" onClick=${blockOps(bi).del}><${Icon} name="trash" size=${15} /></button>
              </span></div>
            <${BlockEditor} block=${b} onChange=${(nb) => updateSection(section.id, { blocks: section.blocks.map((x, j) => (j === bi ? nb : x)) })} />
          </div>`)}
          <div class="add-row"><span class="muted" style="font-size:13px;align-self:center">إضافة:</span>
            ${Object.keys(NEW_BLOCKS).map((t) => html`<button class="btn light sm" onClick=${() => addBlock(t)}><${Icon} name=${BLOCK_ICONS[t]} size=${15} />${BLOCK_LABELS[t]}</button>`)}</div>
        ` : html`<${Empty} title="اختر قسمًا" text="اختر قسمًا من القائمة لتعديله." />`}
      </main>

      <${Preview} proposal=${p} settings=${settings} sel=${sel} onClose=${() => setShowPrev(false)} />
    </div>
    ${revs && html`<${Modal} title="سجل النسخ" onClose=${() => setRevs(null)}>
      ${revs.length === 0 ? html`<p class="muted">لا توجد نسخ محفوظة بعد. استخدم «إصدار نسخة جديدة» لحفظ نسخة قبل التعديلات الكبيرة.</p>`
        : html`<div class="stack" style="gap:8px">${revs.map((r) => html`<div class="inline card-ui" style="padding:10px 14px"><div style="flex:1"><b>نسخة ${r.version}</b><div class="muted" style="font-size:13px">${r.note || ''} · ${relTime(r.created_at)}</div></div><${Btn} kind="light" size="sm" icon="history" onClick=${() => restore(r)}>استرجاع</${Btn}></div>`)}</div>`}
    </${Modal}>`}
    ${tplModal && html`<${SaveTemplate} p=${p} onClose=${() => setTplModal(false)} />`}
  </div>`;
}

function swap(arr, i, j) {
  if (j < 0 || j >= arr.length) return arr;
  const out = [...arr];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

function SectionItem({ s, i, on, onSelect, onMove, onToggle }) {
  const [over, setOver] = useState(false);
  const hidden = s.visible === false;
  return html`<div class=${`sec-item ${on ? 'on' : ''} ${hidden ? 'hidden-sec' : ''} ${over ? 'drag-over' : ''}`} draggable="true"
    onClick=${onSelect} tabIndex="0" role="button" aria-current=${on}
    onKeyDown=${(e) => { if (e.key === 'Enter') onSelect(); if (e.altKey && e.key === 'ArrowUp') onMove(i, i - 1); if (e.altKey && e.key === 'ArrowDown') onMove(i, i + 1); }}
    onDragStart=${(e) => { e.dataTransfer.setData('text/plain', String(i)); e.dataTransfer.effectAllowed = 'move'; }}
    onDragOver=${(e) => { e.preventDefault(); setOver(true); }} onDragLeave=${() => setOver(false)}
    onDrop=${(e) => { e.preventDefault(); setOver(false); onMove(Number(e.dataTransfer.getData('text/plain')), i); }}>
    <span class="grip" aria-hidden="true"><${Icon} name="grip" size=${15} /></span>
    <span class="n">${String(i + 1).padStart(2, '0')}</span><span class="t">${s.title}</span>
    <button class="eye" aria-label=${hidden ? 'إظهار القسم' : 'إخفاء القسم'} onClick=${(e) => { e.stopPropagation(); onToggle(); }}><${Icon} name=${hidden ? 'eyeOff' : 'eye'} size=${16} /></button>
  </div>`;
}

function MissingBanner({ placeholders, missing, id }) {
  const [open, setOpen] = useState(false);
  return html`<div class="notice warn" style="margin-bottom:16px"><${Icon} name="alert" />
    <div style="flex:1"><b>${placeholders > 0 ? `${placeholders} حقل بحاجة إلى تعبئة` : 'معلومات لم تُدخل عند الإنشاء'}</b>
      <span> — لم يخترع النظام هذه المعلومات. عبّئ الحقول المظللة بالأصفر في المعاينة، أو أكمل المدخلات وأعد التوليد.</span>
      ${missing.length > 0 && html` <button class="btn ghost sm" style="padding:0 6px" onClick=${() => setOpen(!open)}>${open ? 'إخفاء التفاصيل' : 'التفاصيل'}</button>`}
      ${open && html`<div class="missing-list">${missing.map((m) => html`<div><b>${m.label}:</b><span>${m.hint}</span></div>`)}
        <div><a href=${`/proposals/${id}/inputs`} onClick=${(e) => link(e, `/proposals/${id}/inputs`)}>إكمال المدخلات وإعادة التوليد</a></div></div>`}
    </div></div>`;
}

function CoverEditor({ doc, updateDoc }) {
  const c = doc.cover || {};
  const setC = (patch) => updateDoc((d) => ({ ...d, cover: { ...d.cover, ...patch } }));
  return html`<div class="stack cover-ed">
    <div class="sec-head"><div class="fields"><h2 style="font-size:22px;color:var(--night)">الغلاف وإعدادات العرض</h2><span class="muted">تظهر هذه البيانات في الصفحة الأولى من العرض.</span></div></div>
    <div class="blk-ed stack">
      <div class="row"><div class="field"><span class="lbl">عنوان العرض (اسم المشروع)</span><${Input} value=${c.title} onInput=${(v) => setC({ title: v })} /></div>
        <div class="field"><span class="lbl">العبارة فوق العنوان</span><${Input} value=${c.kicker} onInput=${(v) => setC({ kicker: v })} /></div></div>
      <div class="field"><span class="lbl">السطر التعريفي</span><${TextArea} minRows=${2} value=${c.subtitle} onInput=${(v) => setC({ subtitle: v })} /></div>
      <div class="row" style="--n:3"><div class="field"><span class="lbl">مقدم إلى</span><${Input} value=${c.client} onInput=${(v) => setC({ client: v })} /></div>
        <div class="field"><span class="lbl">التاريخ</span><${Input} value=${c.date} onInput=${(v) => setC({ date: v })} /></div>
        <div class="field"><span class="lbl">النسخة</span><${Input} value=${c.version} onInput=${(v) => setC({ version: v })} /></div></div>
      <div class="field"><span class="lbl">مقدم من</span><${Input} value=${c.prepared_by} onInput=${(v) => setC({ prepared_by: v })} /></div>
    </div>
    <div class="blk-ed stack">
      <div class="field"><span class="lbl">صورة الغلاف</span><span class="hint">تظهر خلف الغلاف بطبقة بنفسجية كما في عروض أهداف. بدونها يُستخدم التصميم البنفسجي.</span><${ImagePicker} value=${c.image} onChange=${(v) => setC({ image: v })} onUpload=${api.upload} label="رفع صورة الغلاف" /></div>
      <div class="field"><span class="lbl">شعار العميل</span><${ImagePicker} value=${c.client_logo} onChange=${(v) => setC({ client_logo: v })} onUpload=${api.upload} label="رفع الشعار" /></div>
    </div>
    <div class="blk-ed stack">
      <div class="field"><span class="lbl">شكل الصفحات</span><${Seg} value=${doc.layout || 'landscape'} onChange=${(v) => updateDoc((d) => ({ ...d, layout: v }))} options=${[{ value: 'landscape', label: 'أفقي 16:9' }, { value: 'portrait', label: 'مستند A4' }]} /></div>
      <${Switch} checked=${doc.show_toc !== false} onChange=${(v) => updateDoc((d) => ({ ...d, show_toc: v }))} label="صفحة محتويات العرض" />
    </div>
  </div>`;
}

function Preview({ proposal, settings, sel, onClose }) {
  const host = useRef(null);
  const wrap = useRef(null);
  const [all, setAll] = useState(false);
  const [pages, setPages] = useState(0);
  const t = useRef(null);
  useEffect(() => {
    clearTimeout(t.current);
    t.current = setTimeout(async () => {
      if (!host.current || !wrap.current) return;
      const width = Math.max(260, wrap.current.clientWidth - 8);
      try {
        const r = await renderDocument(host.current, proposal, settings, { onlySection: all ? null : sel, scaleTo: width });
        setPages(r.pageCount);
      } catch (e) { console.warn('preview', e); }
    }, 320);
    return () => clearTimeout(t.current);
  }, [proposal.doc, settings, sel, all]);
  return html`<aside class="ed-prev" ref=${wrap} aria-label="معاينة الصفحات">
    <div class="ph"><${Icon} name="eye" size=${16} /><span>${all ? 'العرض كاملًا' : 'معاينة القسم'} · ${pages} صفحة</span><span class="grow"></span>
      <button class="btn light sm" onClick=${() => setAll(!all)}>${all ? 'القسم الحالي فقط' : 'كل الصفحات'}</button>
      <button class="btn ghost icon sm" aria-label="إغلاق المعاينة" onClick=${onClose}><${Icon} name="x" size=${16} /></button></div>
    <div ref=${host}></div>
  </aside>`;
}

function SaveTemplate({ p, onClose }) {
  const [name, setName] = useState(`${p.project_name}`);
  const [desc, setDesc] = useState('');
  const save = async () => {
    try { await api.post(`/api/proposals/${p.id}/save-as-template`, { name, description: desc }); toast('تم حفظ القالب'); onClose(); } catch (e) { toastError(e); }
  };
  return html`<${Modal} title="حفظ العرض كقالب" onClose=${onClose} footer=${html`<${Btn} kind="primary" onClick=${save} disabled=${!name.trim()}>حفظ القالب</${Btn}><${Btn} kind="ghost" onClick=${onClose}>إلغاء</${Btn}>`}>
    <div class="stack"><p class="muted">يحفظ القالب نوع المشروع والخدمات والمدة والتفضيلات، دون بيانات العميل، لتبدأ منه عروضًا مشابهة.</p>
      <div class="field"><span class="lbl">اسم القالب</span><${Input} value=${name} onInput=${setName} /></div>
      <div class="field"><span class="lbl">وصف مختصر</span><${TextArea} minRows=${2} value=${desc} onInput=${setDesc} /></div></div>
  </${Modal}>`;
}
