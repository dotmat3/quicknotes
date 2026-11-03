// Costruisce una versione da distribuire: installer per utente, firma per gli aggiornamenti, server MCP
// incluso e `latest.json`, il file che le copie installate leggono per sapere se c'è una versione nuova.
//
// Uso:  node scripts/rilascio.mjs --repo <utente/repository> [--note "Novità di questa versione"]
//
// La prima volta il repository si ricorda in scripts/rilascio.json. Il risultato va in rilasci/v<versione>/:
// i due file da caricare nella release GitHub `v<versione>` sono l'installer e latest.json.
// Per le prove (scripts/prova-aggiornamento.mjs): --endpoint <url> --base-url <url> --insecure
// --version <x.y.z> --out <cartella> sostituiscono GitHub con un server locale.
import { execFileSync, spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { homedir, tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const args = process.argv.slice(2);
const opt = (name) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : undefined;
};
const flag = (name) => args.includes(`--${name}`);
const fail = (msg) => {
  console.error(`\n${msg}`);
  process.exit(1);
};

// Il repository GitHub da cui le copie installate scaricano gli aggiornamenti.
const saved = join(root, 'scripts', 'rilascio.json');
let repo = opt('repo') ?? (existsSync(saved) ? JSON.parse(readFileSync(saved, 'utf8')).repo : undefined);
const endpointOverride = opt('endpoint');
if (!repo && !endpointOverride) fail('Manca il repository: node scripts/rilascio.mjs --repo <utente/repository>');
if (repo && !/^[\w.-]+\/[\w.-]+$/.test(repo)) fail(`Repository non valido: ${repo} (atteso utente/repository)`);
if (opt('repo')) writeFileSync(saved, `${JSON.stringify({ repo }, null, 2)}\n`);

const cargoVersion = /^version = "([^"]+)"/m.exec(readFileSync(join(root, 'Cargo.toml'), 'utf8'))[1];
const version = opt('version') ?? cargoVersion;
const endpoint = endpointOverride ?? `https://github.com/${repo}/releases/latest/download/latest.json`;
const baseUrl = opt('base-url') ?? `https://github.com/${repo}/releases/download/v${version}/`;
const out = resolve(opt('out') ?? join(root, 'rilasci', `v${version}`));

// La chiave privata firma ogni versione: le copie installate accettano solo aggiornamenti firmati con lei.
const keyDir = join(homedir(), '.tauri');
const keyFile = join(keyDir, 'quicknotes.key');
const passFile = join(keyDir, 'quicknotes.key.password');
if (!existsSync(keyFile)) fail(`Manca la chiave di firma ${keyFile}: senza, le copie installate non accetteranno l'aggiornamento.`);

console.log(`QuickNotes ${version}\naggiornamenti da: ${endpoint}\nrisultato in: ${out}\n`);

// 1. Server MCP, incluso nell'installer accanto all'app.
const env = { ...process.env, PATH: `${join(homedir(), '.cargo', 'bin')};${process.env.PATH}` };
const run = (cmd, cmdArgs, extra = {}, cwd = root) => {
  console.log(`> ${cmd} ${cmdArgs.join(' ')}`);
  const r = spawnSync(cmd, cmdArgs, { cwd, stdio: 'inherit', shell: process.platform === 'win32', env: { ...env, ...extra } });
  if (r.status !== 0) fail(`Comando non riuscito: ${cmd} ${cmdArgs.join(' ')}`);
};
run('cargo', ['build', '--release', '-p', 'quicknotes-mcp']);
const triple = /host: (\S+)/.exec(execFileSync('rustc', ['-vV'], { env, encoding: 'utf8' }))[1];
const binDir = join(root, 'crates', 'quicknotes-app', 'binaries');
mkdirSync(binDir, { recursive: true });
copyFileSync(join(root, 'target', 'release', 'quicknotes-mcp.exe'), join(binDir, `quicknotes-mcp-${triple}.exe`));

// 2. Installer firmato. Le scelte che valgono solo per il rilascio stanno in una configurazione a parte,
// così la compilazione di tutti i giorni non ha bisogno del server MCP né della chiave.
const overlay = {
  ...(opt('version') ? { version } : {}),
  bundle: { externalBin: ['binaries/quicknotes-mcp'] },
  plugins: { updater: { endpoints: [endpoint], ...(flag('insecure') ? { dangerousInsecureTransportProtocol: true } : {}) } },
};
const overlayFile = join(tmpdir(), `quicknotes-rilascio-${process.pid}.json`);
writeFileSync(overlayFile, JSON.stringify(overlay));
// La CLI va lanciata dalla cartella dell'app: i percorsi di tauri.conf.json sono relativi a lei.
const appDir = join(root, 'crates', 'quicknotes-app');
const cli = join(root, 'frontend', 'node_modules', '@tauri-apps', 'cli', 'tauri.js');
run('node', [cli, 'build', '--config', overlayFile], {
  TAURI_SIGNING_PRIVATE_KEY: readFileSync(keyFile, 'utf8'),
  TAURI_SIGNING_PRIVATE_KEY_PASSWORD: existsSync(passFile) ? readFileSync(passFile, 'utf8').trim() : '',
}, appDir);

// 3. latest.json, con la firma dell'installer e l'indirizzo da cui scaricarlo.
const nsis = join(root, 'target', 'release', 'bundle', 'nsis');
const setup = readdirSync(nsis).find((f) => f.endsWith('-setup.exe') && f.includes(`_${version}_`));
if (!setup || !existsSync(join(nsis, `${setup}.sig`))) fail(`Installer o firma non trovati in ${nsis}`);
mkdirSync(out, { recursive: true });
copyFileSync(join(nsis, setup), join(out, setup));
copyFileSync(join(nsis, `${setup}.sig`), join(out, `${setup}.sig`));
const latest = {
  version,
  notes: opt('note') ?? `QuickNotes ${version}`,
  pub_date: new Date().toISOString(),
  platforms: { 'windows-x86_64': { signature: readFileSync(join(nsis, `${setup}.sig`), 'utf8').trim(), url: `${baseUrl}${encodeURIComponent(setup)}` } },
};
writeFileSync(join(out, 'latest.json'), `${JSON.stringify(latest, null, 2)}\n`);

console.log(`
Pronto in ${out}:
  ${setup}   l'installer da dare ai colleghi
  latest.json   dice alle copie installate che c'è la versione ${version}
${endpointOverride ? '' : `
Per pubblicarla: su https://github.com/${repo}/releases/new crea la release con tag v${version},
carica i due file qui sopra e pubblica. Le copie installate la vedranno al prossimo avvio.`}`);
