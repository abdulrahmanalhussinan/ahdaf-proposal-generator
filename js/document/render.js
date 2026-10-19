// Paginated proposal renderer. Builds fixed-size pages (16:9 or A4) and flows blocks into them,
// splitting tables/lists/cards across pages when they overflow. Used by the editor preview, the
// viewer and the headless print page that produces the PDF.
import { renderBlock, itemCount, sliceBlock } from './blocks.js';
import { logoSVG, markSVG } from '../lib/brand.js';
import { esc, rich, pad2 } from '../lib/format.js';
import { art, ALIGN } from './art.js';

const SECTION_ICON = {
  about: 'award', intro: 'text', understanding: 'eye', objectives: 'target', scope: 'layers', methodology: 'compass',
  deliverables: 'list', timeline: 'calendar', team: 'users', kpis: 'chart', governance: 'shield', assumptions: 'check',
  risks: 'alert', budget: 'briefcase', past_projects: 'folder', conclusion: 'flag', idea: 'spark', activations: 'rocket',
  celebrities: 'star', content_plan: 'pen', custom: 'list',
};

// The four proposal designs. Logo colours per surface; the rest of each design lives in document.css.
export const DESIGNS = {
  ahdaf: { name: 'أهداف الكلاسيكي', note: 'تموجات أهداف وإضاءة بنفسجية، والعناوين تبدأ من اليمين.', cover: '#fff', page: '#4C0192' },
  night: { name: 'الليلي الفاخر', note: 'داكن بدوائر ولمسات ذهبية، والعناوين في المنتصف؛ للفعاليات والعلامات الفاخرة.', cover: '#fff', page: '#fff' },
  bold: { name: 'العصري الجريء', note: 'أشكال هندسية وشريط عناوين قوي، والعناوين تبدأ من اليمين.', cover: '#fff', page: '#fff' },
  minimal: { name: 'الأبيض الأنيق', note: 'أبيض بإضاءات ليلكية وخطوط ناعمة، والعناوين في المنتصف؛ للجهات الرسمية.', cover: '#4C0192', page: '#4C0192' },
};
const designOf = (doc) => (DESIGNS[doc?.theme] ? doc.theme : 'ahdaf');

let fontsReady = null;
export function ensureFonts() {
  if (!fontsReady) {
    fontsReady = Promise.all(['400', '500', '700'].map((w) => document.fonts.load(`${w} 16px Saudi`, 'أهداف abc 123')))
      .then(() => document.fonts.ready).catch(() => null);
  }
  return fontsReady;
}

function preloadImages(urls) {
  return Promise.all([...new Set(urls.filter(Boolean))].map((src) => new Promise((resolve) => {
    const img = new Image();
    img.onload = img.onerror = () => resolve();
    img.src = src;
  })));
}

