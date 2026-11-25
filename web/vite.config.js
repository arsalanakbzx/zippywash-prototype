import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" so the built site works from any folder, e.g. https://<user>.github.io/zippywash-prototype/
export default defineConfig({ plugins: [react()], base: "./" });
