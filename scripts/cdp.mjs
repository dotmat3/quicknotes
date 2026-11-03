// Avvia l'app di release in cartelle di prova e la guida via CDP, per controlli e fotografie.
// Uso: node scripts/cdp.mjs <cartella note> <foto.png> [script.mjs]
import { spawn, execSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';
const { chromium } = createRequire(resolve('frontend/package.json'))('playwright-core');

const [notes, shot, scriptPath] = process.argv.slice(2);
const work = mkdtempSync(join(tmpdir(), 'qn-cdp-'));
const child = spawn(resolve('target/release/quicknotes.exe'), [], {
  env: {
    ...process.env,
    QUICKNOTES_DIR: resolve(notes),
    QUICKNOTES_CONFIG_DIR: process.env.QN_CFG ?? join(work, 'cfg'),
    WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: '--remote-debugging-port=9333',
  },
  stdio: 'ignore',
});

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
  console.log('url iniziale:', page.url());
  await page.goto(page.url().startsWith('http') ? page.url() : 'http://tauri.localhost/').catch((e) => console.log('navigazione:', e.message.split('\n')[0]));
  await page.waitForTimeout(1500);
  let expected = [];
  if (scriptPath) {
    const mod = await import(pathToFileURL(resolve(scriptPath)).href);
    // Una prova può dichiarare gli errori che provoca di proposito.
    expected = mod.expectedErrors ?? [];
    await mod.default(page, { notes: resolve(notes), work });
  }
  if (shot) await page.screenshot({ path: shot });
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
} finally {
  // L'app può essere già uscita da sola, se la prova ha chiesto di chiuderla.
  try {
    execSync(`taskkill /PID ${child.pid} /T /F`, { stdio: 'ignore' });
  } catch {}
}
process.exit(code);
