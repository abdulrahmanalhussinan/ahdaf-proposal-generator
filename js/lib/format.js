export const MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'];

export function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Escaped text with [[placeholders]] highlighted as fields that still need input.
export function rich(value) {
  return esc(value).replace(/\[\[([^\]]+)\]\]/g, '<mark class="ph" title="حقل بحاجة إلى تعبئة">$1</mark>');
}

export const hasPlaceholder = (s) => /\[\[[^\]]+\]\]/.test(String(s ?? ''));

export function parseISO(s) {
  if (!s) return null;
  const [y, m, d] = String(s).slice(0, 10).split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(Date.UTC(y, m - 1, d));
}

export function addDays(date, n) {
  const d = new Date(date.getTime());
  d.setUTCDate(d.getUTCDate() + n);
  return d;
}

export function fmtDate(d, withYear = true) {
  if (!d) return '';
  const s = `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  return withYear ? `${s} ${d.getUTCFullYear()}` : s;
}

export function fmtISODate(iso) {
  return fmtDate(parseISO(iso));
}

export function toISO(d) {
  return d ? d.toISOString().slice(0, 10) : '';
}

export function relTime(iso) {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  const diff = (Date.now() - t) / 1000;
  if (diff < 60) return 'الآن';
  if (diff < 3600) return `قبل ${Math.round(diff / 60)} د`;
  if (diff < 86400) return `قبل ${Math.round(diff / 3600)} س`;
  if (diff < 86400 * 7) return `قبل ${Math.round(diff / 86400)} يوم`;
  const d = new Date(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function shortDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export const STATUS = {
  draft: { label: 'مسودة', tone: 'gray' },
  review: { label: 'قيد المراجعة', tone: 'amber' },
  sent: { label: 'مُرسل للعميل', tone: 'blue' },
  approved: { label: 'معتمد', tone: 'green' },
  rejected: { label: 'غير معتمد', tone: 'red' },
};

export function weekLabel(offset, days) {
  const w1 = Math.floor(offset / 7) + 1;
  const w2 = Math.floor((offset + days - 1) / 7) + 1;
  return w1 === w2 ? `الأسبوع ${w1}` : `الأسبوع ${w1} – ${w2}`;
}

export function durationLabel(days) {
  if (days <= 0) return '';
  if (days === 1) return 'يوم';
  if (days === 2) return 'يومان';
  if (days <= 10) return `${days} أيام`;
  return `${days} يومًا`;
}

export function pad2(n) {
  return String(n).padStart(2, '0');
}
