import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import cesium from "vite-plugin-cesium";

export default defineConfig({
  // vite-plugin-cesium copies Cesium's static Assets/Widgets/Workers into
  // the build output and sets window.CESIUM_BASE_URL automatically.
  plugins: [react(), cesium()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
});
