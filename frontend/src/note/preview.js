// Anteprima della nota. L'HTML generato da marked passa sempre da DOMPurify: le note possono arrivare
// da Claude o da una cartella sincronizzata, e la pagina può chiamare i comandi dell'app.
import DOMPurify from 'dompurify';
import { Marked } from 'marked';
import { ALERT_LABELS, DECISION, DONE, DUE, MENTION, TAG, WIKI, dueLabel } from './editor/rules.js';
import './preview.css';

const md = new Marked({ gfm: true, breaks: true });

// Niente stili, classi o id dalla nota: non devono poter imitare i controlli dell'app.
const PURIFY = {
  FORBID_TAGS: ['style', 'form', 'button', 'textarea', 'select', 'option', 'iframe', 'object', 'embed', 'audio', 'video', 'source', 'svg', 'math', 'dialog', 'details', 'summary'],
  FORBID_ATTR: ['style', 'class', 'id', 'name', 'for', 'form'],
  RETURN_DOM_FRAGMENT: true,
};

const ALERT = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/i;
const FENCE = /^\s*(```|~~~)/;
const FOOTNOTE_DEF = /^\[\^([^\]\s]+)\]:\s?(.*)$/;
const FOOTNOTE_REF = /\[\^([^\]\s]+)\]/g;
const SKIP = new Set(['CODE', 'PRE', 'A']);

// Toglie le definizioni delle note a piè di pagina e protegge il | dei [[link|Titolo]] nelle tabelle.
function prepare(text) {
  const notes = new Map();
  const out = [];
  let fence = false;
  for (const line of text.split('\n')) {
    if (FENCE.test(line)) fence = !fence;
    if (!fence) {
      const fn = FOOTNOTE_DEF.exec(line);
      if (fn) {
        notes.set(fn[1], fn[2]);
        continue;
      }
      if (/^\s*\|/.test(line)) {
        out.push(line.replace(WIKI, (m) => m.replace('|', '\\|')));
        continue;
      }
    }
    out.push(line);
  }
  return { source: out.join('\n'), notes };
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

// Le stesse regole dell'editor sul testo semplice, fuori da codice e link.
function inlineParts(text, ctx) {
  const found = [];
  const add = (re, kind) => {
    for (const m of text.matchAll(re)) found.push({ kind, m, from: m.index, to: m.index + m[0].length });
  };
  add(WIKI, 'wiki');
  add(FOOTNOTE_REF, 'fn');
  add(MENTION, 'person');
  add(TAG, 'tag');
  add(DUE, 'due');
  add(DONE, 'done');
  add(DECISION, 'decision');
  if (!found.length) return null;
  found.sort((a, b) => a.from - b.from);

  const frag = document.createDocumentFragment();
  let at = 0;
  for (const { kind, m, from, to } of found) {
    if (from < at) continue;
    if (kind === 'fn' && !ctx.notes.has(m[1])) continue;
    frag.append(text.slice(at, from));
    at = to;
    if (kind === 'wiki') {
      const target = m[2].trim();
      if (m[1]) {
        frag.append(el('span', 'pv-embed', target));
      } else {
        const a = el('a', 'pv-wiki', (m[3] || m[2]).trim());
        a.href = '#';
        a.dataset.wiki = target;
        frag.append(a);
      }
    } else if (kind === 'fn') {
      const sup = el('sup', 'pv-fn-ref');
      const a = el('a', '', String(ctx.order.indexOf(m[1]) + 1));
      a.href = '#';
      a.dataset.fn = m[1];
      sup.append(a);
      frag.append(sup);
    } else if (kind === 'person') {
      const s = el('span', 'pv-mention', m[0]);
      s.dataset.person = m[1];
      frag.append(s);
    } else if (kind === 'tag') {
      const s = el('span', 'pv-tag', m[0]);
      s.dataset.tag = m[1];
      s.style.color = ctx.tagColor(m[1]);
      frag.append(s);
    } else if (kind === 'due') {
      const { label, level } = dueLabel(m[1]);
      frag.append(el('span', `pv-due ${level}`, label));
    } else if (kind === 'decision') {
      frag.append(el('span', 'pv-decision', '!decisione'));
    }
  }
  frag.append(text.slice(at));
  return frag;
}

function decorate(root, ctx) {
  for (const bq of root.querySelectorAll('blockquote')) {
    const p = bq.firstElementChild;
    const head = p?.tagName === 'P' ? p.firstChild : null;
    const m = head?.nodeType === Node.TEXT_NODE ? ALERT.exec(head.data) : null;
    if (!m) continue;
    const kind = m[1].toUpperCase();
    head.data = head.data.slice(m[0].length);
    if (!head.data) {
      head.remove();
      if (p.firstChild?.nodeName === 'BR') p.firstChild.remove();
    }
    if (!p.childNodes.length) p.remove();
    const box = el('div', `pv-alert pv-alert-${kind.toLowerCase()}`);
    box.setAttribute('role', 'note');
    box.append(el('p', 'pv-alert-title', ALERT_LABELS[kind]), ...bq.childNodes);
    bq.replaceWith(box);
  }

  for (const input of root.querySelectorAll('input')) {
    if (input.type !== 'checkbox') {
      input.remove();
      continue;
    }
    input.disabled = true;
    input.setAttribute('aria-label', input.checked ? 'Fatta' : 'Da fare');
    const li = input.closest('li');
    if (li) li.classList.add('pv-task', ...(input.checked ? ['pv-task-done'] : []));
  }

  for (const a of root.querySelectorAll('a[href]')) {
    a.dataset.href = a.getAttribute('href');
    a.title = a.dataset.href;
    a.classList.add('pv-link');
  }

  // Immagini e file collegati arriveranno con l'apertura sicura dei file: per ora resta il nome.
  for (const img of root.querySelectorAll('img')) {
    const src = img.getAttribute('src') ?? '';
    if (/^data:image\/(png|jpe?g|gif|webp);/i.test(src)) continue;
    img.replaceWith(el('span', 'pv-embed', img.alt || src));
  }

  const texts = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => {
      for (let p = n.parentNode; p && p !== root; p = p.parentNode) if (SKIP.has(p.nodeName)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  while (walker.nextNode()) texts.push(walker.currentNode);
  for (const t of texts) {
    const frag = inlineParts(t.data, ctx);
    if (frag) t.replaceWith(frag);
  }
}

// Restituisce un elemento con la nota già sanificata e decorata.
export function renderMarkdown(text, tagColor) {
  const { source, notes } = prepare(text);
  const root = document.createElement('div');
  root.append(DOMPurify.sanitize(md.parse(source), PURIFY));
  const order = [];
  for (const m of source.matchAll(FOOTNOTE_REF)) if (notes.has(m[1]) && !order.includes(m[1])) order.push(m[1]);
  if (order.length) {
    const section = el('section', 'pv-footnotes');
    section.setAttribute('aria-label', 'Note a piè di pagina');
    const ol = el('ol');
    for (const id of order) {
      const li = el('li');
      li.dataset.fnDef = id;
      li.append(DOMPurify.sanitize(md.parseInline(notes.get(id)), PURIFY));
      ol.append(li);
    }
    section.append(ol);
    root.append(section);
  }
  decorate(root, { tagColor, notes, order });
  return root;
}

// Clic nell'Anteprima: i [[link]] restano nell'app, gli altri passano da `onOpen`.
export function previewClick(e, root, onOpen) {
  const target = e.target.closest?.('[data-wiki],[data-person],[data-tag],[data-fn],[data-href]');
  if (!target) return;
  e.preventDefault();
  const d = target.dataset;
  if (d.wiki !== undefined) onOpen('wiki', d.wiki);
  else if (d.person) onOpen('person', d.person);
  else if (d.tag) onOpen('tag', d.tag);
  else if (d.fn) root.querySelector(`[data-fn-def="${CSS.escape(d.fn)}"]`)?.scrollIntoView({ block: 'nearest' });
  else if (d.href) onOpen('url', d.href);
}
