// Prova nell'app vera: Micio sopra le schede, la sua stanza, il negozio, le impostazioni e il minigioco.
// Uso: node scripts/demo-note.mjs <cartella> && QN_CFG=<cartella config> node scripts/cdp.mjs <cartella> <foto.png> scripts/prova-micio.mjs
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};
const until = async (fn, ms = 5000) => {
  for (const end = Date.now() + ms; Date.now() < end; await new Promise((r) => setTimeout(r, 100))) if (await fn()) return true;
  return false;
};

export default async function (page, { cfg }) {
  await page.waitForSelector('.cm-content');
  const layer = page.locator('[role="region"][aria-label="Micio"]');
  await layer.locator('.cat-btn').waitFor();

  // Sopra le note, appoggiato al bordo inferiore della finestra.
  const box = await layer.locator('.cat-btn').boundingBox();
  const vh = await page.evaluate(() => window.innerHeight);
  assert(Math.abs(box.y + box.height - vh) < 12, `Micio poggia sul fondo della finestra (${Math.round(box.y + box.height)} su ${vh})`);
  const front = await page.evaluate(([x, y]) => !!document.elementFromPoint(x, y)?.closest('.cat-btn'), [box.x + box.width / 2, box.y + box.height * 0.8]);
  assert(front, 'Micio è davanti al contenuto della pagina');

  // Fa cose diverse da solo.
  const seen = new Set();
  for (let i = 0; i < 150 && seen.size < 3; i++) {
    const cls = (await layer.locator('.sprite').getAttribute('class')) ?? '';
    seen.add(cls.match(/qn-a-(\w+?)b?(\s|$)/)?.[1]);
    await page.waitForTimeout(200);
  }
  assert(seen.size >= 3, `da solo cambia animazione (${[...seen].join(', ')})`);

  // Un'azione spuntata nell'editor vale 5 crocchette e Micio festeggia.
  await page.locator('.cm-task-box[aria-checked="false"]').first().click();
  assert(await until(async () => (await layer.locator('.bubble').count()) && (await layer.locator('.bubble').innerText()).includes('+5 crocchette')), 'spuntando un’azione nell’editor Micio festeggia: +5 crocchette');
  {
    const b = await layer.locator('.bubble').boundingBox();
    const c = await layer.locator('.cat-btn').boundingBox();
    const gap = c.y - (b.y + b.height);
    assert(gap > -c.height * 0.2 && gap < c.height * 0.3, `la nuvoletta sta appena sopra il gatto (distacco ${Math.round(gap)}px, gatto alto ${Math.round(c.height)}px)`);
    const mid = b.x + b.width / 2;
    assert(mid > c.x && mid < c.x + c.width, 'la nuvoletta è allineata al gatto in orizzontale');
  }

  // La stanza: il gatto ci entra e in fondo alle schede non c'è più.
  await page.getByRole('button', { name: 'Micio', exact: false }).first().click();
  await page.waitForSelector('section[aria-label="La stanza"] .cat-btn');
  assert((await layer.count()) === 0, 'con la stanza aperta Micio non è in fondo alle schede');
  const coinsText = () => page.locator('.coins').innerText();
  const coins0 = Number((await coinsText()).match(/\d+/)[0]);
  assert(coins0 >= 5, `le crocchette contano le azioni fatte da oggi (${coins0})`);

  // Negozio: compra la ciotola, finisce nella stanza e le crocchette calano.
  const bowl = page.locator('.item', { hasText: 'Ciotola' });
  if (coins0 >= 10) {
    await bowl.getByRole('button', { name: /Compra/ }).click();
    assert(await until(async () => Number((await coinsText()).match(/\d+/)[0]) === coins0 - 10), 'comprare la ciotola costa 10 crocchette');
    assert((await bowl.getByRole('button').innerText()) === 'Nella stanza', 'la ciotola risulta nella stanza');
    assert((await page.locator('section[aria-label="La stanza"] .items .it').count()) === 2, 'la ciotola compare nella stanza, accanto alla finestra');
  }
  assert((await page.locator('.item', { hasText: 'Tappeto' }).getByRole('button').innerText()).startsWith('Mancano'), 'un oggetto troppo caro dice quante crocchette mancano');

  // Mantello e dimensione.
  const sheet = () => page.locator('section[aria-label="La stanza"] .sprite').evaluate((el) => el.style.backgroundImage);
  const before = await sheet();
  await page.getByRole('radio', { name: 'Grigio' }).click();
  assert(await until(async () => (await sheet()) !== before), 'il mantello grigio ricolora il gatto');
  await page.locator('#micio-size').fill('5');
  const size = await page.locator('section[aria-label="La stanza"] .cat').evaluate((el) => el.style.fontSize);
  assert(size === '5px', 'la dimensione cambia il gatto (5 pixel per pixel)');

  // Minigioco: parte, si gioca con le frecce, si esce.
  await page.getByRole('button', { name: 'Gioca', exact: true }).click();
  await page.waitForSelector('.hud [role="timer"]');
  for (let i = 0; i < 6; i++) { await page.keyboard.press(i % 2 ? 'ArrowRight' : 'ArrowLeft'); await page.waitForTimeout(400); }
  const t = Number((await page.locator('.hud [role="timer"]').innerText()).match(/\d+/)[0]);
  assert(t < 30 && t > 20, `il tempo scorre (${t} s)`);
  assert((await page.locator('.fall').count()) > 0, 'cadono pesci');
  await page.getByRole('button', { name: 'Esci', exact: true }).click();
  assert((await page.locator('.hud').count()) === 0, 'Esci chiude la partita');

  // Nascosto: tornando alle note Micio non c'è.
  await page.getByRole('radio', { name: 'Nascosto' }).click();
  await page.locator('.tab-main', { hasText: 'Oggi ·' }).click();
  await page.waitForTimeout(500);
  assert((await layer.count()) === 0, 'in modalità Nascosto non compare in fondo alle schede');
  await page.getByRole('button', { name: 'Micio', exact: false }).first().click();
  await page.getByRole('radio', { name: 'Gioca' }).click();
  await page.locator('.tab-main', { hasText: 'Oggi ·' }).click();
  await layer.locator('.cat-btn').waitFor();
  assert(true, 'in modalità Gioca torna in fondo alle schede');

  // Si ricorda tutto.
  await page.waitForTimeout(900);
  const conf = JSON.parse(readFileSync(join(cfg, 'config.json'), 'utf8'));
  const p = conf.ui?.pet;
  assert(p && p.coat === '#9A9FAD' && p.scale === 5 && p.out === 'play' && (coins0 < 10 || p.owned.ciotola), 'mantello, dimensione, modalità e oggetti sono salvati nelle preferenze');
}
