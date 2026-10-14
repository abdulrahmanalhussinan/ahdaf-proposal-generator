// Block → HTML. Every block type can be rendered whole or as a slice of its items, which is
// what lets the paginator split long tables and lists across pages.
import { icon } from '../lib/icons.js';
import { esc, rich, parseISO, addDays, fmtDate, durationLabel, MONTHS } from '../lib/format.js';

// Which array a block is split on, and the minimum items to keep together.
export const SPLIT = {
  list: 'items', cards: 'items', objectives: 'items', phases: 'items', deliverables: 'rows', timeline: 'rows',
  team: 'members', kpis: 'items', risks: 'rows', table: 'rows', steps: 'items', services: 'entries', toc: 'items',
};

export function itemCount(block) {
  if (block.type === 'services') return flattenServices(block).length;
  const key = SPLIT[block.type];
  return key ? (block[key] || []).length : 0;
}

export function sliceBlock(block, from, to) {
  if (block.type === 'services') {
    return { ...block, _entries: flattenServices(block).slice(from, to), _offset: from };
  }
  const key = SPLIT[block.type];
  const all = block[key] || [];
  const part = { ...block, [key]: all.slice(from, to), _offset: (block._offset || 0) + from };
  if (block.type === 'timeline' && to < all.length) part._noMilestones = true; // milestones close the last chunk
  return part;
}

function flattenServices(block) {
  if (block._entries) return block._entries;
  const out = [];
  (block.groups || []).forEach((g, gi) => (g.items || []).forEach((it) => out.push({ gi, g, it })));
  return out;
}

const title = (block, cont) => (block.title && !cont ? `<h3 class="b-title">${rich(block.title)}</h3>` : '');
const lvlClass = (v) => (/مرتفع/.test(v) ? 'hi' : /متوسط/.test(v) ? 'md' : 'lo');

function cols(n, max) {
  return Math.max(1, Math.min(max, n));
}