function el(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function visibleSections(doc) {
  return (doc.sections || []).filter((s) => s.visible !== false);
}

// ------------------------------------------------------------------ page builders
function coverPage(doc, ctx) {
  const c = doc.cover || {};
  const s = ctx.settings || {};
  const photo = c.image ? `<div class="pg-photo" style="background-image:url('${esc(c.image)}')"></div>` : '';
  const clientLogo = c.client_logo ? `<div class="client-pill"><img src="${esc(c.client_logo)}" alt=""></div>` : '<span></span>';
  const mark = ctx.design === 'night' ? '' : markSVG('#fff', ctx.layout === 'portrait' ? 520 : 600, 'deco-mark').replace('<svg ', '<svg style="left:-90px;bottom:-150px" ');
  return el(`<section class="pg pg--cover" data-kind="cover">${photo}
    ${art(ctx.design, 'cover', ctx)}${mark}
    <div class="cover-in">
      <div class="cover-top">${logoSVG(ctx.logoCover, 46)}${clientLogo}</div>
      <div class="cover-main"><span class="cover-kicker">${esc(c.kicker || 'عرض فني')}</span><h1>${rich(c.title)}</h1>${c.subtitle ? `<p>${rich(c.subtitle)}</p>` : ''}</div>
      <div class="cover-foot">
        <div><span>مقدم إلى</span><b>${rich(c.client)}</b></div>
        <div><span>مقدم من</span><b>${esc(c.prepared_by || s.company_name || '')}</b></div>
        <div><span>التاريخ</span><b>${esc(c.date || '')}</b></div>
        <div><span>النسخة</span><b>${esc(c.version || '1.0')}${ctx.number ? ` · ${esc(ctx.number)}` : ''}</b></div>
        <div class="site"><b>${esc(s.website || 'www.ahdaf.co')}</b><span>${esc(s.tagline || 'نربط الإبداع بالهدف')}</span></div>
      </div>
    </div></section>`);
}

function dividerPage(section, num, ctx) {
  const photo = section.image ? `<div class="pg-photo" style="background-image:url('${esc(section.image)}')"></div>` : '';
  const markPos = ctx.layout === 'portrait' ? 'left:-120px;bottom:-140px' : 'left:-80px;bottom:-160px';
  return el(`<section class="pg pg--divider" data-kind="divider" data-section="${esc(section.id)}">${photo}
    ${art(ctx.design, 'divider', { layout: ctx.layout, icon: section.image ? null : SECTION_ICON[section.type] })}
    ${section.image || ctx.design === 'night' ? '' : markSVG('#fff', 560, 'deco-mark').replace('<svg ', `<svg style="${markPos}" `)}
    <div class="div-logo">${logoSVG(ctx.logoCover, 30)}</div>
    <div class="div-in"><span class="div-num">${num}</span><h2>${rich(section.title)}</h2>${section.subtitle ? `<p>${rich(section.subtitle)}</p>` : ''}</div>
  </section>`);
}

function closingPage(ctx) {
  const s = ctx.settings || {};
  const contacts = [s.website, s.email, s.phone].filter(Boolean).map((x) => `<span>${esc(x)}</span>`).join('');
  return el(`<section class="pg pg--closing" data-kind="closing">${art(ctx.design, 'closing', ctx)}${ctx.design === 'night' ? '' : markSVG('#fff', 640, 'deco-mark').replace('<svg ', '<svg style="right:-160px;top:-180px" ')}
    <div class="close-in">${logoSVG(ctx.logoCover, 64)}<div class="tag">${esc(s.tagline || 'نربط الإبداع بالهدف')}</div><div class="bar"></div>
      <h2>شكرًا لكم</h2><p>${rich(ctx.closingLine || '')}</p>
      <div class="close-contacts">${contacts}${s.address ? `<span>${esc(s.address)}</span>` : ''}</div></div></section>`);
}

function contentPage(ctx, section, num, first) {
  const clientLogo = ctx.clientLogo ? `<img class="client-logo" src="${esc(ctx.clientLogo)}" alt=""><span class="sep"></span>` : '';
  const titleHtml = first
    ? `<div class="pg-title"><div class="pg-kicker">${esc(num)}${section.title_en ? ` · ${esc(section.title_en)}` : ''}</div><h2>${rich(section.title)}</h2>${section.subtitle ? `<p class="sub">${rich(section.subtitle)}</p>` : ''}</div>`
    : `<div class="pg-title cont"><h2>${rich(section.title)}<span>(تابع)</span></h2></div>`;
  const airy = ctx.design === 'ahdaf' && ['intro', 'conclusion'].includes(section.type) ? markSVG('#4C0192', 300, 'pg-deco') : '';
  const page = el(`<section class="pg pg--content ${ctx.tight ? 'tight' : ''}" data-kind="content" data-section="${esc(section.id)}">${art(ctx.design, 'content', { layout: ctx.layout, icon: first ? SECTION_ICON[section.type] : null })}${airy}
    <header class="pg-head">${titleHtml}<div class="pg-brand">${clientLogo}${logoSVG(ctx.logoPage, 30)}</div></header>
    <div class="pg-body"></div>
    <footer class="pg-foot"><span>${esc(ctx.footer)}</span><span class="num"></span></footer></section>`);
  return page;
}

// ------------------------------------------------------------------ pagination
function overflows(page) {
  const body = page.querySelector('.pg-body');
  return body.scrollHeight > body.clientHeight + 1;
}

function bodyOf(page) {
  return page.querySelector('.pg-body');
}

function splitSentences(text) {
  return String(text || '').split(/(?<=[.!؟?])\s+/).filter(Boolean);
}

function usedRatio(page) {
  const body = bodyOf(page);
  const kids = [...body.children];
  if (!kids.length) return 0;
  const gap = parseFloat(getComputedStyle(body).rowGap) || 0;
  const used = kids.reduce((n, k) => n + k.offsetHeight, 0) + gap * (kids.length - 1);
  return used / body.clientHeight;
}

// Flow a section; if it ends with a nearly empty page, retry with tighter spacing and keep
// whichever version uses fewer pages.
function flowSection(host, ctx, section, num) {
  const normal = flowSectionOnce(host, ctx, section, num);
  if (normal.length < 2 || ctx.tight || usedRatio(normal[normal.length - 1]) > 0.4) return normal;
  normal.forEach((p) => p.remove());
  const tight = flowSectionOnce(host, { ...ctx, tight: true }, section, num);
  if (tight.length < normal.length) return tight;
  tight.forEach((p) => p.remove());
  normal.forEach((p) => host.appendChild(p));
  return normal;
}

function flowSectionOnce(host, ctx, section, num) {
  let page = contentPage(ctx, section, num, true);
  host.appendChild(page);
  const pages = [page];

  const newPage = () => {
    page = contentPage(ctx, section, num, false);
    host.appendChild(page);
    pages.push(page);
  };

  const place = (block, cont, depth = 0) => {
    const html = renderBlock(block, ctx, cont);
    if (!html) return;
    const node = el(`<div class="blk" data-block="${esc(block.id || '')}">${html}</div>`);
    const body = bodyOf(page);
    body.appendChild(node);
    if (!overflows(page)) return;
    body.removeChild(node);
    const empty = body.children.length === 0;
    if (depth > 40) { body.appendChild(node); return; }

    // 1) split item-based blocks at the largest prefix that still fits
    const n = itemCount(block);
    if (n > 1) {
      let fit = 0;
      for (let k = 1; k < n; k++) {
        const probe = el(`<div class="blk">${renderBlock(sliceBlock(block, 0, k), ctx, cont)}</div>`);
        body.appendChild(probe);
        const ov = overflows(page);
        body.removeChild(probe);
        if (ov) break;
        fit = k;
      }
      const minKeep = empty ? 1 : Math.min(3, Math.ceil(n / 3)); // don't leave a stub of a short table/list behind
      if (fit >= minKeep) {
        body.appendChild(el(`<div class="blk" data-block="${esc(block.id || '')}">${renderBlock(sliceBlock(block, 0, fit), ctx, cont)}</div>`));
        newPage();
        place(sliceBlock(block, fit, n), true, depth + 1);
        return;
      }
    }
    // 2) split long paragraphs by sentence
    if ((block.type === 'paragraph' || block.type === 'lead') && !empty) {
      const parts = splitSentences(block.text);
      if (parts.length > 1) {
        let fit = 0;
        for (let k = 1; k < parts.length; k++) {
          const probe = el(`<div class="blk">${renderBlock({ ...block, text: parts.slice(0, k).join(' ') }, ctx)}</div>`);
          body.appendChild(probe);
          const ov = overflows(page);
          body.removeChild(probe);
          if (ov) break;
          fit = k;
        }
        if (fit >= 1) {
          body.appendChild(el(`<div class="blk">${renderBlock({ ...block, text: parts.slice(0, fit).join(' ') }, ctx)}</div>`));
          newPage();
          place({ ...block, text: parts.slice(fit).join(' ') }, true, depth + 1);
          return;
        }
      }
    }
    // 3) move the whole block to a fresh page (or keep it if the page is already empty)
    if (empty) { body.appendChild(node); return; }
    newPage();
    place(block, cont, depth + 1);
  };

  for (const block of section.blocks || []) place(block, false);
  if (section.image && !section.divider) {
    place({ id: `${section.id}-img`, type: 'image', src: section.image }, false);
  }
  return pages;
}

/**
 * Render the proposal into `host`.
 * options: { mode: 'screen'|'print', onlySection: id|null, scaleTo: px width|null, clean: bool }
 * Returns { pageCount, sectionStart: {sectionId: pageIndex} }
 */
export async function renderDocument(host, proposal, settings, options = {}) {
  const doc = proposal.doc || {};
  const layout = doc.layout === 'portrait' ? 'portrait' : 'landscape';
  await ensureFonts();
  const sections = visibleSections(doc);
  const imgs = [doc.cover?.image, doc.cover?.client_logo, ...sections.flatMap((s) => [s.image, ...(s.blocks || []).filter((b) => b.type === 'image').map((b) => b.src)])];
  await preloadImages(imgs);

  const design = designOf(doc);
  const ctx = {
    layout, design, settings: settings || {}, number: proposal.number,
    logoCover: DESIGNS[design].cover, logoPage: DESIGNS[design].page,
    clientLogo: doc.cover?.client_logo || null,
    footer: `عرض فني — ${(doc.cover?.title || '').replace(/\[\[|\]\]/g, '')}`,
    closingLine: `نتطلع إلى العمل مع ${(doc.cover?.client || '').replace(/\[\[|\]\]/g, '')} على مشروع «${(doc.cover?.title || '').replace(/\[\[|\]\]/g, '')}».`,
  };

  host.innerHTML = '';
  const root = document.createElement('div');
  root.className = `doc ${options.mode === 'print' ? 'print' : 'screen'} ${options.clean ? 'print-clean' : ''}`;
  root.dataset.layout = layout;
  root.dataset.theme = design;
  root.dataset.align = ALIGN[design] || 'start';
  root.style.visibility = 'hidden';
  host.appendChild(root);

  const sectionStart = {};
  const only = options.onlySection || null;

  if (!only || only === '__cover') {
    root.appendChild(coverPage(doc, ctx));
    if (!only && doc.show_toc !== false && sections.length > 2) {
      const tocSection = { id: '__toc', title: 'محتويات العرض', title_en: 'Contents', subtitle: '', blocks: [
        { id: 'toc', type: 'toc', items: sections.map((s, i) => ({ num: pad2(i + 1), title: s.title, sub: s.subtitle })) },
      ] };
      flowSection(root, ctx, tocSection, '');
    }
  }

  sections.forEach((section, i) => {
    if (only && only !== section.id) return;
    const num = pad2(i + 1);
    sectionStart[section.id] = root.children.length;
    if (section.divider) root.appendChild(dividerPage(section, num, ctx));
    flowSection(root, ctx, section, num);
  });

  if (!only && !options.noClosing) root.appendChild(closingPage(ctx));

  // page numbers (cover and closing pages carry none)
  [...root.children].forEach((pg, idx) => {
    const n = pg.querySelector('.pg-foot .num');
    if (n) n.textContent = pad2(idx + 1);
  });

  if (options.scaleTo) {
    const pw = layout === 'portrait' ? 794 : 1280;
    root.style.zoom = String(Math.min(1, options.scaleTo / pw));
  }
  root.style.visibility = '';
  return { pageCount: root.children.length, sectionStart, root };
}
