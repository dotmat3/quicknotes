// Costruisce una versione da distribuire: l'app e il server MCP come due eseguibili da scaricare e avviare,
// senza installer e senza aggiornamenti automatici.
//
// Uso:  node scripts/rilascio.mjs --repo <utente/repository> [--note "Novità di questa versione"]
//
// La prima volta il repository si ricorda in scripts/rilascio.json: l'app lo mostra in Impostazioni ›
// Informazioni, con il pulsante che apre le release. Il risultato va in rilasci/v<versione>/: i due .exe da
// caricare nella release GitHub `v<versione>` e il testo da incollare come descrizione.
// I nomi dei file non cambiano tra una versione e l'altra, così
// https://github.com/<repo>/releases/latest/download/QuickNotes.exe porta sempre all'ultima.
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join, resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const args = process.argv.slice(2);
const opt = (name) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : undefined;
};
const fail = (msg) => {
  console.error(`\n${msg}`);
  process.exit(1);
};

const saved = join(root, 'scripts', 'rilascio.json');
const repo = opt('repo') ?? (existsSync(saved) ? JSON.parse(readFileSync(saved, 'utf8')).repo : undefined);
if (!repo) fail('Manca il repository: node scripts/rilascio.mjs --repo <utente/repository>');
if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) fail(`Repository non valido: ${repo} (atteso utente/repository)`);
if (opt('repo')) writeFileSync(saved, `${JSON.stringify({ repo }, null, 2)}\n`);

const version = /^version = "([^"]+)"/m.exec(readFileSync(join(root, 'Cargo.toml'), 'utf8'))[1];
const releases = `https://github.com/${repo}/releases`;
const out = join(root, 'rilasci', `v${version}`);
console.log(`QuickNotes ${version}\nrelease: ${releases}\nrisultato in: ${out}\n`);

const env = { ...process.env, PATH: `${join(homedir(), '.cargo', 'bin')};${process.env.PATH}`, QUICKNOTES_RELEASES: releases };
const run = (cmd, cmdArgs, cwd = root) => {
  console.log(`> ${cmd} ${cmdArgs.join(' ')}`);
  const r = spawnSync(cmd, cmdArgs, { cwd, stdio: 'inherit', shell: process.platform === 'win32', env });
  if (r.status !== 0) fail(`Comando non riuscito: ${cmd} ${cmdArgs.join(' ')}`);
};

// 1. Server MCP.
run('cargo', ['build', '--release', '-p', 'quicknotes-mcp']);

// 2. App, con l'interfaccia dentro l'eseguibile. La CLI compila prima il frontend e va lanciata dalla cartella
// dell'app: i percorsi di tauri.conf.json sono relativi a lei.
const cli = join(root, 'frontend', 'node_modules', '@tauri-apps', 'cli', 'tauri.js');
run('node', [cli, 'build', '--no-bundle'], join(root, 'crates', 'quicknotes-app'));

// 3. I file della release, con i nomi fissi che l'app si aspetta: Impostazioni › Claude cerca
// quicknotes-mcp.exe accanto all'app.
mkdirSync(out, { recursive: true });
const release = join(root, 'target', 'release');
copyFileSync(join(release, 'quicknotes.exe'), join(out, 'QuickNotes.exe'));
copyFileSync(join(release, 'quicknotes-mcp.exe'), join(out, 'quicknotes-mcp.exe'));
const notes = `${opt('note') ?? `QuickNotes ${version}`}

**Come si usa:** scarica \`QuickNotes.exe\`, mettilo in una cartella a tua scelta (per esempio \`Documenti\\QuickNotes\`) e avvialo. Non si installa nulla e non servono permessi di amministratore.

- Al primo avvio Windows può mostrare "Windows ha protetto il PC": premi "Ulteriori informazioni", poi "Esegui comunque".
- Per collegare le note a Claude scarica anche \`quicknotes-mcp.exe\` e mettilo nella stessa cartella; la configurazione è in Impostazioni › Claude.
- Da una versione precedente: chiudi QuickNotes (icona vicino all'orologio › Esci) e sostituisci i file con questi. Le note restano in \`%USERPROFILE%\\QuickNotes\`.
`;
writeFileSync(join(out, 'note-release.md'), notes);

console.log(`
Pronto in ${out}:
  QuickNotes.exe       l'app
  quicknotes-mcp.exe   il server MCP per Claude, facoltativo
  note-release.md      la descrizione della release

Per pubblicarla: su ${releases}/new crea la release con tag v${version},
incolla note-release.md come descrizione, allega i due .exe e pubblica.`);
