import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import viteCompression from "vite-plugin-compression";
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    viteCompression({
      algorithm: "gzip",
      ext: ".gz",
      threshold: 10240,
    }),
    mode === "analyze" &&
      visualizer({
        open: true,
        filename: "dist/stats.html",
        gzipSize: true,
        brotliSize: true,
      }),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  optimizeDeps: {
    include: ["react", "react-dom", "axios", "@tanstack/react-query"],
  },
  build: {
    target: "esnext",
    minify: "esbuild",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          "react-vendor": ["react", "react-dom", "react-router-dom"],
          "ui-vendor": ["framer-motion", "lucide-react", "sonner"],
          "data-vendor": ["@tanstack/react-query", "axios", "zustand"],
        },
      },
    },
  },
  server: {
    port: 3000,
    strictPort: true,
    headers: {
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
      "Referrer-Policy": "strict-origin-when-cross-origin",
    },
    // MOVED INSIDE SERVER:
    proxy: {
      "/api": {
        target: "http://localhost:8080", // Matches your backend PORT=8080
        changeOrigin: true,
        secure: false,
      },
    },
  },
}));
