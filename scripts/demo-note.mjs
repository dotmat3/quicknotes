// Crea note di prova simili a quelle della tavola Home. Uso: node scripts/demo-note.mjs <cartella>
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const root = resolve(process.argv[2]);
const now = new Date();
const p = (n) => String(n).padStart(2, '0');
const iso = (d) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
const plus = (n) => iso(new Date(now.getFullYear(), now.getMonth(), now.getDate() + n));
const today = iso(now);

function write(id, front, body, day = now) {
  const dir = join(root, String(day.getFullYear()), p(day.getMonth() + 1));
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${id}.md`), `---\n${front}\n---\n${body}`);
}

write(`${today}-giornata`, `type: daily\ntitle: Giornata\ndate: ${today}`, `- [x] Rileggere i requisiti e fissare lo scope della 0.2 #quicknotes done:${today}
- [ ] Mandare a @Giulia la bozza del budget Q4 #lavoro-q4 due:${plus(1)}
    Allegare il foglio costi aggiornato.
    - [x] Raccogliere le voci di ottobre done:${today}
    - [ ] Confrontare con @Elena le voci del terzo trimestre
    - [ ] Rileggere la bozza prima dell'invio due:${plus(1)}
- [ ] Richiamare @Marco per il preventivo della cucina #casa due:${plus(-3)}
- [ ] Provare il modello medium di Whisper sulle registrazioni lunghe #quicknotes

Ricerca semantica: valutare embedding locali accanto a FTS5, senza toccare i file Markdown. L'indice deve restare ricostruibile da zero. !decisione gli embedding vivono in un file separato.

## Note

Vedi [[riunione-budget-q4|Riunione budget Q4]] e i **requisiti** in \`store.rs\`.

> [!NOTE]
> SQLite FTS5 è solo un indice: si ricostruisce in ogni momento dai file.
`);
write('riunione-budget-q4', `type: meeting\ntitle: Riunione budget Q4\ndate: ${plus(-5)}T14:30\npeople: [Giulia, Marco]\ntags: [lavoro-q4]`, `## Decisioni

!decisione Il budget Q4 viene diviso in tre tranche mensili.

## Azioni

- [ ] Aggiornare con @Giulia il foglio costi di ottobre #lavoro-q4 due:${plus(-4)}
- [x] Raccogliere i preventivi dei fornitori #lavoro-q4 done:${plus(-1)}

## Note

Giulia propone di chiudere la bozza entro lunedì. Marco chiede margine per la formazione.

## Trascrizioni

🎙️ [Registrazione 15:02 (18:40)](audio/riunione-budget-q4-150200.wav)

### Trascrizione 15:02
[00:00] Punto della situazione: la bozza è quasi pronta, mancano le voci di ottobre.
[12:40] Per il quarto trimestre servono tre tranche mensili, quindi il foglio costi va diviso per mese.
`);
write('requisiti-e-architettura', `type: note\ntitle: Requisiti e architettura\ndate: ${plus(-12)}\ntags: [quicknotes]`, `Uso personale, solo desktop. Le note sono file Markdown.

- [ ] Preparare i modelli di nota per le riunioni #quicknotes due:${plus(3)}
- [ ] Valutare embedding locali per la ricerca #quicknotes
- [ ] Rivedere gli OKR del trimestre con @Elena #lavoro-q4 due:${plus(20)}
`);
