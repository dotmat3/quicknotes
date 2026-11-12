<script>
  // La stanza di Micio: il gatto usa gli oggetti comprati, il negozio li vende in crocchette, il minigioco ne fa
  // guadagnare. Mentre questa vista è aperta Micio vive qui e non in fondo alle schede.
  import { onDestroy, onMount } from 'svelte';
  import { brain } from '../pet/brain.svelte.js';
  import { COATS, ITEMS, NAME_MAX, PER_ACTION, coins, pet, petCheck, petName, savePet } from '../pet/store.svelte.js';
  import Cat from '../pet/Cat.svelte';
  import Oggetto from '../pet/Oggetto.svelte';
  import Icon from '../shell/Icon.svelte';

  const ROOM_H = 380;
  const FLOOR = 40; // dove poggiano le zampe, dal basso della stanza
  let room = $state();

  onMount(() => {
    pet.roomOpen = true;
    petCheck();
  });
  onDestroy(() => {
    stopLoop();
    if (brain.context === 'game') brain.context = 'room';
    pet.roomOpen = false;
  });

  // ---- negozio
  const ORDER = ['tappeto', 'quadro', 'lampada', 'scatola', 'cuscino', 'ciotola', 'pianta', 'tiragraffi', 'gomitolo'];
  const placed = $derived(
    ORDER.map((id) => ITEMS.find((i) => i.id === id)).filter((i) => pet.placed[i.id] && !(i.id === 'gomitolo' && (brain.usingYarn || game.on))),
  );
  function itemStyle(i) {
    const where = i.at === 'wall' ? 'top:52px' : i.at === 'ceiling' ? 'top:0' : i.at === 'rug' ? `bottom:${FLOOR - 6}px` : `bottom:${FLOOR}px`;
    return `left:calc(${i.x}% - ${i.w / 2}em); ${where}`;
  }
  function buy(i) {
    if (pet.owned[i.id]) {
      pet.placed = { ...pet.placed, [i.id]: !pet.placed[i.id] };
      savePet();
      return;
    }
    if (coins() < i.price) return;
    pet.spent += i.price;
    pet.owned = { ...pet.owned, [i.id]: true };
    pet.placed = { ...pet.placed, [i.id]: true };
    savePet();
    if (!game.on) setTimeout(() => brain.useItem(i), 400);
  }

  // ---- Micio
  // Il nome si salva mentre lo si scrive; uscendo dal campo si tolgono gli spazi in più.
  function setName(e) {
    pet.name = e.currentTarget.value.slice(0, NAME_MAX);
    savePet();
  }
  function tidyName() {
    const n = pet.name.trim().replace(/\s+/g, ' ');
    if (n === pet.name) return;
    pet.name = n;
    savePet();
  }
  function setCoat(c) {
    pet.coat = c;
    savePet();
  }
  function setScale(e) {
    pet.scale = Number(e.currentTarget.value);
    savePet();
  }
  function setOut(v) {
    pet.out = v;
    savePet();
  }
  function poke() {
    if (game.on) return;
    brain.cheer('ti saluta', `Miao! Hai ${coins()} crocchette.`);
  }

  // ---- minigioco: pioggia di pesci
  const game = $state({ on: false, over: false, t: 30, score: 0, fish: [], tx: 50, scared: 0, last: 0, spawn: 0.4, seq: 0, result: 0, pops: [] });
  let raf = 0;
  function stopLoop() {
    cancelAnimationFrame(raf);
    raf = 0;
  }
  function startGame() {
    stopLoop();
    Object.assign(game, { on: true, over: false, t: 30, score: 0, fish: [], tx: 50, scared: 0, spawn: 0.4, pops: [] });
    brain.clear();
    brain.context = 'game';
    brain.bubble = '';
    brain.hearts = false;
    brain.toPose('stand', () => {
      brain.act = 'aspetta i pesci';
      game.last = performance.now();
      raf = requestAnimationFrame(tick);
    });
  }
  function tick(now) {
    if (!game.on) return;
    const dt = Math.min(0.05, (now - game.last) / 1000);
    game.last = now;
    const w = room?.clientWidth || 900;
    const s = pet.scale;
    const catchTop = ROOM_H - FLOOR - 22 * s, catchBottom = ROOM_H - FLOOR;
    const half = ((11 * s) / w) * 100;
    const kept = [];
    let hit = false;
    for (const f of game.fish) {
      f.y += f.v * dt;
      const mid = f.y + 2.5 * s;
      if (game.scared <= 0 && mid > catchTop && mid < catchBottom && Math.abs(f.x - brain.x) < half) {
        const gain = f.kind === 'oro' ? 3 : f.kind === 'cetriolo' ? -2 : 1;
        game.score = Math.max(0, game.score + gain);
        if (f.kind === 'cetriolo') hit = true;
        game.pops.push({ id: ++game.seq, x: f.x, text: gain > 0 ? `+${gain}` : String(gain), good: gain > 0, until: now + 900 });
      } else if (f.y < ROOM_H) kept.push(f);
    }
    game.spawn -= dt;
    if (game.spawn <= 0) {
      const r = Math.random();
      const kind = r < 0.12 ? 'oro' : r < 0.26 ? 'cetriolo' : 'pesce';
      kept.push({ id: ++game.seq, x: 6 + Math.random() * 88, y: -20, v: (kind === 'oro' ? 170 : 105) + Math.random() * 60, kind });
      game.spawn = 0.55 + Math.random() * 0.35;
    }
    game.fish = kept;
    game.pops = game.pops.filter((p) => p.until > now);
    game.t -= dt;
    if (game.t <= 0) return endGame(true);

    if (hit) {
      // Il cetriolo lo spaventa: si siede di colpo e si rialza.
      game.scared = 1;
      brain.set('sitdown', 'si è spaventato per un cetriolo');
    } else if (game.scared > 0) {
      const before = game.scared;
      game.scared = Math.max(0, game.scared - dt);
      if (before > 0.5 && game.scared <= 0.5) brain.set('standup', 'si rialza');
    } else {
      const maxStep = 40 * dt;
      const dx = Math.max(-maxStep, Math.min(maxStep, game.tx - brain.x));
      const anim = Math.abs(dx) > maxStep * 0.6 ? 'run' : Math.abs(dx) > 0.15 ? 'walk' : 'stand';
      if (brain.anim !== anim) { brain.anim = anim; brain.pose = 'stand'; brain.arc = ''; }
      if (dx > 0.05) brain.dir = 1;
      else if (dx < -0.05) brain.dir = -1;
      brain.dur = 0;
      brain.x = Math.max(4, Math.min(96, brain.x + dx));
      brain.act = 'acchiappa i pesci';
    }
    raf = requestAnimationFrame(tick);
  }
  function endGame(finished) {
    stopLoop();
    if (!game.on) return;
    game.on = false;
    brain.context = 'room';
    brain.clear();
    if (finished) {
      game.over = true;
      game.result = game.score;
      pet.bonus += game.score;
      pet.best = Math.max(pet.best, game.score);
      savePet();
      if (game.score > 0) brain.pounce('è soddisfatto', () => brain.sitFor('sit', 'si lecca i baffi', 4000));
      else brain.sitFor('sit', 'ci riproverà', 3000);
    } else brain.next();
  }
  const steer = (tx) => (game.tx = Math.max(4, Math.min(96, tx)));
  function pointer(e) {
    if (!game.on) return;
    const r = e.currentTarget.getBoundingClientRect();
    steer(((e.clientX - r.left) / r.width) * 100);
  }
  function key(e) {
    if (!game.on) return;
    if (e.key === 'ArrowLeft') { e.preventDefault(); steer(game.tx - 12); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); steer(game.tx + 12); }
    else if (e.key === 'Escape') { e.preventDefault(); endGame(false); }
  }

  const OUT = [['walk', 'Passeggia'], ['play', 'Gioca'], ['off', 'Nascosto']];
