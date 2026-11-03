import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig({
  plugins: [svelte()],
  clearScreen: false,
  server: { port: 5173, strictPort: true },
  build: {
    target: 'chrome110',
    cssCodeSplit: true,
    // La prima schermata non precarica i blocchi di editor e viste.
    modulePreload: { polyfill: false },
  },
});
