// Immagini nelle note: Rust le salva in images/ accanto alla nota e le serve con il protocollo qnfile, solo
// se sono immagini vere dentro la cartella delle note. Nel testo resta il tag Markdown standard ![](images/…).
import { invoke } from '@tauri-apps/api/core';
import { Facet } from '@codemirror/state';

// Su Windows Tauri espone i protocolli dell'app come http://<nome>.localhost.
const ORIGIN = /Windows|Android/.test(navigator.userAgent) ? 'http://qnfile.localhost/' : 'qnfile://localhost/';

// Sopra questa dimensione si chiede prima di salvare.
const LARGE = 10 * 1024 * 1024;

// Il percorso della nota nella cartella delle note (2026/11/nota.md): le immagini sono relative a lei.
export const notePathFacet = Facet.define({ combine: (values) => values[0] ?? '' });

// L'indirizzo da cui la pagina carica un'immagine citata nella nota, oppure null: indirizzi web, percorsi
// assoluti e percorsi che escono dalla cartella delle note non si caricano.
export function imageUrl(notePath, src) {
  if (!notePath || !src) return null;
  let path = src.trim().replace(/^<(.*)>$/, '$1');
  if (/^[a-z][\w+.-]*:/i.test(path) || /^[\\/]/.test(path)) return null;
  try {
    path = decodeURI(path);
  } catch {
    // Un % isolato nel nome: si usa com'è.
  }
  const parts = [];
  for (const seg of (notePath.replace(/[^/]*$/, '') + path).split(/[\\/]/)) {
    if (!seg || seg === '.') continue;
    if (seg !== '..') parts.push(seg);
    else if (!parts.pop()) return null;
  }
  return ORIGIN + parts.map(encodeURIComponent).join('/');
}

// Le immagini negli appunti o in un trascinamento. Incollando, se ci sono anche testo semplice (una tabella
// copiata da Word, per esempio) vince il testo: l'immagine è solo una sua copia.
export function imagesIn(data, pasting) {
  if (!data) return [];
  if (pasting && data.getData('text/plain')) return [];
  return [...data.items].filter((i) => i.kind === 'file' && i.type.startsWith('image/')).map((i) => i.getAsFile()).filter(Boolean);
}

// Salva le immagini una dopo l'altra e restituisce i tag Markdown da inserire. Un'immagine grande chiede
// conferma; una rifiutata da Rust viene segnalata con `onError` e saltata.
export async function saveImages(noteId, files, onError) {
  const tags = [];
  for (const file of files) {
    const mb = (file.size / 1024 / 1024).toFixed(1);
    if (file.size > LARGE && !confirm(`L'immagine pesa ${mb} MB. Salvarla accanto alla nota?`)) continue;
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const rel = await invoke('save_image', bytes, { headers: { 'x-note': encodeURIComponent(noteId) } });
      tags.push(`![](${rel})`);
    } catch (e) {
      onError(`Immagine non salvata: ${e}`);
    }
  }
  return tags;
}
