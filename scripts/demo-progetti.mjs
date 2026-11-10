// Note di prova per progetti, stati, Agenda e Revisione: una settimana come quella delle note vere.
// Uso: node scripts/demo-progetti.mjs <cartella>, poi node scripts/cdp.mjs <cartella> foto.png scripts/prova-agenda.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const root = resolve(process.argv[2]);
const now = new Date();
const p = (n) => String(n).padStart(2, '0');
const day = (n) => new Date(now.getFullYear(), now.getMonth(), now.getDate() + n);
const iso = (d) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;

function daily(n, body) {
  const d = day(n);
  const dir = join(root, String(d.getFullYear()), p(d.getMonth() + 1));
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${iso(d)}-giornata.md`), `---\ntype: daily\ntitle: Giornata\ndate: ${iso(d)}\n---\n${body}`);
}

function project(id, text) {
  mkdirSync(join(root, 'progetti'), { recursive: true });
  writeFileSync(join(root, 'progetti', `${id}.md`), text);
}

project('llm-training', `---
type: project
title: LLM Training
project: llm-training
status: attivo
aliases: [LLM Training]
areas: [dedup, filter]
---
## Obiettivo

Addestrare il modello sui dati ripuliti.

## Prossime azioni

### dedup
- [/] Dedup su fineweb

### filter
- [x] Filtro lingua done:${iso(day(-3))}
- [ ] Filtro qualità due:${iso(day(3))}

## Note collegate
`);
project('ekm', `---
type: project
title: EKM
status: pausa
---
## Prossime azioni
- [ ] Rivedere il parser
`);

daily(-6, `# LLM Training
- [ ] Lanciare dedup e filtri
- Lanciato il job dedup
- [ ] Lanciare dedup e filtri
# Varie
- [ ] Comprare il toner
- [w] Preventivo da @Laura
- [?] Usare bf16 per il training?
`);
daily(-1, `# LLM Training
- [ ] Rilanciare finepdfs
    - [x] shard 1 done:${iso(day(-2))}
    - [x] shard 2 done:${iso(day(-1))}
# EKM
- [ ] Task EKM fermo
`);
daily(0, `- [ ] Scrivere il report scheduled:${iso(day(0))}
- [-] Rilanciare dedup fineweb_edu done:${iso(day(0))}
    Saltiamo la dedup: decisione del giorno.
`);
console.log(`note di prova in ${root}`);
