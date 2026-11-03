// Prepara una versione da pubblicare su GitHub: lo zip portatile e la descrizione della release.
//
// Uso:  node scripts/rilascio.mjs [--note "Novità di questa versione"]
//
// Il risultato va in rilasci/v<versione>/. Il nome dello zip non cambia tra una versione e l'altra, così
// https://github.com/<repo>/releases/latest/download/QuickNotes.zip porta sempre all'ultima.
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
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

const { repo } = JSON.parse(readFileSync(join(root, 'scripts', 'rilascio.json'), 'utf8'));
const version = /__version__ = "([^"]+)"/.exec(readFileSync(join(root, 'quicknotes', '__init__.py'), 'utf8'))[1];
const releases = `https://github.com/${repo}/releases`;
const out = join(root, 'rilasci', `v${version}`);
console.log(`QuickNotes ${version}\nrelease: ${releases}\nrisultato in: ${out}\n`);

const python = join(root, '.venv', 'Scripts', 'python.exe');
const r = spawnSync(python, [join(root, 'scripts', 'costruisci.py')], { cwd: root, stdio: 'inherit' });
if (r.status !== 0) fail('Costruzione non riuscita.');

mkdirSync(out, { recursive: true });
copyFileSync(join(root, 'dist', 'QuickNotes.zip'), join(out, 'QuickNotes.zip'));
const notes = `${opt('note') ?? `QuickNotes ${version}`}

**Come si usa:** scarica \`QuickNotes.zip\`. Prima di estrarlo: tasto destro › Proprietà › spunta **Sblocca**. Estrai la cartella dove vuoi (per esempio \`Documenti\\QuickNotes\`) e apri \`QuickNotes.cmd\`. Non si installa nulla e non servono permessi di amministratore: dentro c'è anche Python.

- Se l'app non parte, \`Verifica.cmd\` controlla il PC e dice cosa manca.
- Per collegare le note a Claude: Impostazioni › Claude dentro l'app, con la configurazione già pronta da copiare.
- Da una versione precedente: chiudi QuickNotes (icona vicino all'orologio › Esci) e sostituisci la cartella con questa. Le note restano in \`%USERPROFILE%\\QuickNotes\`. Se avevi attivato l'avvio con Windows, riattivalo.
`;
writeFileSync(join(out, 'note-release.md'), notes);

console.log(`
Pronto in ${out}:
  QuickNotes.zip       l'app portatile, con Python e server MCP
  note-release.md      la descrizione della release

Per pubblicarla: su ${releases}/new crea la release con tag v${version},
incolla note-release.md come descrizione, allega QuickNotes.zip e pubblica.`);
