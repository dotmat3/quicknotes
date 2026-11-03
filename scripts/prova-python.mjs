// Prova dal vivo dell'app: avvia QuickNotes su note di prova, la guida via
// CDP e controlla scrittura, salvataggio su disco, comandi, modifiche esterne, immagini e chiusura.
// Uso: node scripts/prova-python.mjs [foto.png]   (prima: cd frontend && npm run build)
// Con QN_PYTHON=<cartella portatile>/python/pythonw.exe prova la cartella portatile al posto della venv.
import { execSync, spawn } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createRequire } from 'node:module';
const { chromium } = createRequire(resolve('frontend/package.json'))('playwright-core');

const shot = process.argv[2];
const work = mkdtempSync(join(tmpdir(), 'qn-py-'));
const notes = join(work, 'note');
const pad = (n) => String(n).padStart(2, '0');
const now = new Date();
const [y, m, d] = [now.getFullYear(), pad(now.getMonth() + 1), pad(now.getDate())];
const today = `${y}-${m}-${d}`;
mkdirSync(join(notes, `${y}`, m), { recursive: true });
const dailyPath = join(notes, `${y}`, m, `${today}-giornata.md`);
const meetingId = `${today}-0900-kickoff-cliente`;
const meetingPath = join(notes, `${y}`, m, `${meetingId}.md`);
writeFileSync(dailyPath, `---\ntype: daily\ntitle: Giornata\ndate: ${today}\n---\n## Priorità\n- [ ] @Marco invia preventivo due:2020-01-01 #clientex\n- [x] fatto\n`);
writeFileSync(meetingPath, `---\r\ntype: meeting\r\ntitle: Kickoff cliente\r\npeople: [Laura]\r\n---\r\nNe parliamo [[${today}-giornata|oggi]] con @Laura #clientex\r\n`);

const python = resolve(process.env.QN_PYTHON ?? '.venv/Scripts/python.exe');
const child = spawn(python, ['-m', 'quicknotes'], {
  cwd: resolve('.'),
  env: { ...process.env, QUICKNOTES_DIR: notes, QUICKNOTES_CONFIG_DIR: join(work, 'cfg'),
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: '--remote-debugging-port=9334' },
  stdio: 'ignore',
});
let exited = false;
child.on('exit', () => (exited = true));

const failures = [];
const check = (ok, what) => { console.log(`${ok ? 'ok ' : 'NO '} ${what}`); if (!ok) failures.push(what); };
const invoke = (page, cmd, args = {}) => page.evaluate(([c, a]) => window.pywebview.api.invoke(c, a), [cmd, args]);

