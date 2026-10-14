// Thin API client. On the server edition every call goes over HTTP; in the browser edition
// (GitHub Pages) the same calls are answered in-process by the Python backend running in Pyodide.
import { STATIC } from './env.js';

let backend = null;
const localBackend = async () => backend || (backend = await import('./pybackend.js'));
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(method, url, body, opts = {}) {
  if (STATIC) return (await localBackend()).request(method, url, body === undefined ? null : body);
  const init = { method, headers: { Accept: 'application/json' } };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(body); }
  let res;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError('تعذر الاتصال بالخادم. تأكد من تشغيل النظام ثم أعد المحاولة.', 0);
  }
  if (opts.raw) {
    if (!res.ok) throw new ApiError(await errorText(res), res.status);
    return res;
  }
  if (res.status === 204) return null;
  if (!res.ok) throw new ApiError(await errorText(res), res.status);
  return res.json();
}

async function errorText(res) {
  try {
    const data = await res.json();
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) return 'بعض الحقول غير صحيحة. راجع المدخلات.';
  } catch { /* not JSON */ }
  return `حدث خطأ (${res.status})`;
}

export const api = {
  get: (u) => request('GET', u),
  post: (u, b = {}) => request('POST', u, b),
  put: (u, b) => request('PUT', u, b),
  del: (u) => request('DELETE', u),
  upload: (file) => {
    if (STATIC) return fileToDataUrl(file);
    const fd = new FormData();
    fd.append('file', file);
    return request('POST', '/api/uploads', fd);
  },
  // Files the server reads (celebrity sheets, client profiles). The browser edition sends them as base64.
  async uploadFile(path, file) {
    if (STATIC) {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let bin = '';
      for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
      return request('POST', path, { filename: file.name, data: btoa(bin) });
    }
    const fd = new FormData();
    fd.append('file', file);
    return request('POST', path, fd);
  },
  async exportPptxLocal(id) { return (await localBackend()).exportPptx(id); },
  saveBlob,
  async download(url, fallbackName) {
    const res = await request('GET', url, undefined, { raw: true });
    const blob = await res.blob();
    const cd = res.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename\*=UTF-8''([^;]+)/);
    const name = m ? decodeURIComponent(m[1]) : fallbackName;
    saveBlob(blob, name);
    return name;
  },
};

function saveBlob(blob, name) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

// Browser edition: images are kept inside the proposal as data URLs (resized to keep storage small).
async function fileToDataUrl(file) {
  const allowed = ['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml'];
  if (!allowed.includes(file.type)) throw new ApiError('الصيغ المسموحة: PNG، JPG، WEBP، SVG', 415);
  if (file.size > 8 * 1024 * 1024) throw new ApiError('الحد الأقصى لحجم الصورة 8 ميجابايت', 413);
  if (file.type === 'image/svg+xml') {
    const text = await file.text();
    if (/<script|javascript:/i.test(text)) throw new ApiError('ملف SVG يحتوي على شيفرة غير مسموحة', 415);
    const bytes = new TextEncoder().encode(text);
    let bin = '';
    bytes.forEach((b) => { bin += String.fromCharCode(b); });
    return { url: `data:image/svg+xml;base64,${btoa(bin)}`, filename: file.name };
  }
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1800 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const type = file.type === 'image/png' ? 'image/png' : 'image/jpeg';
  return { url: canvas.toDataURL(type, 0.86), filename: file.name };
}
