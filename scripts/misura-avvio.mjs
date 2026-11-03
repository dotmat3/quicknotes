// Misura l'avvio a freddo dell'app, in cartelle di prova. I tempi partono dalla creazione del processo Python.
// Uso: node scripts/misura-avvio.mjs <cartella note> [ripetizioni]
// Il dato che conta è "prima pittura": la finestra compare subito dopo.
import { spawn, execSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const notes = resolve(process.argv[2]);
const runs = Number(process.argv[3] ?? 7);
// Python di .venv, oppure quello della cartella portatile con QN_PYTHON.
const exe = resolve(process.env.QN_PYTHON ?? '.venv/Scripts/python.exe');
const args = ['-m', 'quicknotes'];
const work = mkdtempSync(join(tmpdir(), 'qn-avvio-'));
const results = {};

for (let i = 0; i < runs; i++) {
  const trace = join(work, `trace-${i}.txt`);
  const child = spawn(exe, args, {
    env: { ...process.env, QUICKNOTES_DIR: notes, QUICKNOTES_CONFIG_DIR: join(work, 'cfg'), QUICKNOTES_TRACE: trace },
    stdio: 'ignore',
  });
  const started = performance.now();
  while (performance.now() - started < 8000) {
    if (existsSync(trace) && readFileSync(trace, 'utf8').includes('prima pittura')) break;
    await new Promise((r) => setTimeout(r, 10));
  }
  await new Promise((r) => setTimeout(r, 400));
  // Riapertura: una seconda istanza mostra la finestra già pronta e termina.
  const t0 = performance.now();
  await new Promise((done) => spawn(exe, args, { env: { ...process.env, QUICKNOTES_DIR: notes, QUICKNOTES_CONFIG_DIR: join(work, 'cfg') }, stdio: 'ignore' }).on('exit', done));
  (results['riapertura'] ??= []).push(performance.now() - t0);
  execSync(`taskkill /PID ${child.pid} /T /F`, { stdio: 'ignore' });
  await new Promise((r) => setTimeout(r, 400));
  for (const line of readFileSync(trace, 'utf8').trim().split('\n')) {
    const [, ms, phase] = line.match(/([\d.]+) ms\s+(.*)/);
    (results[phase] ??= []).push(Number(ms));
  }
}

const median = (a) => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
for (const [phase, values] of Object.entries(results)) {
  console.log(`${phase.padEnd(18)} mediana ${median(values).toFixed(0).padStart(5)} ms   (min ${Math.min(...values).toFixed(0)}, max ${Math.max(...values).toFixed(0)})`);
}
rmSync(work, { recursive: true, force: true });
