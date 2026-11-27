/**
 * 1200x630 social preview card rendered at build time from business.json and the palette.
 * Replace with a real photo later by deleting this file and adding public/og.png.
 */
import type { APIRoute } from "astro";
import sharp from "sharp";
import site from "../data/site.json";

const escape = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

function wrap(text: string, max: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(/\s+/)) {
    if ((line + " " + word).trim().length > max && line) {
      lines.push(line);
      line = word;
    } else line = (line + " " + word).trim();
  }
  if (line) lines.push(line);
  return lines.slice(0, 3);
}

export const GET: APIRoute = async () => {
  const { business } = site;
  const c = site.theme.colors.light ?? { background: "#FFFFFF", text: "#111111", primary: "#222222", muted: "#555555", accent: "#DDDDDD" };
  const nameLines = wrap(business.name ?? "", 22);
  const size = nameLines.length > 2 ? 76 : 92;
  const place = [business.category_label, business.address?.locality].filter(Boolean).join(" · ");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="${c.background}"/>
<rect x="0" y="0" width="24" height="630" fill="${c.primary}"/>
<rect x="88" y="96" width="120" height="10" fill="${c.accent}"/>
${nameLines
  .map((l, i) => `<text x="88" y="${210 + i * (size * 1.08)}" font-family="Georgia, 'Times New Roman', serif" font-size="${size}" font-weight="700" fill="${c.text}">${escape(l)}</text>`)
  .join("\n")}
<text x="88" y="540" font-family="Helvetica, Arial, sans-serif" font-size="34" fill="${c.muted}">${escape(place)}</text>
${business.domain ? `<text x="1112" y="540" text-anchor="end" font-family="Helvetica, Arial, sans-serif" font-size="30" fill="${c.primary}">${escape(business.domain)}</text>` : ""}
</svg>`;
  const png = await sharp(Buffer.from(svg)).png().toBuffer();
  return new Response(new Uint8Array(png), { headers: { "Content-Type": "image/png" } });
};
