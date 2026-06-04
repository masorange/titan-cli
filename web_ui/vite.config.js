import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: '../titan_cli/ui_web/static',
        emptyOutDir: true,
    },
});
