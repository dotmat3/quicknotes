// Prova dal vivo con input di sistema veri (scripts/win.mjs): tasti globali, nota rapida che compare in primo
// piano, Alt F4, area di notifica e il suo menu, barra del titolo con il mouse (doppio clic, spostamento,
// bordo), trascinamento di una scheda con il mouse vero, uscita dal menu.
// Muove davvero mouse e tastiera per una ventina di secondi: durante la prova il PC non va usato.
// Va usata con le note di demo-note.mjs e con nessun'altra QuickNotes aperta.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { Win } from './win.mjs';

const assert = (cond, msg) => {
  if (!cond) throw new Error(`FALLITO: ${msg}`);
  console.log(`ok: ${msg}`);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const WM_TRAY = 6002;
const WM_LBUTTONUP = 0x0202;
const WM_RBUTTONUP = 0x0205;

export default async function (page, { notes, pid }) {
  const win = new Win();
  const now = new Date();
  const p = (n) => String(n).padStart(2, '0');
  const daily = join(notes, String(now.getFullYear()), p(now.getMonth() + 1), `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}-giornata.md`);
  const find = async (pred) => (await win.windows(pid)).find(pred);
  const main = () => find((w) => w.title.includes('QuickNotes') && w.cls !== 'tray_icon_app');
  const capture = () => find((w) => w.title === 'Nota rapida');
  const until = async (fn, ms = 3000) => {
    for (const end = Date.now() + ms; Date.now() < end; await sleep(80)) if (await fn()) return true;
    return false;
  };
  const capturePage = () => page.context().pages().find((x) => x.url().includes('#capture'));

  try {
    await page.waitForSelector('.cm-content');
    await page.waitForTimeout(2200);

    // Nota rapida con il tasto globale: compare in primo piano e riceve i tasti veri.
    await win.keys('ctrl+alt+n');
    assert(await until(async () => (await capture())?.visible && (await capture())?.fg), 'Ctrl Alt N mostra la nota rapida in primo piano');
    await sleep(200);
    await win.type('ciao');
    await sleep(150);
    assert((await capturePage().locator('textarea').inputValue()) === 'ciao', 'il testo scritto arriva nel campo, che ha già il fuoco');
    await win.keys('esc');
    assert(await until(async () => !(await capture())?.visible), 'Esc la nasconde');
    await win.keys('ctrl+alt+n');
    assert(await until(async () => (await capture())?.fg), 'riaprendola torna in primo piano');
    assert((await capturePage().locator('textarea').inputValue()) === 'ciao', 'con il testo di prima');
    await win.type(' mondo');
    await win.keys('ctrl+enter');
    assert(await until(async () => readFileSync(daily, 'utf8').includes('ciao mondo')), 'Ctrl Invio la salva nella nota del giorno');
    assert(await until(async () => !(await capture())?.visible && (await main())?.fg), 'e passa alla finestra principale');

    // Alt F4 nasconde; il clic sull'icona dell'area di notifica la riporta.
    await win.keys('alt+f4');
    assert(await until(async () => !(await main())?.visible), 'Alt F4 nasconde la finestra principale');
    assert(!!(await main()), 'senza chiudere l\'app');
    const tray = await find((w) => w.cls === 'tray_icon_app');
    assert(!!tray, 'l\'icona dell\'area di notifica esiste');
    await win.post(tray.hwnd, WM_TRAY, 0, WM_LBUTTONUP);
    assert(await until(async () => (await main())?.visible), 'il clic sinistro sull\'icona riapre la finestra');

    // Ctrl Alt D: nota del giorno. Ctrl Alt R: per ora un avviso.
    await page.keyboard.press('Control+2');
    await win.keys('ctrl+alt+d');
    assert(await until(async () => (await page.locator('main.pane .tab.on .clip').first().innerText()).startsWith('Oggi')), 'Ctrl Alt D apre la nota del giorno');
    await win.keys('ctrl+alt+r');
    assert(await until(async () => (await page.locator('.toast').count()) && (await page.locator('.toast').innerText()).includes('registrazione')), 'Ctrl Alt R avvisa che la registrazione non c\'è ancora');

    // Menu dell'area di notifica, con il mouse.
    const menuPick = async (label) => {
      await win.post(tray.hwnd, WM_TRAY, 0, WM_RBUTTONUP);
      let items = [];
      await until(async () => (items = await win.menuItems(pid)).length > 0);
      const item = items.find((i) => i.text === label);
      assert(!!item, `il menu ha la voce «${label}» (voci: ${items.map((i) => i.text).join(', ')})`);
      await win.click(item.x, item.y);
    };
    await menuPick('Nota rapida');
    assert(await until(async () => (await capture())?.fg), 'dal menu, «Nota rapida» la mostra in primo piano');
    await win.keys('esc');
    await until(async () => !(await capture())?.visible);

    // Barra del titolo e bordi, con il mouse vero. La finestra va in un punto noto, dentro lo schermo.
    let m = await main();
    await win.move(m.hwnd, 80, 60, 1100, 760);
    await page.waitForTimeout(300);
    m = await main();
    const dpr = await page.evaluate(() => devicePixelRatio);
    const at = async (selector, dx = 0.5, dy = 0.5) => {
      const b = await page.locator(selector).first().boundingBox();
      return [m.ox + (b.x + b.width * dx) * dpr, m.oy + (b.y + b.height * dy) * dpr];
    };
    const [tx, ty] = await at('.titlebar .title', 0.5, 0.5);
    await win.click(tx, ty, 2);
    assert(await until(async () => (await main()).zoomed), 'doppio clic sulla barra del titolo: ingrandita');
    await sleep(300);
    m = await main();
    const [zx, zy] = await at('.titlebar .title', 0.5, 0.5);
    await win.click(zx, zy, 2);
    assert(await until(async () => !(await main()).zoomed), 'secondo doppio clic: ripristinata');
    await sleep(300);
    m = await main();
    const before = m.x;
    const [sx, sy] = await at('.titlebar .title', 0.5, 0.5);
    await win.drag(sx + 60, sy, sx + 260, sy + 40);
    assert(await until(async () => Math.abs((await main()).x - before - 200) < 20), `trascinando la barra la finestra si sposta (${before} → ${(await main()).x})`);
    m = await main();
    const width = m.w;
    const rx = m.x + m.w - 3;
    const ry = m.y + m.h / 2;
    await win.drag(rx, ry, rx + 150, ry);
    assert(await until(async () => (await main()).w - width > 100), `il bordo destro ridimensiona la finestra (${width} → ${(await main()).w})`);

    // Una scheda trascinata con il mouse vero davanti alla prima.
    m = await main();
    await page.keyboard.press('Control+3');
    await page.waitForSelector('.column');
    const tabs = () => page.locator('main.pane .tab .clip').allInnerTexts();
    const first = (await tabs())[0];
    const [ax, ay] = await at('main.pane .tab:has-text("Azioni")', 0.5, 0.5);
    const [fx, fy] = await at('main.pane .tab', 0.15, 0.5);
    await win.drag(ax, ay, fx, fy);
    await page.waitForTimeout(300);
    const order = await tabs();
    assert(order[0] === 'Azioni' && order.includes(first), `trascinata con il mouse, la scheda Azioni diventa la prima: ${order.join(' | ')}`);

    // Esci dal menu: salva e chiude il processo.
    await page.locator('.cm-content').first().click().catch(() => {});
    await menuPick('Esci');
    const gone = await until(async () => {
      try {
        process.kill(pid, 0);
        return false;
      } catch {
        return true;
      }
    }, 5000);
    assert(gone, '«Esci» chiude l\'app');
  } finally {
    win.close();
  }
}
