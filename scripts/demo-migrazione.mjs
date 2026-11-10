// Note nel formato di prima della 0.6.0, per provare la migrazione: intestazioni di progetto nei daily, task
// «Deprecato» chiusi con [x], domande scritte come task, etichette ripetute sotto l'intestazione.
// Uso: node scripts/demo-migrazione.mjs <cartella>, poi node scripts/cdp.mjs <cartella> foto.png scripts/prova-migrazione.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const root = resolve(process.argv[2]);
const now = new Date();
const p = (n) => String(n).padStart(2, '0');
const day = (n) => new Date(now.getFullYear(), now.getMonth(), now.getDate() + n);
const iso = (d) => `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;

function note(d, name, front, body) {
  const dir = join(root, String(d.getFullYear()), p(d.getMonth() + 1));
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${name}.md`), `---\n${front}\n---\n${body}`);
}
const daily = (n, body) => note(day(n), `${iso(day(n))}-giornata`, `type: daily\ntitle: Giornata\ndate: ${iso(day(n))}`, body);

daily(-6, `# LLM Training
- [x] Rilanciare dedup fineweb_edu #llm-training done:${iso(day(-5))}
    Deprecato: si è deciso di saltare la dedup.
- [ ] Lanciare dedup e filtri #llm-training #dedup
- Lanciato il job dedup #llm-training
- [ ] Serve rifare i filtri? #filter
# Varie
- [ ] Comprare il toner
`);
daily(-1, `# LLM Training
- [ ] Controllare i filtri #filter
- [ ] Lanciare dedup e filtri #dedup
# MBDA
- [ ] Preparare la documentazione della gara #gara
`);
daily(0, `- [ ] Scrivere il report
`);
note(day(-40), `${iso(day(-40))}-1000-parser`, `type: meeting\ntitle: Parser EKM\ndate: ${iso(day(-40))}T10:00`, `- [ ] Rivedere il parser #ekm
- [ ] Test del parser #ekm
- [x] Vecchio approccio #ekm done:${iso(day(-39))}
    Deprecato
`);
console.log(`note di prova in ${root}`);
