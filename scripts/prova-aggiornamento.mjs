// Prova completa di installazione e aggiornamento, con gli installer veri di scripts/rilascio.mjs:
//   node scripts/rilascio.mjs --endpoint http://127.0.0.1:8765/latest.json --base-url http://127.0.0.1:8765/ --insecure --version 0.3.0 --out <cartella>/a
//   node scripts/rilascio.mjs ... --version 0.3.1 --out <cartella>/b
//   node scripts/prova-aggiornamento.mjs <cartella>
// Installa la versione di a/ per l'utente in <cartella>/inst, la avvia su note di prova, fa trovare la
// versione di b/ a un server locale che fa da GitHub, la installa e alla fine disinstalla tutto.
// L'app installata riceve le cartelle di prova come argomenti (--cartella-note, --cartella-config): sono gli
// unici che sopravvivono al riavvio fatto dall'installer. La prova controlla che le note vere non cambino.
import { spawn, spawnSync, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';
import { createRequire } from 'node:module';
const { chromium } = createRequire(resolve('frontend/package.json'))('playwright-core');

const base = resolve(process.argv[2]);
const inst = join(base, 'inst');
const notes = join(base, 'note');
const cfg = join(base, 'cfg');
const setupOf = (dir) => join(base, dir, readdirSync(join(base, dir)).find((f) => f.endsWith('-setup.exe')));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};
const until = async (fn, ms) => {
  for (const end = Date.now() + ms; Date.now() < end; await sleep(250)) if (await fn()) return true;
  return false;
};
const ps = (cmd) => execFileSync('powershell.exe', ['-NoProfile', '-Command', cmd], { encoding: 'utf8' }).trim();
const processes = () => {
  const out = ps("Get-CimInstance Win32_Process -Filter \"Name='quicknotes.exe'\" | ForEach-Object { \"$($_.ProcessId)|$($_.ExecutablePath)|$($_.CommandLine)\" }");
  return out.split(/\r?\n/).filter(Boolean).map((l) => {
    const [pid, path, ...cmd] = l.split('|');
    return { pid: Number(pid), path, cmd: cmd.join('|') };
  });
};
const installed = () => processes().filter((p) => p.path?.toLowerCase().startsWith(inst.toLowerCase()));
const fileVersion = () => ps(`(Get-Item '${join(inst, 'quicknotes.exe')}').VersionInfo.ProductVersion`);
const runKey = () => spawnSync('reg', ['query', 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run'], { encoding: 'utf8' }).stdout;

// L'ultima modifica nelle cartelle vere: non deve cambiare durante la prova.
function newest(dir, skip = []) {
  let max = 0;
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      if (skip.includes(e.name)) continue;
      const p = join(d, e.name);
      if (e.isDirectory()) walk(p);
      else max = Math.max(max, statSync(p).mtimeMs);
    }
  };
  if (existsSync(dir)) walk(dir);
  return max;
}
const real = () => [newest(join(homedir(), 'QuickNotes')), newest(join(homedir(), '.quicknotes'), ['webview'])].join(',');

// Il finto GitHub: latest.json e installer della versione nuova. Con `falso` l'installer servito è un altro
// file, firmato ma non quello indicato dalla firma: l'app deve rifiutarlo.
let falso = true;
const server = createServer((req, res) => {
  const name = decodeURIComponent(req.url.slice(1));
  const file = name === 'latest.json' ? join(base, 'b', 'latest.json') : name.endsWith('-setup.exe') ? (falso ? setupOf('a') : setupOf('b')) : null;
  if (!file) return res.writeHead(404).end();
  res.writeHead(200).end(readFileSync(file));
});
await new Promise((r) => server.listen(8765, '127.0.0.1', r));

