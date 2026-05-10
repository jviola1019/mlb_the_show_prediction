/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 650
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:7860"
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    exclude: ["node_modules/**", "dist/**", "e2e/**"]
  }
});
