// Avvia l'app in cartelle di prova e la guida via CDP, per controlli e fotografie.
// Uso: node scripts/cdp.mjs <cartella note> <foto.png> [script.mjs]
// Usa il Python di .venv; con QN_PYTHON=<cartella portatile>/python/pythonw.exe prova la cartella portatile.
import { spawn, execSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
const { chromium } = createRequire(resolve('frontend/package.json'))('playwright-core');

const [notes, shot, scriptPath] = process.argv.slice(2);
const work = mkdtempSync(join(tmpdir(), 'qn-cdp-'));
// Il WebView2 della prova precedente può tenere la porta ancora per un attimo: collegarsi a lui sarebbe un errore.
for (let i = 0; i < 40; i++) {
  const busy = await fetch('http://127.0.0.1:9333/json/version').then(() => true, () => false);
  if (!busy) break;
  await new Promise((r) => setTimeout(r, 250));
}
const child = spawn(resolve(process.env.QN_PYTHON ?? '.venv/Scripts/python.exe'), ['-m', 'quicknotes'], {
  cwd: resolve('.'),
  env: {
    ...process.env,
    QUICKNOTES_DIR: resolve(notes),
    QUICKNOTES_CONFIG_DIR: process.env.QN_CFG ?? join(work, 'cfg'),
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: '--remote-debugging-port=9333',
  },
  stdio: 'ignore',
});
// Alcune prove chiudono l'app (Esci, riavvio): dopo non si può più fotografare.
let exited = false;
child.on('exit', () => (exited = true));

let code = 0;
try {
  let browser;
  for (let i = 0; i < 60 && !browser; i++) {
    try {
      browser = await chromium.connectOverCDP('http://127.0.0.1:9333');
    } catch {
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  if (!browser) throw new Error('nessuna connessione CDP');
  const page = browser.contexts()[0].pages()[0];
  const errors = [];
  // Il ricaricamento qui sotto lascia in sospeso le chiamate iniziali: quell'avviso è atteso.
  page.on('console', (m) => { if ((m.type() === 'error' || m.type() === 'warning') && !m.text().includes("Couldn't find callback id")) errors.push(`${m.type()}: ${m.text()}`); });
  page.on('pageerror', (e) => errors.push(`eccezione: ${e.message}`));
  // La pagina arriva dal server locale di Python: finché WebView2 non l'ha chiesta, l'indirizzo è about:blank.
  for (let i = 0; i < 60 && !page.url().startsWith('http'); i++) await page.waitForTimeout(250);
  console.log('url iniziale:', page.url());
  // Si ricarica per ascoltare gli errori fin dal primo script, ma solo a pagina ferma: pywebview inserisce il suo
  // ponte a fine navigazione, e due inserimenti nella stessa pagina perderebbero le risposte in attesa.
  await page.waitForFunction(() => document.readyState === 'complete' && window.pywebview?.api?.invoke, null, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(500);
  await page.reload().catch((e) => console.log('navigazione:', e.message.split('\n')[0]));
  await page.waitForTimeout(1500);
  let expected = [];
  if (scriptPath) {
    const mod = await import(pathToFileURL(resolve(scriptPath)).href);
    // Una prova può dichiarare gli errori che provoca di proposito.
    expected = mod.expectedErrors ?? [];
    // Il python.exe della venv è un lanciatore: le finestre appartengono al processo figlio.
    let pid = child.pid;
    try {
      const inner = execSync(`powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ParentProcessId=${child.pid}' | Where-Object Name -like 'python*').ProcessId"`, { encoding: 'utf8' }).trim();
      if (/^\d+$/.test(inner)) pid = Number(inner);
    } catch {}
    await mod.default(page, { notes: resolve(notes), work, cfg: process.env.QN_CFG ?? join(work, 'cfg'), pid });
  }
  if (shot && !exited) await page.screenshot({ path: shot });
  const unexpected = errors.filter((e) => !expected.some((re) => re.test(e)));
  if (unexpected.length < errors.length) console.log(`errori attesi dalla prova: ${errors.length - unexpected.length}`);
  errors.splice(0, errors.length, ...unexpected);
  if (errors.length) {
    code = 1;
    console.log('ERRORI DELLA PAGINA:\n' + errors.join('\n'));
  } else {
    console.log('nessun errore nella pagina');
  }
  await browser.close().catch(() => {});
} catch (e) {
  code = 1;
  console.error(e);
  // Per capire il fallimento: com'era la pagina e cosa ha scritto l'app nel registro.
  const page = (await chromium.connectOverCDP('http://127.0.0.1:9333').catch(() => null))?.contexts()[0]?.pages().find((p) => !p.url().includes('#capture'));
  const state = await page?.evaluate(() => JSON.stringify({ url: location.href, bridge: !!window.pywebview?.api?.invoke, text: document.body?.innerText.slice(0, 300) })).catch(() => null);
  console.error('PAGINA:', state ?? 'non raggiungibile');
  try {
    const log = readFileSync(join(process.env.QN_CFG ?? join(work, 'cfg'), 'quicknotes.log'), 'utf8').trim().split('\n');
    console.error('REGISTRO:\n' + log.slice(-15).join('\n'));
  } catch {}
} finally {
  // L'app può essere già uscita da sola, se la prova ha chiesto di chiuderla.
  try {
    execSync(`taskkill /PID ${child.pid} /T /F`, { stdio: 'ignore' });
  } catch {}
}
process.exit(code);
