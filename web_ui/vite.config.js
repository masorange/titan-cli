var _a;
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
var backendTarget = (_a = process.env.VITE_TITAN_BACKEND_TARGET) !== null && _a !== void 0 ? _a : 'http://127.0.0.1:8765';
export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            '/ws': {
                target: backendTarget,
                ws: true,
            },
            '/healthz': {
                target: backendTarget,
            },
        },
    },
    build: {
        outDir: '../titan_cli/ui_web/static',
        emptyOutDir: true,
    },
});
