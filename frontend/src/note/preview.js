// Anteprima della nota. L'HTML generato da marked passa sempre da DOMPurify: le note possono arrivare
// da Claude o da una cartella sincronizzata, e la pagina può chiamare i comandi dell'app.
import DOMPurify from 'dompurify';
import { Marked } from 'marked';
import { LanguageDescription } from '@codemirror/language';
import { languages } from '@codemirror/language-data';
import { classHighlighter, highlightCode } from '@lezer/highlight';
import { ALERT_LABELS, DECISION, DONE, DUE, MENTION, PRIO, SCHEDULED, TAG, WIKI, alertIcon, dueLabel, prioArrow, prioName, statusLabel, statusOfMark } from './editor/rules.js';
import { imageUrl } from './images.js';
import './preview.css';

const escapeHtml = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

// La lingua dei blocchi di codice resta in un attributo data-, perché le classi della nota vengono tolte.
const md = new Marked({
  gfm: true,
  breaks: true,
  renderer: {
    code({ text, lang }) {
      const name = (lang ?? '').trim().split(/\s+/)[0];
      return `<pre${name ? ` data-lang="${escapeHtml(name)}"` : ''}><code>${escapeHtml(text)}</code></pre>\n`;
    },
  },
});

// Niente stili, classi o id dalla nota: non devono poter imitare i controlli dell'app.
const PURIFY = {
  FORBID_TAGS: ['style', 'form', 'button', 'textarea', 'select', 'option', 'iframe', 'object', 'embed', 'audio', 'video', 'source', 'svg', 'math', 'dialog'],
  FORBID_ATTR: ['style', 'class', 'id', 'name', 'for', 'form', 'srcset'],
  RETURN_DOM_FRAGMENT: true,
};

// Un <img> comincia a caricare appena entra nella pagina, anche se non è ancora mostrato. L'indirizzo
// passa quindi in un attributo inerte già durante la sanificazione, e `decorate` lo rimette solo per le
// immagini della cartella delle note: nessuna richiesta parte verso il web o verso indirizzi sbagliati.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.nodeName !== 'IMG' || !node.hasAttribute('src')) return;
  node.setAttribute('data-src', node.getAttribute('src'));
  node.removeAttribute('src');
});

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
  add(SCHEDULED, 'sched');
  add(DONE, 'done');
  add(PRIO, 'prio');
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
      const s = el('span', 'pv-tag tag-chip', m[0]);
      s.dataset.tag = m[1];
      s.style.color = ctx.tagColor(m[1]);
      frag.append(s);
    } else if (kind === 'due') {
      const { label, level } = dueLabel(m[1]);
      frag.append(el('span', `pv-due ${level}`, label));
    } else if (kind === 'sched') {
      const { label, level } = dueLabel(m[1]);
      const s = el('span', `pv-due pv-sched ${level}`, label);
      s.title = `Da fare ${label}`;
      frag.append(s);
    } else if (kind === 'prio') {
      const p = prioName(m[1]);
      frag.append(el('span', `pv-prio ${p}`, `${prioArrow(p)} ${p}`));
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
    const title = el('p', 'pv-alert-title');
    title.append(alertIcon(kind), ALERT_LABELS[kind]);
    box.append(title, ...bq.childNodes);
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

  // [/] [w] [?] [-]: marked li lascia come testo. Diventano un segno come le caselle.
  for (const li of root.querySelectorAll('li')) {
    const p = li.firstElementChild?.tagName === 'P' && li.firstChild === li.firstElementChild ? li.firstElementChild : li;
    const first = p.firstChild;
    const m = first?.nodeType === Node.TEXT_NODE ? /^\[([/wW?-])\]\s+/.exec(first.data) : null;
    if (!m) continue;
    const status = statusOfMark(m[1]);
    first.data = first.data.slice(m[0].length);
    const mark = el('span', `pv-status pv-status-${status}`, { doing: '◐', waiting: '◷', question: '?', cancelled: '–' }[status]);
    mark.setAttribute('role', 'img');
    mark.setAttribute('aria-label', statusLabel(status));
    mark.title = statusLabel(status);
    p.prepend(mark);
    li.classList.add('pv-task', `pv-task-${status}`, ...(status === 'cancelled' ? ['pv-task-done'] : []));
  }

  for (const a of root.querySelectorAll('a[href]')) {
    a.dataset.href = a.getAttribute('href');
    a.title = a.dataset.href;
    a.classList.add('pv-link');
  }

  // Immagini: solo quelle dentro la cartella delle note, servite da Python. Indirizzi web e file mancanti
  // lasciano un segnaposto con il nome.
  for (const img of root.querySelectorAll('img')) {
    const src = img.dataset.src ?? '';
    img.removeAttribute('data-src');
    const url = /^data:image\/(png|jpe?g|gif|webp);/i.test(src) ? src : imageUrl(ctx.notePath, src);
    if (!url) {
      img.replaceWith(el('span', 'pv-embed', img.alt || src));
      continue;
    }
    img.src = url;
    img.classList.add('pv-img');
    img.addEventListener('error', () => img.replaceWith(el('span', 'pv-embed', `Immagine mancante: ${img.alt || src}`)), { once: true });
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
export function renderMarkdown(text, tagColor, notePath = '') {
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
  decorate(root, { tagColor, notes, order, notePath });
  for (const pre of root.querySelectorAll('pre[data-lang]')) pre.prepend(el('span', 'pv-code-lang', pre.dataset.lang));
  highlightBlocks(root);
  return root;
}

// Colori della sintassi nei blocchi di codice, con le stesse grammatiche dell'editor. Le lingue si caricano
// solo quando servono; se una lingua non è nota il blocco resta in tinta unica.
async function highlightBlocks(root) {
  for (const pre of root.querySelectorAll('pre[data-lang]')) {
    const desc = LanguageDescription.matchLanguageName(languages, pre.dataset.lang, true);
    const code = pre.querySelector('code');
    if (!desc || !code) continue;
    try {
      const support = desc.support ?? (await desc.load());
      const text = code.textContent;
      const frag = document.createDocumentFragment();
      highlightCode(
        text,
        support.language.parser.parse(text),
        classHighlighter,
        (t, cls) => frag.append(cls ? el('span', cls, t) : t),
        () => frag.append('\n'),
      );
      code.replaceChildren(frag);
    } catch {
      // Lingua non disponibile: resta il testo semplice.
    }
  }
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
