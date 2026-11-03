import { mount } from 'svelte';
import './app.css';
import { appReady } from './api.js';

// La stessa pagina serve la finestra principale e la nota rapida: l'hash decide quale parte caricare.
const { default: Root } = location.hash === '#capture' ? await import('./overlays/CaptureWindow.svelte') : await import('./App.svelte');

mount(Root, { target: document.getElementById('app') });

// La finestra resta nascosta finché la pagina non è disegnata: due fotogrammi garantiscono la pittura.
requestAnimationFrame(() => requestAnimationFrame(appReady));
