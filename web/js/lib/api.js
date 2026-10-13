// Thin API client. All data goes through the server; nothing sensitive is stored in the browser.
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(method, url, body, opts = {}) {
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
  upload: (file) => { const fd = new FormData(); fd.append('file', file); return request('POST', '/api/uploads', fd); },
  async download(url, fallbackName) {
    const res = await request('GET', url, undefined, { raw: true });
    const blob = await res.blob();
    const cd = res.headers.get('Content-Disposition') || '';
    const m = cd.match(/filename\*=UTF-8''([^;]+)/);
    const name = m ? decodeURIComponent(m[1]) : fallbackName;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    return name;
  },
};
