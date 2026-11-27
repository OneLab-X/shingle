// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import site from "./src/data/site.json" with { type: "json" };

// `site` comes from business.json (via shingle sync.py) so canonical URLs and the sitemap
// always match the business's domain.
export default defineConfig({
  // SHINGLE_SITE / SHINGLE_BASE override these for previews served from a sub-folder.
  site: process.env.SHINGLE_SITE || site.business.url,
  base: process.env.SHINGLE_BASE || "/",
  output: "static",
  build: { format: "directory" },
  integrations: [sitemap({ filter: (page) => !page.endsWith("/404/") })],
  vite: { plugins: [tailwindcss()] },
});
