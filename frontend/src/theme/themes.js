// I sei temi della tavola Home, il Personalizzato e l'Automatico. Si applicano come variabili CSS.

export const THEMES = {
  grafite: { name: 'Grafite', dark: true, t: { bar: '#111214', sunk: '#121315', surface: '#141518', card: '#16171A', chrome: '#17181B', raised: '#1F2025', dots: '#202227', hover: '#24262C', border: '#222428', border2: '#2B2E35', border3: '#353841', line: '#1F2125', text: '#ECEAE4', text2: '#D9D6CF', muted: '#B4B1A9', subtle: '#96938C', faint: '#6E6B65', faint2: '#5E5C57', person: '#8DB4F0', late: '#F0956E', dec: '#C9A0F0' }, accent: '#E8A84A' },
  mezzanotte: { name: 'Mezzanotte', dark: true, t: { bar: '#0B0E14', sunk: '#0D1118', surface: '#0F131B', card: '#131925', chrome: '#141A25', raised: '#1A2130', dots: '#1C2433', hover: '#212A3B', border: '#1E2533', border2: '#283246', border3: '#34405A', line: '#1A2130', text: '#E6EAF2', text2: '#CBD3E1', muted: '#A5B0C4', subtle: '#8A96AD', faint: '#67728A', faint2: '#545E73', person: '#8DB4F0', late: '#F29A76', dec: '#C3A2F2' }, accent: '#7FB2FF' },
  salvia: { name: 'Salvia', dark: true, t: { bar: '#0F1311', sunk: '#101512', surface: '#121714', card: '#151B17', chrome: '#161C18', raised: '#1D2520', dots: '#1F2822', hover: '#232D26', border: '#202923', border2: '#2A352E', border3: '#36443A', line: '#1D2520', text: '#E8EDE8', text2: '#D0D8D1', muted: '#AEB8B0', subtle: '#919C93', faint: '#6C776E', faint2: '#59635B', person: '#8DB4F0', late: '#F0956E', dec: '#C9A0F0' }, accent: '#7CC4A8' },
  lavanda: { name: 'Lavanda', dark: false, t: { bar: '#E9E2F3', sunk: '#F3EFF9', surface: '#FCFAFE', card: '#F6F2FB', chrome: '#EEE8F6', raised: '#F2EDF9', dots: '#D9CFE8', hover: '#E4DCF0', border: '#E2DAEE', border2: '#D3C8E3', border3: '#BFB1D4', line: '#EAE4F3', text: '#231C2E', text2: '#3A3147', muted: '#5A4F6B', subtle: '#716685', faint: '#8E84A1', faint2: '#A59CB6', person: '#3B63C9', late: '#C0532A', dec: '#7A3FC0' }, accent: '#BF5612' },
  carta: { name: 'Carta', dark: false, t: { bar: '#ECE9E2', sunk: '#F4F2ED', surface: '#FDFCF9', card: '#F7F5F0', chrome: '#EFECE5', raised: '#F3F1EB', dots: '#DDD8CD', hover: '#E6E2D9', border: '#E3DFD6', border2: '#D6D1C6', border3: '#C4BEB1', line: '#ECE8E0', text: '#1F1E1B', text2: '#34322D', muted: '#57544C', subtle: '#6F6B62', faint: '#8C887E', faint2: '#A29E94', person: '#2F6BC4', late: '#C0532A', dec: '#8A52C7' }, accent: '#A3640A' },
  nebbia: { name: 'Nebbia', dark: false, t: { bar: '#E7EAEE', sunk: '#F2F4F7', surface: '#FFFFFF', card: '#F6F7F9', chrome: '#EDF0F3', raised: '#F1F3F6', dots: '#D7DCE3', hover: '#E2E6EC', border: '#DFE3E9', border2: '#D0D6DE', border3: '#BCC4CF', line: '#E9ECF0', text: '#1A1D23', text2: '#2E333C', muted: '#4F5663', subtle: '#697080', faint: '#8A909D', faint2: '#A1A7B2', person: '#2563C9', late: '#C2481F', dec: '#7C45C4' }, accent: '#3B6FE0' },
};

// Testo sopra l'accento: scuro o chiaro in base alla luminanza.
export function onAccent(hex) {
  const n = parseInt(hex.replace('#', ''), 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2] > 0.36 ? '#141518' : '#FFFFFF';
}

const systemDark = () => matchMedia('(prefers-color-scheme: dark)').matches;

// `id` può essere anche un valore della versione precedente: auto, light, dark.
export function resolveTheme(id, custom) {
  if (id === 'custom') {
    const c = custom ?? {};
    const base = THEMES[c.base === 'chiaro' ? 'carta' : 'grafite'];
    const t = { ...base.t };
    if (c.chrome) t.chrome = c.chrome;
    if (c.surface) {
      t.surface = c.surface;
      t.card = c.surface;
    }
    if (c.text) t.text = c.text;
    return { t, accent: c.accent ?? base.accent, dark: base.dark };
  }
  if (id === 'light') return THEMES.carta;
  if (id === 'dark') return THEMES.grafite;
  return THEMES[id] ?? (systemDark() ? THEMES.grafite : THEMES.carta);
}

export function applyTheme(theme) {
  const s = document.documentElement.style;
  for (const [k, v] of Object.entries(theme.t)) s.setProperty(`--${k}`, v);
  s.setProperty('--accent', theme.accent);
  s.setProperty('--on-accent', onAccent(theme.accent));
  s.setProperty('color-scheme', theme.dark ? 'dark' : 'light');
}

// Colori delle etichette: tinta per i temi scuri, tinta per i temi chiari, nome.
export const TAG_PALETTE = {
  ambra: ['#E8A84A', '#7F4C04', 'Ambra'],
  corallo: ['#F28B7D', '#A12D22', 'Corallo'],
  rosa: ['#EE8FBD', '#9C2465', 'Rosa'],
  viola: ['#C3A2F2', '#7238B8', 'Viola'],
  blu: ['#8DB4F0', '#2259BA', 'Blu'],
  ciano: ['#5CC6D0', '#0A6370', 'Ciano'],
  verde: ['#7CC48F', '#1F6937', 'Verde'],
  oliva: ['#BDC46A', '#535C12', 'Oliva'],
  grigio: ['#B4B1A9', '#5C5951', 'Grigio'],
};

const key = (tag) => String(tag).trim().replace(/^#/, '').toLowerCase();

// Il colore scelto, oppure uno stabile ricavato dal nome. `#progetto/area` prende il colore di `#progetto`,
// così un progetto ha un solo colore anche quando si scrive con l'area.
export function tagColorId(tag, chosen = {}) {
  let k = key(tag);
  if (TAG_PALETTE[chosen[k]]) return chosen[k];
  if (k.includes('/')) {
    k = k.slice(0, k.indexOf('/'));
    if (TAG_PALETTE[chosen[k]]) return chosen[k];
  }
  const ids = Object.keys(TAG_PALETTE);
  let sum = 0;
  for (const c of k) sum += c.codePointAt(0);
  return ids[sum % ids.length];
}

export function tagHex(tag, chosen, dark) {
  return TAG_PALETTE[tagColorId(tag, chosen)][dark ? 0 : 1];
}
