// Ponte verso Python: i metodi della classe Api di quicknotes/webapp.py, esposti da pywebview.
// Aperta nel browser con ?mock (anteprima senza Python) usa dati finti in memoria.

let ready;

function backend() {
  ready ??= new Promise((resolve) => {
    if (window.pywebview?.api) return resolve(window.pywebview.api);
    window.addEventListener('pywebviewready', () => resolve(window.pywebview.api), { once: true });
    if (new URLSearchParams(location.search).has('mock')) import('./mock.js').then((m) => resolve(m.mockApi));
  });
  return ready;
}

export async function call(name, ...args) {
  const api = await backend();
  return api[name](...args);
}
