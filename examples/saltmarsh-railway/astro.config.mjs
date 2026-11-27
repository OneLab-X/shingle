// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";
import tailwindcss from "@tailwindcss/vite";
import site from "./src/data/site.json" with { type: "json" };

// `site` comes from business.json (via shingle sync.py) so canonical URLs and the sitemap
// always match the business's domain. With 2+ `languages` there is a /<lang>/ copy of every
// page, "/" redirects to the default language, and the sitemap carries hreflang alternates.
const i18n = site.i18n;
const paths = i18n.locales.map((l) => l.path);
const defaultPath = i18n.locales.find((l) => l.code === i18n.default)?.path ?? paths[0];
const base = process.env.SHINGLE_BASE || "/";
// Astro does not add `base` to a redirect target, so do it here.
const rootRedirect = `${base.replace(/\/$/, "")}/${defaultPath}/`;

export default defineConfig({
  // SHINGLE_SITE / SHINGLE_BASE override these for previews served from a sub-folder.
  site: process.env.SHINGLE_SITE || site.business.url,
  base,
  output: "static",
  build: { format: "directory" },
  ...(i18n.enabled && {
    i18n: { defaultLocale: defaultPath, locales: paths, routing: { prefixDefaultLocale: true, redirectToDefaultLocale: false } },
    redirects: { "/": rootRedirect },
  }),
  integrations: [
    sitemap({
      filter: (page) => !page.endsWith("/404/"),
      ...(i18n.enabled && {
        i18n: { defaultLocale: defaultPath, locales: Object.fromEntries(i18n.locales.map((l) => [l.path, l.hreflang])) },
      }),
    }),
  ],
  vite: { plugins: [tailwindcss()] },
});
