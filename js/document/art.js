// Decorative artwork for the four proposal designs: waves, rings, geometric shapes, soft glows.
// Everything is inline SVG sized to the page (16:9 or A4), drawn behind the content, so it prints
// sharply and needs no image files. scripts/build_deco.py renders the same art to PNG for PowerPoint.
import { icon } from '../lib/icons.js';

const C = { purple: '#4C0192', deep: '#2B0560', mid: '#6A1FB0', accent: '#B77BFF', lilac: '#EAE1F8', lilac2: '#D9C8F3', gold: '#D8B26A', white: '#FFFFFF' };
let uid = 0;

// filled wave from height y down to the bottom edge
function wave(W, H, y, amp, shift, fill, op) {
  const k = W / 4;
  const s = shift * k;
  return `<path d="M0 ${y} C ${k * 0.6 + s} ${y - amp}, ${k * 1.4 + s} ${y + amp}, ${k * 2} ${y} S ${k * 3.4 - s} ${y - amp * 1.1}, ${W} ${y + amp * 0.4} L ${W} ${H} L 0 ${H} Z" fill="${fill}" fill-opacity="${op}"/>`;
}

function lines(W, y0, n, gap, color, op0, wgt = 1.4) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const y = y0 + i * gap;
    out.push(`<path d="M-20 ${y} C ${W * 0.2} ${y - 90 + i * 6}, ${W * 0.4} ${y + 110 - i * 4}, ${W * 0.64} ${y - 10} S ${W * 0.92} ${y - 120 + i * 8}, ${W + 40} ${y - 40}" stroke="${color}" stroke-opacity="${(op0 + i * 0.03).toFixed(3)}" stroke-width="${wgt}" fill="none"/>`);
  }
  return out.join('');
}

function rings(cx, cy, r0, step, n, color, op, wgt = 1.2) {
  let out = '';
  for (let i = 0; i < n; i++) out += `<circle cx="${cx}" cy="${cy}" r="${r0 + i * step}" fill="none" stroke="${color}" stroke-opacity="${(op * (1 - i / (n + 1))).toFixed(3)}" stroke-width="${wgt}"/>`;
  return out;
}

function dots(x, y, cols, rows, gap, r, color, op) {
  let out = '';
  for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) out += `<circle cx="${x + i * gap}" cy="${y + j * gap}" r="${r}" fill="${color}" fill-opacity="${op}"/>`;
  return out;
}

function glow(cx, cy, r, color, op) {
  const id = `g${++uid}`;
  return `<defs><radialGradient id="${id}"><stop offset="0" stop-color="${color}" stop-opacity="${op}"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></radialGradient></defs><circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#${id})"/>`;
}

function stars(W, H, n, color, seed) {
  let out = '';
  let x = seed;
  const rnd = () => { x = (x * 9301 + 49297) % 233280; return x / 233280; };
  for (let i = 0; i < n; i++) out += `<circle cx="${(rnd() * W).toFixed(0)}" cy="${(rnd() * H).toFixed(0)}" r="${(0.8 + rnd() * 1.6).toFixed(1)}" fill="${color}" fill-opacity="${(0.25 + rnd() * 0.5).toFixed(2)}"/>`;
  return out;
}

function svg(W, H, body, cls = 'pg-art') {
  return `<svg class="${cls}" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">${body}</svg>`;
}

