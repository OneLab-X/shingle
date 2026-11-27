/**
 * Prefix an internal path with the site's base path (set SHINGLE_BASE when the site is served
 * from a sub-folder, e.g. a GitHub Pages project site). url("/contact/") -> "/contact/" or
 * "/my-repo/contact/".
 */
const base = import.meta.env.BASE_URL.replace(/\/$/, "");
export const url = (path: string): string => (path.startsWith("/") ? `${base}${path}` : path);