</script>

<svelte:window onkeydown={key} />

<div class="head">
  <div class="titles">
    <h1>La stanza di {petName()}</h1>
    <div class="sub" role="status">{petName()} {brain.act}</div>
  </div>
  <div class="coins" title="{PER_ACTION} crocchette per ogni azione completata"><svg viewBox="0 0 5 5" width="15" height="15" aria-hidden="true"><path d="M1 0h3v5H1zM0 1h5v3H0z" fill="#E8A84A" /><path d="M2 1h1v3H2z" fill="#B97F2C" /></svg>{coins()} crocchette</div>
</div>

<section class="room" aria-label="La stanza" bind:this={room} onpointermove={pointer} style="height:{ROOM_H}px">
  <div class="wall" aria-hidden="true"></div>
  <div class="floor" aria-hidden="true"></div>
  {#if pet.placed.lampada}<div class="glow" aria-hidden="true"></div>{/if}
  <div class="items" aria-hidden="true" style="font-size:{pet.scale}px">
    <div class="it" style="left:7%; top:56px"><Oggetto id="finestra" size={pet.scale} /></div>
    {#each placed as i (i.id)}
      <div class="it" style={itemStyle(i)}><Oggetto id={i.id} size={pet.scale} /></div>
    {/each}
  </div>

  {#if brain.context === 'room' || brain.context === 'game'}
    <Cat bottom="{FLOOR}px" onpoke={poke} />
  {/if}

  {#if game.on}
    {#each game.fish as f (f.id)}
      <div class="fall" aria-hidden="true" style="left:calc({f.x}% - {4 * pet.scale}px); top:{f.y}px"><Oggetto id={f.kind} size={pet.scale} /></div>
    {/each}
    {#each game.pops as p (p.id)}
      <span class="plus" class:bad={!p.good} aria-hidden="true" style="left:calc({p.x}% - 12px); bottom:{FLOOR + 24 * pet.scale}px">{p.text}</span>
    {/each}
    <div class="hud">
      <span class="chip" role="timer">{Math.ceil(game.t)} s</span>
      <span class="chip gold" role="status">{game.score} pesci</span>
    </div>
    <button class="pxbtn quit" type="button" onclick={() => endGame(false)}>Esci</button>
    <button class="pxbtn arrow left" type="button" aria-label="Sposta {petName()} a sinistra" onclick={() => steer(game.tx - 14)}>&lt;</button>
    <button class="pxbtn arrow right" type="button" aria-label="Sposta {petName()} a destra" onclick={() => steer(game.tx + 14)}>&gt;</button>
  {/if}

  {#if game.over}
    <div class="result" role="dialog" aria-label="Fine della partita">
      <div class="rt">FINE DELLA PIOGGIA</div>
      <div class="rs">{game.result} pesci</div>
      <div>+{game.result} crocchette · record {pet.best}</div>
      <div class="rb">
        <button class="pxbtn gold" type="button" onclick={startGame}>Rigioca</button>
        <button class="pxbtn" type="button" onclick={() => (game.over = false)}>Chiudi</button>
      </div>
    </div>
  {/if}
</section>

<div class="below">
  <section class="card shop" aria-label="Negozio">
    <div class="ch"><h2>Negozio</h2><span class="sub">{PER_ACTION} crocchette per ogni azione completata, più quelle del minigioco.</span></div>
    <div class="grid">
      {#each ITEMS as i (i.id)}
        {@const owned = !!pet.owned[i.id]}
        {@const inRoom = !!pet.placed[i.id]}
        {@const short = !owned && coins() < i.price}
        <div class="item" class:in={inRoom}>
          <div class="pic"><Oggetto id={i.id} fit={56} /></div>
          <div><div class="name">{i.name}</div><div class="desc">{i.desc}</div></div>
          <button class="buy" class:primary={!owned && !short} class:pressed={owned && inRoom} type="button" disabled={short} aria-pressed={owned ? inRoom : undefined} onclick={() => buy(i)}>
            {owned ? (inRoom ? 'Nella stanza' : 'Metti nella stanza') : short ? `Mancano ${i.price - coins()}` : `Compra · ${i.price}`}
          </button>
        </div>
      {/each}
    </div>
  </section>

  <div class="side">
    <section class="card" aria-label={petName()}>
      <h2>{petName()}</h2>
      <label class="lab" for="micio-name">Nome</label>
      <input id="micio-name" class="name-in" type="text" maxlength={NAME_MAX} autocomplete="off" spellcheck="false" placeholder="Micio" value={pet.name} oninput={setName} onblur={tidyName} onkeydown={(e) => { if (e.key === 'Enter' || e.key === 'Escape') e.currentTarget.blur(); }} />
      <div class="lab">Mantello</div>
      <div class="swatches" role="radiogroup" aria-label="Colore del mantello">
        {#each COATS as [name, hex] (hex)}
          <button type="button" role="radio" aria-checked={pet.coat.toLowerCase() === hex.toLowerCase()} aria-label={name} title={name} class="sw" class:on={pet.coat.toLowerCase() === hex.toLowerCase()} style="background:{hex}" onclick={() => setCoat(hex)}></button>
        {/each}
        <label class="sw custom" title="Altro colore"><Icon name="plus" size={12} /><input type="color" aria-label="Altro colore" value={pet.coat} onchange={(e) => setCoat(e.currentTarget.value)} /></label>
      </div>
      <label class="lab row" for="micio-size"><span>Dimensione</span><span class="mono">{pet.scale}× · {32 * pet.scale} px</span></label>
      <input id="micio-size" type="range" min="2" max="6" step="1" value={pet.scale} oninput={setScale} />
      <div class="lab">Fuori dalla stanza, in fondo alle schede</div>
      <div class="seg" role="radiogroup" aria-label="Cosa fa {petName()} fuori dalla stanza">
        {#each OUT as [v, label] (v)}
          <button type="button" role="radio" aria-checked={pet.out === v} class:on={pet.out === v} onclick={() => setOut(v)}>{label}</button>
        {/each}
      </div>
    </section>

    <section class="card" aria-label="Minigioco">
      <div class="ch"><h2>Pioggia di pesci</h2><span class="sub mono">record {pet.best}</span></div>
      <p class="sub">30 secondi. Muovi {petName()} con il mouse o con le frecce: ogni pesce è una crocchetta, quello d’oro ne vale tre. Attento ai cetrioli.</p>
      <button class="pxbtn gold wide" type="button" disabled={game.on} onclick={startGame}>Gioca</button>
    </section>
  </div>
</div>

<style>
  .head { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px 20px; margin-bottom: 16px; }
  .titles { flex: 1 1 260px; }
  .sub { font-size: 13px; color: var(--subtle); }
  .mono { font-family: 'Geist Mono', monospace; }
  .coins { display: flex; align-items: center; gap: 8px; height: 36px; padding: 0 14px; border-radius: 10px; background: var(--raised); border: 1px solid var(--border2); font-family: 'Geist Mono', monospace; font-size: 14px; color: var(--accent); }
  .room { position: relative; border-radius: 14px; overflow: hidden; border: 1px solid var(--border2); touch-action: none; user-select: none; }
  .wall { position: absolute; inset: 0 0 92px 0; background-color: #262830; background-image: radial-gradient(#2f323b 1.5px, transparent 1.6px); background-size: 22px 22px; }
  .floor { position: absolute; left: 0; right: 0; bottom: 0; height: 92px; border-top: 5px solid #1c1d22; background-color: #3a2e26; background-image: repeating-linear-gradient(90deg, transparent 0 62px, #2e241d 62px 65px), repeating-linear-gradient(0deg, transparent 0 28px, #33281f 28px 30px); }
  .glow { position: absolute; inset: 0; background: radial-gradient(circle at 38% 34%, rgba(242, 193, 122, 0.2), rgba(242, 193, 122, 0) 55%); }
  .items { position: absolute; inset: 0; }
  .it { position: absolute; }
  .fall { position: absolute; animation: wiggle 0.5s steps(2) infinite; }
  @keyframes wiggle { 0%, 100% { transform: rotate(-6deg); } 50% { transform: rotate(6deg); } }
  .plus { position: absolute; font-family: 'Geist Mono', monospace; font-weight: 600; font-size: 15px; color: #f2c17a; text-shadow: 2px 2px 0 #141518; animation: up 0.9s steps(6) forwards; }
  .plus.bad { color: #7cc4a8; }
  @keyframes up { 0% { opacity: 0; transform: translateY(0); } 15% { opacity: 1; } 100% { opacity: 0; transform: translateY(-46px); } }
  .hud { position: absolute; left: 12px; top: 12px; display: flex; gap: 8px; }
  .chip { padding: 4px 10px; background: #141518; color: #eceae4; border: 2px solid #eceae4; box-shadow: 3px 3px 0 #000; font-family: 'Geist Mono', monospace; font-size: 13px; }
  .chip.gold { border-color: #f2c17a; color: #f2c17a; }
  .pxbtn { height: 34px; padding: 0 14px; border: 2px solid #141518; background: #eceae4; color: #141518; font-weight: 600; box-shadow: 3px 3px 0 #000; }
  .pxbtn.gold { background: #f2c17a; }
  .pxbtn.wide { width: 100%; height: 38px; margin-top: 12px; }
  .pxbtn:disabled { opacity: 0.5; cursor: default; }
  .quit { position: absolute; right: 12px; top: 12px; background: #141518; color: #eceae4; border-color: #eceae4; }
  .arrow { position: absolute; bottom: 12px; width: 48px; height: 44px; background: #141518; color: #eceae4; border-color: #eceae4; font-family: 'Geist Mono', monospace; font-size: 16px; }
  .arrow.left { left: 12px; }
  .arrow.right { right: 12px; }
  .result { position: absolute; left: 50%; top: 70px; translate: -50% 0; width: 300px; max-width: calc(100% - 24px); padding: 18px; background: #eceae4; color: #141518; border: 3px solid #141518; box-shadow: 5px 5px 0 #000; text-align: center; font-size: 13.5px; }
  .rt { font-family: 'Geist Mono', monospace; font-size: 13px; font-weight: 600; letter-spacing: 0.04em; }
  .rs { margin: 8px 0 2px; font-size: 22px; font-weight: 700; }
  .rb { display: flex; justify-content: center; gap: 8px; margin-top: 14px; }
  .below { display: flex; flex-wrap: wrap; gap: 16px; margin-top: 16px; align-items: flex-start; }
  .card { padding: 16px; border-radius: 14px; background: var(--card); border: 1px solid var(--border); }
  .shop { flex: 999 1 420px; min-width: 0; }
  .side { flex: 1 1 280px; display: flex; flex-direction: column; gap: 16px; }
  h2 { margin: 0; font-size: 16px; font-weight: 600; }
  .card > h2 { margin-bottom: 12px; }
  .ch { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin-bottom: 12px; }
  .card p.sub { margin: 6px 0 0; line-height: 1.5; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .item { display: flex; flex-direction: column; gap: 8px; padding: 10px; border-radius: 10px; background: var(--raised); border: 1px solid var(--border2); }
  .item.in { border-color: var(--border3); }
  .pic { height: 64px; display: flex; align-items: center; justify-content: center; border-radius: 8px; background: #262830; }
  .name { font-size: 13.5px; font-weight: 600; }
  .desc { font-size: 12px; color: var(--subtle); }
  .buy { height: 32px; padding: 0 10px; border: 1px solid var(--border3); border-radius: 8px; background: transparent; font-size: 12.5px; font-weight: 600; }
  .buy.primary { background: var(--accent); border-color: var(--accent); color: var(--on-accent); }
  .buy.pressed { background: var(--hover); }
  .buy:disabled { color: var(--faint); cursor: default; }
  .lab { margin-top: 14px; font-size: 12px; color: var(--subtle); }
  .card > h2 + .lab { margin-top: 0; }
  .name-in { display: block; width: 100%; height: 32px; margin-top: 6px; padding: 0 10px; border: 1px solid var(--border2); border-radius: 8px; background: var(--surface); color: var(--text); font: inherit; font-size: 13.5px; outline: none; }
  .name-in:focus { border-color: var(--accent); }
  .lab.row { display: flex; justify-content: space-between; }
  .swatches { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
  .sw { width: 26px; height: 26px; padding: 0; border-radius: 6px; border: 1px solid var(--border3); }
  .sw.on { border: 2px solid var(--text); }
  .custom { position: relative; display: flex; align-items: center; justify-content: center; border-style: dashed; color: var(--subtle); cursor: pointer; }
  .custom input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
  input[type='range'] { width: 100%; margin-top: 6px; accent-color: var(--accent); }
  .seg { display: flex; padding: 2px; margin-top: 6px; border-radius: 9px; background: var(--raised); border: 1px solid var(--border); }
  .seg button { flex: 1; height: 30px; border: 0; border-radius: 7px; background: transparent; color: var(--muted); font-size: 12.5px; }
  .seg button.on { background: var(--border2); color: var(--text); }
  @media (prefers-reduced-motion: reduce) { .fall, .plus { animation: none; } }
</style>
