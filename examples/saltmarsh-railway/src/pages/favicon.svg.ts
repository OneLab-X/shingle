/** Monogram favicon generated from the business name and palette at build time. */
import type { APIRoute } from "astro";
import site from "../data/site.json";

const escape = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

export const GET: APIRoute = () => {
  const words = (site.business.name ?? "S").replace(/[^\p{L}\p{N}\s]/gu, "").split(/\s+/).filter(Boolean);
  const initials = (words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? "S").slice(0, 2)).toUpperCase();
  const c = site.theme.colors.light ?? { primary: "#222222", on_primary: "#FFFFFF" };
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="14" fill="${c.primary}"/>
<text x="32" y="33" text-anchor="middle" dominant-baseline="central" font-family="Georgia, 'Times New Roman', serif" font-size="${initials.length > 1 ? 28 : 36}" font-weight="700" fill="${c.on_primary}">${escape(initials)}</text>
</svg>`;
  return new Response(svg, { headers: { "Content-Type": "image/svg+xml" } });
};
