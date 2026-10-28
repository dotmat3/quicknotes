import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Il build finisce dentro il pacchetto Python: l'app installata non ha bisogno di Node.
export default defineConfig({
  plugins: [svelte()],
  base: './',
  server: { port: 5173, strictPort: true },
  build: { outDir: '../quicknotes/webui', emptyOutDir: true, target: 'chrome110', chunkSizeWarningLimit: 1000 },
});
