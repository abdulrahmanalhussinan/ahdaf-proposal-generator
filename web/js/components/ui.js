import { html, useEffect, useRef, useState } from '../vendor/preact-htm.js';
import { icon } from '../lib/icons.js';
import { STATUS } from '../lib/format.js';
import { store, useStore, link } from '../lib/store.js';

export const Icon = ({ name, size = 18 }) => html`<span style="display:inline-flex" dangerouslySetInnerHTML=${{ __html: icon(name, size) }} />`;

export function Btn({ kind = 'light', size, icon: ic, children, block, href, ...rest }) {
  const cls = ['btn', kind, size, block ? 'block' : '', !children ? 'icon' : ''].filter(Boolean).join(' ');
  if (href) return html`<a class=${cls} href=${href} onClick=${(e) => link(e, href)} ...${rest}>${ic && html`<${Icon} name=${ic} />`}${children}</a>`;
  return html`<button type="button" class=${cls} ...${rest}>${ic && html`<${Icon} name=${ic} />`}${children}</button>`;
}

export function Field({ label, hint, optional, required, error, children, id }) {
  return html`<div class="field">
    ${label && html`<label for=${id}>${label}${required && html`<span class="req">*</span>`}${optional && html`<span class="opt">(اختياري)</span>`}</label>`}
    ${children}
    ${error ? html`<span class="err">${error}</span>` : hint && html`<span class="hint">${hint}</span>`}
  </div>`;
}

export function Input({ value, onInput, ...rest }) {
  return html`<input class="input" value=${value ?? ''} onInput=${(e) => onInput && onInput(e.target.value)} ...${rest} />`;
}

export function TextArea({ value, onInput, autoGrow = true, minRows = 3, ...rest }) {
  const ref = useRef(null);
  const grow = () => {
    const el = ref.current;
    if (!el || !autoGrow) return;
    el.style.height = 'auto';
    el.style.height = `${Math.max(el.scrollHeight + 2, minRows * 26)}px`;
  };
  useEffect(grow, [value]);
  return html`<textarea ref=${ref} class="textarea" value=${value ?? ''} rows=${minRows}
    onInput=${(e) => { onInput && onInput(e.target.value); grow(); }} ...${rest}></textarea>`;
}

export function Select({ value, onChange, options, placeholder, ...rest }) {
  return html`<select class="select" value=${value ?? ''} onChange=${(e) => onChange && onChange(e.target.value)} ...${rest}>
    ${placeholder !== undefined && html`<option value="">${placeholder}</option>`}
    ${options.map((o) => html`<option value=${o.value} selected=${String(o.value) === String(value ?? '')}>${o.label}</option>`)}
  </select>`;
}

export function Switch({ checked, onChange, label }) {
  return html`<label class="switch"><input type="checkbox" checked=${!!checked} onChange=${(e) => onChange(e.target.checked)} />${label}</label>`;
}

export function Chips({ options, value = [], onChange, multi = true }) {
  const toggle = (k) => {
    if (!multi) return onChange(k);
    onChange(value.includes(k) ? value.filter((x) => x !== k) : [...value, k]);
  };
  const isOn = (k) => (multi ? value.includes(k) : value === k);
  return html`<div class="chips">${options.map((o) => html`<button type="button" class=${`chip ${isOn(o.value) ? 'on' : ''}`} aria-pressed=${isOn(o.value)} onClick=${() => toggle(o.value)}>${isOn(o.value) && multi ? html`<${Icon} name="check" size=${14} />` : null}${o.label}</button>`)}</div>`;
}

export function Seg({ options, value, onChange }) {
  return html`<div class="seg" role="radiogroup">${options.map((o) => html`<button type="button" role="radio" aria-checked=${value === o.value} class=${value === o.value ? 'on' : ''} onClick=${() => onChange(o.value)}>${o.label}</button>`)}</div>`;
}

export function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.draft;
  return html`<span class=${`badge ${s.tone}`}>${s.label}</span>`;
}

export function Spinner() { return html`<span class="spinner" aria-label="جارٍ التحميل"></span>`; }

export function Empty({ icon: ic = 'file', title, text, action }) {
  return html`<div class="empty"><div class="ill"><${Icon} name=${ic} size=${28} /></div><h3>${title}</h3>${text && html`<p>${text}</p>`}${action}</div>`;
}

