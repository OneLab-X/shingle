# Changelog

## Unreleased

- **Landing page is now a how-to-use guide.** The gallery index opens with ten steps (install and run, check intake, confirm category, interview, palette and direction, preview, add photos, audit and placeholders, deploy, update later), each with a screenshot and the command to run, then what every site includes, then the examples. Images are real script output and real built-site screenshots, regenerated with `python3 .github/scripts/capture_guide.py` (headless Chrome over DevTools via `shot.mjs`) and kept in `docs/media/guide/`.
- **Palette and direction contributions made easy.** `validate_library.py` checks every palette (roles, hex, unique ids, WCAG AA, categories, moods, complete dark mode) and direction (tokens, Fontsource fonts, table row, signature element); `--palette` / `--direction` validate a file before merging and `--check-fonts` asks npm that the fonts exist. New guides `docs/adding-a-palette.md` and `docs/adding-a-direction.md`, issue forms, PR checklist lines and a CI step.
- **Starter batch of seed content:** 8 palettes (now 30; Postcard Stamp, Ledger Green, Fjord Mist, Dune & Clay, Cobalt Pop, High-Contrast Ink (7:1), Moss & Sand, Brick & Brass) and 2 directions (now 10): Ledger and Postcard. New examples `tamsin-pike` (bookkeeper, Ledger) and `saltmarsh-railway` (heritage railway nonprofit, Postcard). `palettes.json` documents the allowed `moods`.
- **Import from a Google Business Profile export.** `import_gbp.py` reads the spreadsheet downloaded from Business Profile Manager (`.csv`, `.tsv`, `.xlsx`) or an API `Location` `.json` and fills `business.json`: name, address, phone, hours (split shifts, past-midnight and 24 h), website, description, category (mapped with `references/google-categories.json`), opening date and attributes. It never overwrites existing values (differences are reported as conflicts; `--prefer-google` opts in), never imports reviews, ratings or photos, and is a dry run unless `--write` is given. `/shingle ./export.csv` uses it.

- **Multi-language sites.** With two or more entries in `languages`, Shingle builds `/<lang>/` copies of every page (`/pt/`, `/en/`), a language switcher, absolute reciprocal `hreflang` alternates with `x-default`, self-referencing canonicals, `og:locale:alternate`, sitemap alternates and per-language JSON-LD. `/` redirects to the default language.
- `translations.<lang>` overlays in business.json (Claude drafts, the owner reviews; a visible notice stays until `review` is `"reviewed"`). The validator rejects translated prices, phone numbers, emails, URLs and people's names.
- Interface text in en, pt, es, fr, de and it (`references/ui-strings/`); other languages fall back to English. See `docs/adding-a-language.md`.
- `sync.py --init-i18n`; `audit_site.py` checks hreflang, canonicals, `lang`, page parity, the root redirect and sitemap alternates.
- New example: `barro-e-luz` (Lisbon ceramics shop, pt + en).
- Sub-folder previews (`SHINGLE_BASE`) now produce correct canonicals, og:image and redirects.

- **Image pipeline.** `import_images.py <folder> --site <dir>` imports jpg, png, webp, gif and avif photos into `public/images/` under clean unique names, reads their size from the file headers, rejects corrupt, empty and over-25 MB files with a reason, and **strips GPS, camera and date metadata** (EXIF, XMP, IPTC, PNG text chunks) from the copies while keeping orientation. Re-running changes nothing. `--apply-alt answers.json` records the alt text the owner confirmed (non-empty unless decorative, at most 125 characters, no "image of", not a file name, never the same twice; per language with `translations`). Claude suggests alt text from the pictures and asks for one confirmation (`references/images.md`).
- New `Photo.astro` component: `<Photo slot="Dining room" />` renders the matching photo with `astro:assets` (responsive WebP, lazy or eager, alt from the page's language) and falls back to the placeholder with its TODO. `sync.py` passes confirmed images into `site*.json`.
- `audit_site.py` warns on poor or repeated alt text, unused files in `public/images` and large unoptimised originals, and errors on images still `needs-alt` or GPS data left in any JPEG in `dist/`.
- New example: `harbour-loaf-bakery` (generated flat-colour test images through the real pipeline).

## 0.1.0 (2026-11-27)

First public version.

- `/shingle` command and `shingle` skill: intake → classify → interview → design → build → verify → handoff.
- 13 categories, 8 design directions, 22 WCAG AA palettes (20 with dark mode).
- Scripts: `validate_input.py`, `check_contrast.py`, `sync.py` (safe re-runs), `audit_site.py`.
- Astro 7 + Tailwind 4 template with LocalBusiness JSON-LD, Open Graph image, sitemap, live open status, click-to-load map.
- 8 example sites, CI that builds and audits all of them, and a GitHub Pages gallery.