// kind: cover | divider | content | closing ; ctx: { layout, icon }
export function art(design, kind, ctx = {}) {
  const portrait = ctx.layout === 'portrait';
  const W = portrait ? 794 : 1280;
  const H = portrait ? 1123 : 720;
  const big = kind !== 'content';
  const mark = (color, op) => (ctx.icon && kind === 'content'
    ? `<g transform="translate(${portrait ? 40 : 56} ${H - (portrait ? 300 : 250)})" opacity="${op}" color="${color}">${icon(ctx.icon, 200).replace('stroke-width="1.8"', 'stroke-width="0.8"')}</g>` : '');
  const ic = ctx.icon && kind === 'divider' ? `<g transform="translate(${portrait ? 60 : 90} ${H / 2 - 170}) " opacity=".10" color="#fff">${icon(ctx.icon, 340).replace('stroke-width="1.8"', 'stroke-width="0.9"')}</g>` : '';

  if (design === 'night') {
    if (big) {
      return svg(W, H, glow(W * 0.5, H * 0.45, W * 0.45, '#5B2BB5', 0.55) + stars(W, H, 60, C.gold, kind.length * 97)
        + rings(-40, H + 40, 120, 38, 8, C.gold, 0.5) + rings(W + 30, -30, 90, 34, 7, C.gold, 0.45)
        + `<path d="M${W * 0.12} ${H * 0.86} Q ${W * 0.5} ${H * 0.66} ${W * 0.88} ${H * 0.86}" stroke="${C.gold}" stroke-opacity=".35" stroke-width="1.2" fill="none"/>`
        + `<path d="M${W * 0.18} ${H * 0.9} Q ${W * 0.5} ${H * 0.74} ${W * 0.82} ${H * 0.9}" stroke="${C.gold}" stroke-opacity=".2" stroke-width="1" fill="none"/>` + ic);
    }
    return svg(W, H, glow(W, 0, W * 0.4, '#3B2C8F', 0.4) + rings(-60, H + 60, 110, 30, 6, C.gold, 0.28) + stars(W, H * 0.2, 14, C.gold, 7) + mark(C.gold, 0.07));
  }

  if (design === 'bold') {
    if (big) {
      return svg(W, H, `<circle cx="${W * 0.2}" cy="${H * 0.52}" r="${H * 0.36}" fill="${C.white}" fill-opacity=".07"/>`
        + `<circle cx="${W * 0.2}" cy="${H * 0.52}" r="${H * 0.46}" fill="none" stroke="${C.white}" stroke-opacity=".18" stroke-width="2"/>`
        + `<circle cx="${W * 0.06}" cy="${H * 0.12}" r="${H * 0.08}" fill="${C.accent}" fill-opacity=".55"/>`
        + dots(W * 0.32, H * 0.08, 6, 4, 22, 3, C.white, 0.35)
        + `<g stroke="${C.white}" stroke-opacity=".12" stroke-width="16">${[0, 1, 2, 3, 4].map((i) => `<line x1="${W * 0.62 + i * 46}" y1="${H + 20}" x2="${W * 0.82 + i * 46}" y2="${H * 0.72}"/>`).join('')}</g>` + ic);
    }
    return svg(W, H, `<rect x="${W - 10}" y="0" width="10" height="${H}" fill="${C.purple}"/>`
      + `<g stroke="${C.purple}" stroke-opacity=".07" stroke-width="10">${[0, 1, 2, 3].map((i) => `<line x1="${-20 + i * 30}" y1="${H + 10}" x2="${70 + i * 30}" y2="${H - 90}"/>`).join('')}</g>`
      + dots(W - 190, H - 92, 6, 3, 18, 2.4, C.purple, 0.14) + mark(C.purple, 0.05));
  }

  if (design === 'minimal') {
    if (big) {
      return svg(W, H, glow(W * 0.92, H * 0.08, W * 0.36, C.accent, 0.5) + glow(W * 0.06, H * 0.96, W * 0.34, '#C9A8F5', 0.55)
        + rings(W * 0.92, H * 0.08, 70, 26, 5, C.purple, 0.12, 1) + lines(W, H * 0.62, 4, 16, C.purple, 0.16, 1.1) + (kind === 'divider' ? ic.replace('color="#fff"', `color="${C.purple}"`).replace('opacity=".10"', 'opacity=".06"') : ''));
    }
    return svg(W, H, glow(W * 0.97, 0, W * 0.22, C.accent, 0.22) + lines(W, H - 46, 2, 12, C.purple, 0.12, 1) + mark(C.purple, 0.05));
  }

  // ahdaf (classic): flowing lines, layered waves, the brand glow
  if (big) {
    return svg(W, H, glow(W * 0.85, 0, W * 0.5, '#8A3FE0', 0.55) + lines(W, H * 0.3, 9, 26, C.accent, 0.16)
      + wave(W, H, H * 0.82, 26, 0, C.white, 0.05) + wave(W, H, H * 0.88, 20, 1, C.white, 0.06) + wave(W, H, H * 0.93, 14, 2, C.accent, 0.12) + ic);
  }
  return svg(W, H, glow(W, 0, W * 0.2, C.accent, 0.16) + wave(W, H, H - 56, 14, 0, C.lilac, 0.75) + wave(W, H, H - 38, 11, 1, C.lilac2, 0.55)
    + wave(W, H, H - 22, 8, 2, C.accent, 0.22) + mark(C.purple, 0.05));
}

// Per-design layout: where titles sit (start = right in Arabic, or centred)
export const ALIGN = { ahdaf: 'start', night: 'center', bold: 'start', minimal: 'center' };
