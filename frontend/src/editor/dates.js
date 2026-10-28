// Etichette delle scadenze, come formatting.due_badge in Python.
const MONTHS = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];

export function dueBadge(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  const due = new Date(y, m - 1, d);
  if (Number.isNaN(due.getTime())) return [iso, ''];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((due - today) / 86400000);
  const short = `${d} ${MONTHS[m - 1]}`;
  if (days < 0) return [`Scaduta il ${short}`, 'danger'];
  if (days === 0) return ['Oggi', 'warning'];
  if (days === 1) return ['Domani', 'warning'];
  return [short, ''];
}

export function clock() {
  const now = new Date();
  return `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
}