export function Modal({ title, onClose, children, footer, size }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose && onClose(); };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = ''; };
  }, []);
  return html`<div class="modal-back" onMouseDown=${(e) => { if (e.target === e.currentTarget) onClose && onClose(); }}>
    <div class=${`modal ${size || ''}`} role="dialog" aria-modal="true" aria-label=${title}>
      <div class="modal-h"><h3>${title}</h3><button class="btn ghost icon x" aria-label="إغلاق" onClick=${onClose}><${Icon} name="x" /></button></div>
      <div class="modal-b">${children}</div>
      ${footer && html`<div class="modal-f">${footer}</div>`}
    </div></div>`;
}

export function Menu({ trigger, items, align = 'left' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, [open]);
  return html`<div class="menu-wrap" ref=${ref}>
    ${trigger((e) => { e && e.stopPropagation(); setOpen(!open); }, open)}
    ${open && html`<div class=${`menu ${align === 'right' ? 'right' : ''}`} role="menu" onClick=${(e) => e.stopPropagation()}>
      ${items.filter(Boolean).map((it) => (it === '-' ? html`<hr />` : html`<button role="menuitem" class=${it.danger ? 'danger' : ''} onClick=${() => { setOpen(false); it.onClick(); }}><${Icon} name=${it.icon || 'spark'} size=${17} />${it.label}</button>`))}
    </div>`}
  </div>`;
}

export function Toasts() {
  const toasts = useStore((s) => s.toasts);
  return html`<div class="toasts" role="status" aria-live="polite">${toasts.map((t) => html`<div class=${`toast ${t.kind}`}><${Icon} name=${t.kind === 'error' ? 'alert' : 'check'} />${t.message}</div>`)}</div>`;
}

export function ConfirmHost() {
  const c = useStore((s) => s.confirm);
  if (!c) return null;
  return html`<${Modal} title=${c.title || 'تأكيد'} onClose=${() => c.resolve(false)}
    footer=${html`<${Btn} kind=${c.danger ? 'danger' : 'primary'} onClick=${() => c.resolve(true)}>${c.confirmLabel || 'تأكيد'}</${Btn}><${Btn} kind="ghost" onClick=${() => c.resolve(false)}>إلغاء</${Btn}>`}>
    <p style="line-height:1.8">${c.message}</p></${Modal}>`;
}

export function Tabs({ tabs, value, onChange }) {
  return html`<div class="tabs" role="tablist">${tabs.map((t) => html`<button role="tab" aria-selected=${t.key === value} class=${t.key === value ? 'on' : ''} onClick=${() => onChange(t.key)}>${t.label}${t.count !== undefined && html`<span class="n">${t.count}</span>`}</button>`)}</div>`;
}

// Textarea bound to an array of lines
export function LinesInput({ value = [], onChange, placeholder, minRows = 3 }) {
  const [text, setText] = useState((value || []).join('\n'));
  useEffect(() => {
    const joined = (value || []).join('\n');
    if (joined !== text.split('\n').map((s) => s.trim()).filter(Boolean).join('\n')) setText(joined);
  }, [JSON.stringify(value)]);
  return html`<${TextArea} value=${text} minRows=${minRows} placeholder=${placeholder}
    onInput=${(v) => { setText(v); onChange(v.split('\n').map((s) => s.trim()).filter(Boolean)); }} />`;
}

export function ImagePicker({ value, onChange, label = 'رفع صورة', onUpload }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);
  const pick = async (e) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = '';
    if (!f) return;
    setBusy(true);
    try { const r = await onUpload(f); onChange(r.url); } finally { setBusy(false); }
  };
  return html`<div class="inline">
    ${value ? html`<img src=${value} alt="" style="width:96px;height:56px;object-fit:cover;border-radius:8px;border:1px solid var(--line)" />` : null}
    <input ref=${ref} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" hidden onChange=${pick} />
    <${Btn} kind="light" size="sm" icon="image" disabled=${busy} onClick=${() => ref.current.click()}>${busy ? 'جارٍ الرفع…' : value ? 'تغيير' : label}</${Btn}>
    ${value && html`<${Btn} kind="ghost" size="sm" icon="trash" onClick=${() => onChange(null)}>إزالة</${Btn}>`}
  </div>`;
}

export function useDebounced(fn, ms) {
  const t = useRef(null);
  const latest = useRef(fn);
  latest.current = fn;
  useEffect(() => () => clearTimeout(t.current), []);
  return (...args) => { clearTimeout(t.current); t.current = setTimeout(() => latest.current(...args), ms); };
}

export function setTitle(t) {
  document.title = t ? `${t} — مولّد العروض الفنية | أهداف` : 'مولّد العروض الفنية | أهداف';
}

export { store };
