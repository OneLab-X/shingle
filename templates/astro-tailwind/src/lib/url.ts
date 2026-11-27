/**
 * Prefix an internal path with the site's base path (set SHINGLE_BASE when the site is served
 * from a sub-folder, e.g. a GitHub Pages project site) and, on multi-language sites, with the
 * language: url("/contact/", "pt") -> "/pt/contact/" or "/my-repo/pt/contact/".
 * `lang` is a language path ("pt", "pt-br"). Leave it out on single-language sites.
 */
const base = import.meta.env.BASE_URL.replace(/\/$/, "");
export const url = (path: string, lang?: string): string =>
  path.startsWith("/") ? `${base}${lang ? `/${lang}` : ""}${path}` : path;