try {
  let browser;
  for (let i = 0; i < 80 && !browser; i++) {
    try { browser = await chromium.connectOverCDP('http://127.0.0.1:9334'); } catch { await new Promise((r) => setTimeout(r, 250)); }
  }
  if (!browser) throw new Error('nessuna connessione CDP');
  const page = browser.contexts()[0].pages()[0];
  const errors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') errors.push(msg.text()); });
  page.on('pageerror', (e) => errors.push(`eccezione: ${e.message}`));
  page.on('response', (r) => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });

  await page.waitForSelector('.cm-content', { timeout: 15000 });
  await page.waitForFunction(() => window.pywebview?.api?.invoke);
  check(true, 'pagina disegnata con l\'editor della nota di oggi');
  check(await page.evaluate(() => window.__QN__?.backend === 'py'), 'dati d\'avvio iniettati da Python');

  // Eventi da Python, registrati per i controlli sotto.
  await page.evaluate(() => { const orig = window.__qnEmit; window.__eventi = []; window.__qnEmit = (n, p) => { window.__eventi.push([n, p]); orig(n, p); }; });

  // Scrittura e salvataggio automatico.
  await page.click('.cm-content');
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\n- [ ] @Giulia scritta da pywebview #prova');
  let saved = false;
  for (let i = 0; i < 20 && !saved; i++) {
    await page.waitForTimeout(250);
    saved = readFileSync(dailyPath, 'utf8').includes('@Giulia scritta da pywebview #prova');
  }
  check(saved, 'testo scritto nell\'editor salvato su disco');
  check(readFileSync(dailyPath, 'utf8').startsWith('---\ntype: daily\ntitle: Giornata\n'), 'frontmatter della nota di oggi intatto');

  const side = (await invoke(page, 'sidebar')).ok;
  check(side?.open === 2 && side?.late === 1 && side?.todayTotal === 3, `contatori della barra laterale ${JSON.stringify(side)}`);
  const people = (await invoke(page, 'top_people', { limit: 10 })).ok.map((p) => p.name).sort();
  check(JSON.stringify(people) === '["Giulia","Laura","Marco"]', `persone ${people}`);
  const found = (await invoke(page, 'search_titles', { query: 'kickoff', limit: 5 })).ok;
  check(found?.[0]?.id === meetingId, 'ricerca per titolo');
  const daily = (await invoke(page, 'read_note', { id: `${today}-giornata` })).ok;
  check(daily?.links_in?.[0]?.note_id === meetingId, 'collegamenti in entrata');
  const board = (await invoke(page, 'action_board')).ok;
  check(board?.open === 2 && board?.late === 1, `bacheca delle azioni ${JSON.stringify({ open: board?.open, late: board?.late })}`);
  const hits = (await invoke(page, 'search_all', { query: 'preventivo' })).ok;
  check(hits?.some((h) => h.kind === 'action'), 'Ctrl K trova anche le azioni');

  // Una modifica fatta fuori dall'app arriva alla pagina.
  writeFileSync(meetingPath, readFileSync(meetingPath, 'utf8') + 'aggiunta esterna\r\n');
  await page.waitForTimeout(3000);
  const events = await page.evaluate(() => window.__eventi);
  check(events.some(([n, p]) => n === 'note-changed' && p.includes(meetingId)), 'modifica esterna segnalata alla pagina');
  check(readFileSync(meetingPath, 'utf8').includes('\r\n') && !/[^\r]\n/.test(readFileSync(meetingPath, 'utf8')), 'a capo di Windows conservati');

  // Immagine incollata: salvata accanto alla nota e servita dal server locale.
  const img = await page.evaluate(async (id) => {
    const png = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='), (c) => c.charCodeAt(0));
    const res = await fetch(`${window.__QN__.fileOrigin}?note=${encodeURIComponent(id)}`, { method: 'POST', body: png });
    const rel = await res.text();
    const back = await fetch(`${window.__QN__.fileOrigin}${id.slice(0, 4)}/${id.slice(5, 7)}/${rel}`);
    return { rel, status: back.status, type: back.headers.get('content-type') };
  }, meetingId);
  check(img.rel.startsWith('images/') && img.status === 200 && img.type === 'image/png', `immagine salvata e servita ${JSON.stringify(img)}`);

  if (shot) await page.screenshot({ path: shot });
  check(errors.length === 0, `nessun errore nella pagina${errors.length ? ': ' + errors.join(' | ') : ''}`);

  // La X della finestra (WM_CLOSE), subito dopo aver scritto: il testo deve arrivare su disco anche se il
  // salvataggio automatico non è ancora partito, e la finestra va nell'area di notifica senza bloccarsi.
  await page.click('.cm-content');
  await page.keyboard.press('Control+End');
  await page.keyboard.type(' ultima parola');
  // Con la venv il processo avviato è solo un lanciatore: la finestra va cercata per titolo.
  const closed = execSync('powershell -NoProfile -Command "Get-Process | Where-Object { $_.ProcessName -like \'python*\' '
    + '-and $_.MainWindowTitle -like \'*QuickNotes\' } | ForEach-Object { $_.CloseMainWindow() }"').toString().trim();
  check(closed === 'True', 'X della finestra premuta');
  let saved2 = false;
  for (let i = 0; i < 20 && !saved2; i++) {
    await page.waitForTimeout(250);
    saved2 = readFileSync(dailyPath, 'utf8').includes('ultima parola');
  }
  check(saved2, 'testo scritto subito prima della chiusura salvato');
  // WebView2 resta "visible" anche a finestra nascosta: lo dice Windows, che non la trova più tra quelle visibili.
  const visible = execSync('powershell -NoProfile -Command "@(Get-Process | Where-Object { $_.ProcessName -like \'python*\' '
    + '-and $_.MainWindowTitle -like \'*QuickNotes\' }).Count"').toString().trim();
  check(!exited && visible === '0', 'la X nasconde la finestra, l\'app resta attiva');
  // Esci, come dal menu dell'area di notifica.
  await invoke(page, 'quit').catch(() => {});
  for (let i = 0; i < 40 && !exited; i++) await new Promise((r) => setTimeout(r, 250));
  check(exited, 'Esci chiude l\'app');
  await browser.close().catch(() => {});
} catch (e) {
  failures.push(String(e));
  console.log('ERRORE:', e);
} finally {
  if (!exited) child.kill();
}
console.log(failures.length ? `\n${failures.length} controlli falliti` : '\ntutti i controlli superati');
process.exit(failures.length ? 1 : 0);
