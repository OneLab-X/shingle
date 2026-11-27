/**
 * Language helpers. Single-language sites: everything resolves to the one language and the
 * output is unchanged. Multi-language sites (business.json `languages` has 2+ entries): data per
 * language comes from src/data/site.<code>.json, interface text from src/data/ui.json.
 */
import defaultSite from "../data/site.json";
import ui from "../data/ui.json";
import { url } from "./url";

type Site = typeof defaultSite;
type Strings = Record<string, string>;
export type Locale = Site["i18n"]["locales"][number];

export const i18n = defaultSite.i18n;
export const locales: Locale[] = i18n.locales;

const files = import.meta.glob("../data/site.*.json", { eager: true, import: "default" }) as Record<string, Site>;
const siteByCode: Record<string, Site> = { [i18n.default]: defaultSite };
for (const [file, data] of Object.entries(files)) {
  const code = file.match(/site\.(.+)\.json$/)?.[1];
  if (code) siteByCode[code] = data;
}

/** Find a locale by language code ("pt-BR") or URL path ("pt-br"). Falls back to the default. */
export const localeOf = (value?: string): Locale =>
  locales.find((l) => l.code === value || l.path === value) ?? locales.find((l) => l.code === i18n.default)!;

export const getSite = (value?: string): Site => siteByCode[localeOf(value).code] ?? defaultSite;

/** Returns t(key, vars): interface text with {placeholders} filled in. */
export function useT(value?: string) {
  const code = localeOf(value).code;
  const dict = (ui as Record<string, Strings>)[code] ?? (ui as Record<string, Strings>)[i18n.default] ?? {};
  return (key: string, vars: Record<string, string | number> = {}): string =>
    (dict[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? `{${name}}`));
}

/** getStaticPaths() for src/pages/[lang]/*.astro. */
export const langPaths = () => locales.map((l) => ({ params: { lang: l.path }, props: { lang: l.code } }));

const base = import.meta.env.BASE_URL.replace(/\/$/, "");

/** "/my-repo/pt/contact/" -> { lang: "pt", rest: "/contact/" } (lang undefined on single-language sites). */
export function splitPath(pathname: string): { lang?: string; rest: string } {
  const withoutBase = pathname.startsWith(base) ? pathname.slice(base.length) || "/" : pathname;
  const [, first = "", ...tail] = withoutBase.split("/");
  const match = i18n.enabled ? locales.find((l) => l.path === first) : undefined;
  return match ? { lang: match.code, rest: `/${tail.join("/")}` } : { rest: withoutBase };
}

/** The same page in another language: pathIn("/pt/contact/", "en") -> "/en/contact/". */
export const pathIn = (pathname: string, target: Locale): string => url(splitPath(pathname).rest, target.path);

/** Internal link in the current language: lurl("/contact/", Astro.currentLocale). */
export const lurl = (path: string, value?: string): string => url(path, i18n.enabled ? localeOf(value).path : undefined);
