// Iniziali e colore dell'avatar, come formatting.initials / avatar_color in Python.
const AVATAR_COLORS = ['#c4553a', '#2961ae', '#1e7b46', '#7444bb', '#a15f0f', '#0e7c86', '#b03a6f'];

export function person(name) {
  const parts = name.trim().replace(/^@/, '').split(/[\s._-]+/).filter(Boolean);
  const initials = parts.slice(0, 2).map((p) => [...p][0]).join('').toUpperCase() || '?';
  const sum = [...name.toLowerCase()].reduce((acc, ch) => acc + ch.codePointAt(0), 0);
  return { name, initials, color: AVATAR_COLORS[sum % AVATAR_COLORS.length] };
}
