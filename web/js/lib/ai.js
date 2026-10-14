// Claude in the browser edition (GitHub Pages). The visitor's own API key is kept in this browser
// only (localStorage) and is sent to api.anthropic.com and nowhere else. The prompts are built by the
// same Python code as on the server (/api/ai/request), and the answers go back through the same
// guards (`ai_content`), so the site writes exactly like the installed version.
const KEY = 'ahdaf.ai.key';
const MODEL = 'ahdaf.ai.model';
export const MODELS = [
  { value: 'claude-opus-5-5', label: 'Claude Opus 5.5 (الأفضل كتابةً)' },
  { value: 'claude-sonnet-5-5', label: 'Claude Sonnet 5.5 (أسرع وأقل تكلفة)' },
];

const read = (k) => { try { return localStorage.getItem(k) || ''; } catch { return ''; } };
const write = (k, v) => { try { if (v) localStorage.setItem(k, v); else localStorage.removeItem(k); } catch { /* storage blocked */ } };

export const getKey = () => read(KEY);
export const setKey = (v) => write(KEY, (v || '').trim());
export const getModel = () => read(MODEL) || MODELS[0].value;
export const setModel = (v) => write(MODEL, v);
export const status = () => (getKey()
  ? { provider: 'browser', enabled: true, model: getModel(), label: 'Claude عبر مفتاحك المحفوظ في هذا المتصفح' }
  : { provider: 'rules', enabled: false, model: null, label: 'محرك الكتابة الداخلي' });

export class AiError extends Error {}

function explain(status, body) {
  const msg = body?.error?.message || '';
  if (status === 401) return 'مفتاح Claude غير صحيح. راجعه في الإعدادات.';
  if (status === 403) return 'المفتاح لا يملك صلاحية لهذا النموذج.';
  if (status === 429) return 'تجاوزت حد الاستخدام في حساب Claude. حاول بعد قليل.';
  if (status === 529 || status === 503) return 'خدمة Claude مزدحمة الآن. حاول بعد دقائق.';
  if (/credit|balance|billing/i.test(msg)) return 'رصيد حساب Claude لا يكفي. اشحن الرصيد من console.anthropic.com.';
  return `تعذر الاتصال بـ Claude (${status})${msg ? `: ${msg}` : ''}`;
}

// One Messages API call, streamed (long answers would otherwise risk an idle connection drop).
async function stream(req, structured, onText) {
  const body = {
    model: getModel(), max_tokens: req.max_tokens, stream: true, system: req.system,
    messages: [{ role: 'user', content: structured ? req.prompt : `${req.prompt}\n\nأجب بكائن JSON واحد فقط يطابق هذا المخطط:\n${JSON.stringify(req.schema)}` }],
  };
  if (structured) body.output_config = { format: { type: 'json_schema', schema: req.schema } };
  let res;
  try {
    res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': getKey(), 'anthropic-version': '2023-06-01',
        'anthropic-dangerous-direct-browser-access': 'true' },
      body: JSON.stringify(body),
    });
  } catch {
    throw new AiError('تعذر الوصول إلى Claude. تحقق من الاتصال بالإنترنت.');
  }
  if (!res.ok) {
    let err = null;
    try { err = await res.json(); } catch { /* not JSON */ }
    const e = new AiError(explain(res.status, err));
    e.status = res.status;
    e.raw = err?.error?.message || '';
    throw e;
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  let text = '';
  let stop = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const line = chunk.split('\n').find((l) => l.startsWith('data:'));
      if (!line) continue;
      let ev;
      try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
      if (ev.type === 'content_block_delta' && ev.delta?.type === 'text_delta') { text += ev.delta.text; if (onText) onText(ev.delta.text.length); }
      else if (ev.type === 'message_delta' && ev.delta?.stop_reason) stop = ev.delta.stop_reason;
      else if (ev.type === 'error') throw new AiError(explain(ev.error?.type === 'overloaded_error' ? 529 : 500, ev));
    }
  }
  if (stop === 'refusal') throw new AiError('اعتذر Claude عن كتابة هذا المحتوى.');
  if (stop === 'max_tokens') throw new AiError('انقطعت الكتابة قبل اكتمالها. جرّب مستوى تفصيل أقل.');
  const clean = text.trim().replace(/^```(?:json)?\s*|```$/g, '');
  try { return JSON.parse(clean); } catch { throw new AiError('وصل رد غير مكتمل من Claude.'); }
}

let structuredOk = true;
async function call(req, onText) {
  if (structuredOk) {
    try { return await stream(req, true, onText); } catch (e) {
      // older API versions/models without structured output: ask for JSON in the prompt instead
      if (!(e.status === 400 && /output_config|json_schema|format/i.test(e.raw || ''))) throw e;
      structuredOk = false;
    }
  }
  return stream(req, false, onText);
}

const pick = (obj, keys) => Object.fromEntries(keys.filter((k) => obj && k in obj).map((k) => [k, obj[k]]).concat(obj && 'cover_subtitle' in obj ? [['cover_subtitle', obj.cover_subtitle]] : []));

// Whole proposal: the creative core first, then the other sections in parallel (as on the server).
export async function writeProposal(backend, inputs, onText) {
  const one = await backend('POST', '/api/ai/request', { inputs });
  const first = one.requests[0];
  const core = pick(await call(first, onText), first.sections);
  const two = await backend('POST', '/api/ai/request', { inputs, concept: Object.fromEntries(first.sections.filter((k) => core[k]).map((k) => [k, core[k]])) });
  const parts = await Promise.allSettled(two.requests.map((r) => call(r, onText).then((c) => pick(c, r.sections))));
  const content = { ...core };
  parts.forEach((p) => { if (p.status === 'fulfilled') Object.assign(content, p.value); });
  return content;
}

export async function writeSection(backend, proposalId, sectionId, tone) {
  const r = await backend('POST', '/api/ai/request', { proposal_id: proposalId, section_id: sectionId, tone });
  if (!r.requests.length) return null;
  return call(r.requests[0]);
}

export async function testKey() {
  return call({ system: 'أجب بكائن JSON فقط.', prompt: 'اكتب كلمة: تم', max_tokens: 50,
    schema: { type: 'object', properties: { ok: { type: 'string' } }, required: ['ok'], additionalProperties: false } });
}