export function renderBlock(block, ctx, cont = false) {
  const portrait = ctx.layout === 'portrait';
  const off = block._offset || 0;
  switch (block.type) {
    case 'lead':
      return `<p class="b-lead">${rich(block.text)}</p>`;
    case 'paragraph':
      return `<p class="b-par">${rich(block.text)}</p>`;
    case 'callout':
      return `<div class="b-callout"><span class="lbl">${esc(block.label || 'ملاحظة')}</span><div class="txt">${rich(block.text)}</div></div>`;
    case 'stats': {
      const items = block.items || [];
      return `<div>${title(block, cont)}<div class="b-stats" style="--n:${cols(items.length, portrait ? 2 : 4)}">${items
        .map((s) => `<div class="st"><div class="v">${esc(s.value)}</div><div class="l">${rich(s.label)}</div></div>`).join('')}</div>${block.note ? `<p class="b-par" style="font-size:var(--fs-xs);color:var(--muted);margin-top:6px">${rich(block.note)}</p>` : ''}</div>`;
    }
    case 'cards': {
      const items = block.items || [];
      const c = portrait ? Math.min(2, block.columns || 2) : block.columns || (items.length <= 4 ? 2 : 3);
      return `<div>${title(block, cont)}<div class="b-cards" style="--c:${c}">${items
        .map((it) => `<div class="card">${it.icon ? `<div class="ic">${icon(it.icon, 18)}</div>` : ''}<h4>${rich(it.title)}</h4><p>${rich(it.text)}</p></div>`).join('')}</div></div>`;
    }
    case 'list': {
      const items = block.items || [];
      const two = !portrait && items.length > 5 && items.every((x) => String(x).length < 140);
      return `<div class="b-list ${block.style || ''} ${two ? 'two' : ''}">${title(block, cont)}<ul>${items.map((x) => `<li>${rich(x)}</li>`).join('')}</ul></div>`;
    }
    case 'objectives': {
      const items = block.items || [];
      return `<div class="b-obj" style="--c:${portrait ? 1 : 2}">${items.map((o, i) => `
        <div class="obj"><div class="top"><span class="n">${off + i + 1}</span><h4>${rich(o.title)}</h4></div>
        <p>${rich(o.text)}</p>
        <div class="meta">${o.measure ? `<span>يُقاس بـ: <b>${rich(o.measure)}</b></span>` : ''}<span>المستهدف: <span class="tgt">${rich(o.target || 'يُحدد مع العميل')}</span></span></div></div>`).join('')}</div>`;
    }
    case 'services': {
      const entries = flattenServices(block);
      const groups = [];
      entries.forEach((e) => {
        const last = groups[groups.length - 1];
        if (last && last.gi === e.gi) last.items.push(e.it);
        else groups.push({ gi: e.gi, g: e.g, items: [e.it] });
      });
      const c = portrait ? 1 : groups.length === 4 ? 4 : cols(groups.length, 3);
      return `<div class="b-svc" style="--c:${c}">${groups.map((gr) => `
        <div class="svc"><div class="svc-h"><span class="ic">${icon(gr.g.icon || 'spark', 18)}</span>${rich(gr.g.title)}</div>
        <ul>${gr.items.map((it) => `<li><b>${rich(it.title)}</b>${it.text ? `<span>${rich(it.text)}</span>` : ''}</li>`).join('')}</ul></div>`).join('')}</div>`;
    }
    case 'phases': {
      const items = block.items || [];
      return `<div class="b-phases">${items.map((p, i) => `
        <div class="ph-row"><div class="ph-n">${String(off + i + 1).padStart(2, '0')}</div>
          <div class="ph-t"><h4>${rich(p.title)}</h4>${p.period ? `<span class="per">${rich(p.period)}</span>` : ''}${p.goal ? `<p>${rich(p.goal)}</p>` : ''}</div>
          <div class="ph-acts"><ul>${(p.activities || []).map((a) => `<li>${rich(a)}</li>`).join('')}</ul></div>
          <div class="ph-out">${(p.outputs || []).length ? `<span class="lbl">المخرجات</span>${p.outputs.map((o) => `<span class="chip">${rich(o)}</span>`).join('')}` : ''}</div>
        </div>`).join('')}</div>`;
    }
    case 'deliverables': {
      const rows = block.rows || [];
      return `<table class="tbl"><thead><tr><th class="num">#</th><th>المخرج</th><th>الوصف</th><th class="num">الكمية</th><th>الوحدة</th><th>التوقيت</th></tr></thead><tbody>${rows
        .map((r, i) => `<tr><td class="num muted">${off + i + 1}</td><td class="strong">${rich(r.title)}</td><td>${rich(r.description)}</td>
        <td class="num"><span class="qty">${r.qty === null || r.qty === undefined || r.qty === '' ? '<mark class="ph">يُحدد</mark>' : esc(r.qty)}</span></td><td>${rich(r.unit)}</td><td class="muted">${rich(r.timing)}</td></tr>`).join('')}</tbody></table>`;
    }
    case 'kpis': {
      const items = block.items || [];
      if (portrait) {
        return `<table class="tbl"><thead><tr><th>المؤشر</th><th>التعريف وطريقة القياس</th><th>المستهدف</th></tr></thead><tbody>${items
          .map((k) => `<tr><td class="strong">${rich(k.name)}${k.name_en ? `<span class="en">${esc(k.name_en)}</span>` : ''}</td><td>${rich(k.definition)}<br><span style="color:var(--muted)">${rich(k.measurement)} · ${rich(k.frequency)}</span></td><td>${rich(k.target)}</td></tr>`).join('')}</tbody></table>`;
      }
      return `<table class="tbl"><thead><tr><th>المؤشر</th><th>التعريف</th><th>أداة القياس</th><th>الدورية</th><th>المستهدف</th></tr></thead><tbody>${items
        .map((k) => `<tr><td class="strong" style="width:18%">${rich(k.name)}${k.name_en ? `<span class="en">${esc(k.name_en)}</span>` : ''}</td><td>${rich(k.definition)}</td><td class="muted" style="width:17%">${rich(k.measurement)}</td><td class="muted" style="width:11%">${rich(k.frequency)}</td><td style="width:15%"><b style="color:var(--b)">${rich(k.target)}</b></td></tr>`).join('')}</tbody></table>`;
    }
    case 'risks': {
      const rows = block.rows || [];
      return `<table class="tbl"><thead><tr><th>الخطر</th><th class="num">الاحتمالية</th><th class="num">التأثير</th><th>آلية المعالجة</th></tr></thead><tbody>${rows
        .map((r) => `<tr><td class="strong" style="width:30%">${rich(r.risk)}</td><td class="num"><span class="lvl ${lvlClass(r.likelihood)}">${esc(r.likelihood)}</span></td><td class="num"><span class="lvl ${lvlClass(r.impact)}">${esc(r.impact)}</span></td><td>${rich(r.mitigation)}</td></tr>`).join('')}</tbody></table>`;
    }
    case 'table': {
      const columns = block.columns || [];
      const rows = block.rows || [];
      return `<div>${title(block, cont)}<table class="tbl"><thead><tr>${columns.map((c) => `<th>${esc(c.label)}</th>`).join('')}</tr></thead><tbody>${rows
        .map((r) => `<tr>${columns.map((c, ci) => `<td class="${ci === 0 ? 'strong' : ''}">${rich(r[c.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    }
    case 'team': {
      const members = block.members || [];
      const c = portrait ? 2 : cols(members.length, 3);
      return `<div class="b-team" style="--c:${c}">${members.map((m) => `
        <div class="tm"><div class="hd"><span class="av">${icon('users', 18)}</span><div><h4>${rich(m.role)}</h4>${m.role_en ? `<div class="en">${esc(m.role_en)}</div>` : ''}</div>${Number(m.count) > 1 ? `<span class="cnt">×${esc(m.count)}</span>` : ''}</div>
        ${(m.responsibilities || []).length ? `<ul>${m.responsibilities.map((r) => `<li>${rich(r)}</li>`).join('')}</ul>` : ''}</div>`).join('')}</div>`;
    }
    case 'steps': {
      const items = block.items || [];
      return `<div>${title(block, cont)}<div class="b-steps" style="--c:${portrait ? 2 : cols(items.length, 4)}">${items
        .map((s, i) => `<div class="stp"><span class="n">${String(off + i + 1).padStart(2, '0')}</span><h4>${rich(s.title)}</h4><p>${rich(s.text)}</p></div>`).join('')}</div></div>`;
    }
    case 'image':
      return block.src ? `<div class="b-image"><figure><img src="${esc(block.src)}" alt="">${block.caption ? `<figcaption>${rich(block.caption)}</figcaption>` : ''}</figure></div>` : '';
    case 'timeline':
      return renderGantt(block, ctx, cont);
    case 'toc': {
      const items = block.items || [];
      return `<div class="b-toc ${items.length > 12 ? 'dense' : ''}" style="--c:${portrait ? 2 : items.length > 16 ? 5 : 4}">${items
        .map((t) => `<div class="toc"><span class="n">${esc(t.num)}</span><h4>${rich(t.title)}</h4>${t.sub ? `<p>${rich(t.sub)}</p>` : ''}</div>`).join('')}</div>`;
    }
    default:
      return '';
  }
}

// ---------------------------------------------------------------- Gantt
function renderGantt(block, ctx) {
  const total = Math.max(1, Number(block.total_days) || 1);
  const start = parseISO(block.start_date);
  const rows = block.rows || [];
  const pct = (d) => `${Math.max(0, Math.min(100, (d / total) * 100)).toFixed(3)}%`;

  // scale ticks: weeks for short projects, months for long ones
  const ticks = [];
  if (total <= 70) {
    for (let d = 0; d < total; d += 7) ticks.push({ at: d, label: `أ${Math.floor(d / 7) + 1}` });
  } else {
    for (let m = 0; m * 30.4 < total; m++) {
      const at = Math.round(m * 30.4);
      const label = start ? MONTHS[addDays(start, at).getUTCMonth()] : `ش${m + 1}`;
      ticks.push({ at, label });
    }
  }
  const tickW = total <= 70 ? 7 : 30.4;
  const grid = ticks.slice(1).map((t) => `<i class="g-tick" style="inset-inline-start:${pct(t.at)}"></i>`).join('');

  const dates = (r) => {
    if (start) {
      const s = addDays(start, r.offset);
      const e = addDays(start, r.offset + Math.max(1, r.days) - 1);
      return { s: fmtDate(s, false), e: fmtDate(e, false) };
    }
    const w1 = Math.floor(r.offset / 7) + 1;
    const w2 = Math.floor((r.offset + Math.max(1, r.days) - 1) / 7) + 1;
    return { s: `أسبوع ${w1}`, e: `أسبوع ${w2}` };
  };

  let lastPhase = null;
  const body = rows.map((r, i) => {
    const d = dates(r);
    const showPhase = r.phase !== lastPhase || i === 0;
    lastPhase = r.phase;
    const alt = (block._altIndex || 0) % 2;
    return `<div class="g-row">
      <div class="g-lbl">${showPhase ? `<span class="phn">${rich(r.phase)}</span>` : ''}<span class="act">${rich(r.activity)}</span><span class="dts">${esc(d.s)} – ${esc(d.e)}</span></div>
      <div class="g-dates"><b>${esc(d.s)}</b> – <b>${esc(d.e)}</b> · ${esc(durationLabel(Math.max(1, r.days)))}</div>
      <div class="g-own">${rich(r.owner)}</div>
      <div class="g-track">${grid}<div class="g-bar ${alt ? 'alt' : ''}" style="inset-inline-start:${pct(r.offset)};width:${pct(Math.max(1, r.days))}"></div></div>
    </div>`;
  }).join('');

  const ms = (block.milestones || []).filter((m) => m.offset >= 0 && m.offset <= total);
  const msRow = ms.length && !block._noMilestones ? `<div class="g-row g-ms"><div class="g-lbl">المحطات الرئيسية</div><div class="g-dates"></div><div class="g-own"></div>
      <div class="g-track">${grid}${ms.map((m) => `<span class="g-dia" title="${esc(m.label)}" style="inset-inline-start:${pct(m.offset)}"></span>`).join('')}</div></div>` : '';
  const legend = ms.length && !block._noMilestones ? `<div class="g-legend">${ms.map((m) => `<span>${rich(m.label)}${start ? ` (${esc(fmtDate(addDays(start, m.offset), false))})` : ''}</span>`).join('')}</div>` : '';

  return `<div class="gantt"><div class="g-row g-head"><div>المرحلة / النشاط</div><div class="g-dates" style="color:#fff">البداية – النهاية · المدة</div><div>المسؤول</div>
    <div class="g-scale">${ticks.filter((t) => t.at + tickW / 2 <= total).map((t) => `<span style="inset-inline-start:${pct(t.at + tickW / 2)}">${esc(t.label)}</span>`).join('')}</div></div>${body}${msRow}${legend}</div>`;
}
