// Minimal shared state: app metadata, toasts and confirm dialogs, plus the path router.
import { useEffect, useState } from '../vendor/preact-htm.js';
import { STATIC } from './env.js';

function createStore(initial) {
  let state = initial;
  const subs = new Set();
  return {
    get: () => state,
    set(patch) { state = { ...state, ...(typeof patch === 'function' ? patch(state) : patch) }; subs.forEach((f) => f(state)); },
    subscribe(f) { subs.add(f); return () => subs.delete(f); },
  };
}

export const store = createStore({ meta: null, toasts: [], confirm: null, navOpen: false });

export function useStore(selector = (s) => s) {
  const [value, setValue] = useState(() => selector(store.get()));
  useEffect(() => store.subscribe((s) => setValue(selector(s))), []);
  return value;
}

let toastId = 0;
export function toast(message, kind = 'ok', ms = 3200) {
  const id = ++toastId;
  store.set((s) => ({ toasts: [...s.toasts, { id, message, kind }] }));
  setTimeout(() => store.set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), ms);
}

export function toastError(err) {
  toast(err?.message || String(err), 'error', 5000);
}

export function confirmDialog(opts) {
  return new Promise((resolve) => {
    store.set({ confirm: { ...opts, resolve: (v) => { store.set({ confirm: null }); resolve(v); } } });
  });
}

// ---------------------------------------------------------------- router
const routeSubs = new Set();

function current() {
  if (STATIC) {
    const h = location.hash.replace(/^#/, '') || '/';
    const [p, qs = ''] = h.split('?');
    return { path: p || '/', search: qs ? `?${qs}` : '' };
  }
  return { path: location.pathname, search: location.search };
}

/** URL to put in an <a href> for an in-app route. */
export const hrefOf = (to) => (STATIC ? `#${to}` : to);

export function navigate(to, { replace = false } = {}) {
  const c = current();
  if (to === c.path + c.search) return;
  if (STATIC) {
    if (replace) location.replace(`#${to}`); else location.hash = to;
  } else {
    if (replace) history.replaceState(null, '', to); else history.pushState(null, '', to);
    routeSubs.forEach((f) => f());
  }
  window.scrollTo(0, 0);
  store.set({ navOpen: false });
}
window.addEventListener(STATIC ? 'hashchange' : 'popstate', () => routeSubs.forEach((f) => f()));

export function useRoute() {
  const [, force] = useState(0);
  useEffect(() => { const f = () => force((n) => n + 1); routeSubs.add(f); return () => routeSubs.delete(f); }, []);
  const c = current();
  return { path: c.path, query: new URLSearchParams(c.search) };
}

export function link(e, to) {
  if (e.metaKey || e.ctrlKey || e.shiftKey || e.button === 1) return;
  e.preventDefault();
  navigate(to);
}

export function match(pattern, path) {
  const p = pattern.split('/').filter(Boolean);
  const s = path.split('/').filter(Boolean);
  if (p.length !== s.length) return null;
  const params = {};
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(':')) params[p[i].slice(1)] = decodeURIComponent(s[i]);
    else if (p[i] !== s[i]) return null;
  }
  return params;
}