const before = real();
let browser;
try {
  assert(!processes().length, 'nessuna QuickNotes aperta prima della prova');
  execFileSync('node', ['scripts/demo-note.mjs', notes]);

  // Installazione silenziosa per l'utente, senza permessi di amministratore.
  spawnSync(setupOf('a'), ['/S', `/D=${inst}`], { stdio: 'ignore' });
  assert(existsSync(join(inst, 'quicknotes.exe')) && existsSync(join(inst, 'quicknotes-mcp.exe')), 'l\'installer mette app e server MCP nella cartella scelta');
  assert(fileVersion().startsWith('0.3.0'), `versione installata ${fileVersion()}`);
  const shortcut = join(process.env.APPDATA, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'QuickNotes.lnk');
  assert(existsSync(shortcut), 'c\'è il collegamento nel menu Start');

  spawn(join(inst, 'quicknotes.exe'), [`--cartella-note=${notes}`, `--cartella-config=${cfg}`], {
    env: { ...process.env, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: '--remote-debugging-port=9333' },
    detached: true,
    stdio: 'ignore',
  }).unref();
  for (let i = 0; i < 60 && !browser; i++) browser = await chromium.connectOverCDP('http://127.0.0.1:9333').catch(() => sleep(250).then(() => null));
  assert(!!browser, 'l\'app installata parte');
  const page = browser.contexts()[0].pages().find((p) => !p.url().includes('#capture')) ?? browser.contexts()[0].pages()[0];
  if (!page.url().startsWith('http')) await page.goto('http://tauri.localhost/');
  await page.waitForSelector('.cm-content', { timeout: 15000 });
  const today = new Date();
  const p2 = (n) => String(n).padStart(2, '0');
  const daily = join(notes, String(today.getFullYear()), p2(today.getMonth() + 1), `${today.getFullYear()}-${p2(today.getMonth() + 1)}-${p2(today.getDate())}-giornata.md`);
  assert(existsSync(daily), 'lavora sulle note di prova indicate negli argomenti');

  // Testo scritto e non ancora salvato: l'aggiornamento non deve perderlo.
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type('\nScritto subito prima dell\'aggiornamento');

  // Il controllo automatico all'avvio trova la versione nuova.
  await page.waitForSelector('.titlebar .update', { timeout: 30000 });
  assert((await page.locator('.titlebar .update').innerText()).includes('0.3.1'), 'dopo l\'avvio la barra del titolo segnala la 0.3.1');
  await page.locator('.titlebar .update').click();
  await page.waitForSelector('text=Novità della 0.3.1');
  assert((await page.locator('main.pane').innerText()).includes('0.3.0'), 'Impostazioni › Informazioni mostra la versione installata e le novità');

  // Avvia con Windows: scrive e toglie la voce di avvio dell'utente.
  await page.getByRole('switch', { name: 'Avvia con Windows' }).click();
  assert(await until(() => /QuickNotes.*--nascosta/i.test(runKey()) && runKey().toLowerCase().includes(inst.toLowerCase()), 5000), '«Avvia con Windows» registra l\'app installata, che partirà nascosta');
  await page.getByRole('switch', { name: 'Avvia con Windows' }).click();
  assert(await until(() => !/QuickNotes/i.test(runKey()), 5000), 'e spegnendolo la voce sparisce');

  // Un installer che non corrisponde alla firma si rifiuta, e l'app resta aperta.
  const pid = installed()[0].pid;
  await page.getByRole('button', { name: 'Aggiorna e riavvia' }).click();
  assert(await until(async () => /non ha la firma di QuickNotes/.test(await page.locator('main.pane').innerText()), 30000), 'un installer con la firma sbagliata viene rifiutato, e l\'avviso lo dice in italiano');
  assert(installed().some((p) => p.pid === pid), 'e l\'app resta aperta, senza installare nulla');

  // L'installer giusto: salva, chiude, installa e riapre l'app aggiornata con gli stessi argomenti.
  falso = false;
  await page.getByRole('button', { name: 'Aggiorna e riavvia' }).click();
  browser.close().catch(() => {});
  browser = null;
  assert(await until(() => !installed().some((p) => p.pid === pid), 30000), 'la versione vecchia si chiude');
  assert(await until(() => installed().length > 0 && fileVersion().startsWith('0.3.1'), 60000), `e la 0.3.1 si riapre da sola (${fileVersion()})`);
  const again = installed()[0];
  assert(again.cmd.includes('--cartella-note=') && again.cmd.includes('--cartella-config='), 'con gli stessi argomenti, quindi sulle stesse note');
  assert(readFileSync(daily, 'utf8').includes('Scritto subito prima dell\'aggiornamento'), 'il testo scritto prima dell\'aggiornamento è salvato');
  await sleep(3000);
  for (const p of installed()) spawnSync('taskkill', ['/PID', String(p.pid), '/T', '/F']);
} finally {
  await browser?.close().catch(() => {});
  for (const p of installed()) spawnSync('taskkill', ['/PID', String(p.pid), '/T', '/F']);
  server.close();
  // Disinstallazione silenziosa: l'uninstaller si copia altrove e lavora in sottofondo.
  if (existsSync(join(inst, 'uninstall.exe'))) {
    spawnSync(join(inst, 'uninstall.exe'), ['/S'], { stdio: 'ignore' });
    await until(() => !existsSync(join(inst, 'quicknotes.exe')), 20000);
  }
  const shortcut = join(process.env.APPDATA, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'QuickNotes.lnk');
  console.log(`${!existsSync(join(inst, 'quicknotes.exe')) && !existsSync(shortcut) ? 'ok' : 'ATTENZIONE'}: disinstallata, senza app né collegamento nel menu Start`);
  console.log(`${real() === before ? 'ok' : 'ATTENZIONE'}: le note e la configurazione vere non sono cambiate`);
}
