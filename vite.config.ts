import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5178,
    proxy: {
      "/api": "http://127.0.0.1:8118",
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4178,
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
