import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development /api is proxied to the FastAPI server; in production the frontend calls
// VITE_API_BASE_URL, or the same origin when it is empty (the Vercel deployment).
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: { output: { manualChunks: { react: ["react", "react-dom"], charts: ["recharts"] } } },
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
