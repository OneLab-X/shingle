# Changelog

## Unreleased

- **Multi-language sites.** With two or more entries in `languages`, Shingle builds `/<lang>/` copies of every page (`/pt/`, `/en/`), a language switcher, absolute reciprocal `hreflang` alternates with `x-default`, self-referencing canonicals, `og:locale:alternate`, sitemap alternates and per-language JSON-LD. `/` redirects to the default language.
- `translations.<lang>` overlays in business.json (Claude drafts, the owner reviews; a visible notice stays until `review` is `"reviewed"`). The validator rejects translated prices, phone numbers, emails, URLs and people's names.
- Interface text in en, pt, es, fr, de and it (`references/ui-strings/`); other languages fall back to English. See `docs/adding-a-language.md`.
- `sync.py --init-i18n`; `audit_site.py` checks hreflang, canonicals, `lang`, page parity, the root redirect and sitemap alternates.
- New example: `barro-e-luz` (Lisbon ceramics shop, pt + en).
- Sub-folder previews (`SHINGLE_BASE`) now produce correct canonicals, og:image and redirects.

## 0.1.0 (2026-11-27)

First public version.

- `/shingle` command and `shingle` skill: intake → classify → interview → design → build → verify → handoff.
- 13 categories, 8 design directions, 22 WCAG AA palettes (20 with dark mode).
- Scripts: `validate_input.py`, `check_contrast.py`, `sync.py` (safe re-runs), `audit_site.py`.
- Astro 7 + Tailwind 4 template with LocalBusiness JSON-LD, Open Graph image, sitemap, live open status, click-to-load map.
- 8 example sites, CI that builds and audits all of them, and a GitHub Pages gallery.
