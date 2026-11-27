---
name: shingle
description: Build a finished, distinctive, production-ready website for a local business from its basic details (name, domain, category, address, phone, email, hours, socials). Interviews the owner, proposes a design direction and accessible palette, builds a static Astro site, audits it, and explains deployment. Use when someone wants a website for a business, shop, clinic, restaurant, studio, practice, or nonprofit, or wants to update a site Shingle built.
user-invocable: false
---

# Shingle: business details in, website out

Paths below are relative to `${CLAUDE_PLUGIN_ROOT}/skills/shingle/` (call it `SK`).
Scripts are standard-library Python 3: run them with `python3 SK/scripts/<name>.py`.
Load reference files only at the step that needs them. Never load every category file.

## Ground rules (apply at every step)
- **Never fabricate** reviews, testimonials, ratings, awards, certifications, years in business,
  prices, team members, client names, or statistics. Unknown content becomes a TODO (see Step 5).
- Ask questions with the interactive question tool (AskUserQuestion): at most 4 questions per
  round, 2-4 options each, recommended option first and labelled "(Recommended)".
- Never ask what you can infer from the input, the category file, or a sensible default.
- Ask before changing scope (adding a backend, CMS, e-commerce checkout, paid service).
- Show progress: after each step, a 1-3 line status of what was decided.

## Step 1: INTAKE
1. Input is free text, a pasted list, a path to `business.json`, or a Google Business Profile export
   (`.csv .tsv .xlsx`, or API Location `.json`). The command passes `$ARGUMENTS`.
2. Extract every fact into `business.json` following `SK/references/business-schema.md`.
   Keep the owner's wording for names; do not "improve" facts. For an export, run
   `python3 SK/scripts/import_gbp.py <file> --out business.json --write` instead (details in
   `SK/references/google-business-profile.md`). Several locations: it exits 2 with a list, so ask
   which one, then re-run with `--location`. It never overwrites existing values; show its
   report (filled, kept, not imported) and ask only for what is still missing.
3. Run `python3 SK/scripts/validate_input.py business.json --write`. It normalizes phone (E.164),
   hours, URLs, socials and slug, and prints `errors`, `warnings` and `missing`.
4. Show a compact table: understood facts, normalized changes, and missing items.
   Ask (one round) only for missing **essentials**: business name, category, and at least one
   contact method (phone, email, or address). Everything else may stay unknown.

## Step 2: CLASSIFY
Map the business to one file in `SK/references/categories/` by meaning, not keywords
(a "smile studio" is `dental-clinic`; a "plumber" is `contractor-home-services`).
If nothing fits, use `generic-local-business.md` and tell the user which category you used and why.
Read only that one category file now. Set `category` in business.json.

## Step 3: INTERVIEW
Read `SK/references/interview.md`. Merge its core bank with the category file's questions,
drop anything already answered or inferable, then ask in rounds (max 4 questions each, max
3 rounds). Cover: primary goal and CTA, one page vs multi-page, tone, imagery source, languages,
booking/contact method, and which features (menu, pricing, gallery, testimonials, FAQ, blog).
Save answers under `decisions` in business.json so re-runs do not ask again.
With 2+ languages also set `languages` (first = default) and read `SK/references/i18n.md`.

## Step 4: DESIGN
1. Read `SK/references/design-directions.md`. Pick ONE direction that fits category + tone
   (the category file lists good fits). Respect the anti-slop list.
2. Shortlist 2-3 palettes without loading the whole palette file:
   `python3 SK/scripts/check_contrast.py --suggest --category <category> [--mood <tone>]`
   prints only matching palettes from `SK/references/palettes.json`, ranked. For each, show:
   name, 4-6 hex swatches by role, one-line rationale, dark mode yes/no.
3. Run `python3 SK/scripts/check_contrast.py --palette <id>` for each shortlisted palette (or
   `--file custom.json` for a tweaked one). Only offer palettes that pass; if a user tweak fails,
   show the script's suggested fixes and re-check.
4. Ask the user to pick a palette and confirm or swap the direction (one round). Record both
   in `decisions.design`.

## Step 5: BUILD
1. Target folder: `./<slug>-site/` unless the user names one. If it exists and has
   `.shingle/manifest.json`, this is an **update**: follow `SK/references/regeneration.md`.
2. New site: copy `${CLAUDE_PLUGIN_ROOT}/templates/astro-tailwind/` to the target and put
   `business.json` at its root.
3. Run `python3 SK/scripts/sync.py <target>`: writes `src/data/site.json` and theme tokens from
   business.json and the chosen palette and direction.
4. Write pages and components following the category file's required sections, the direction's
   layout and signature element, and the interview decisions. Copy rules:
   - Real copy from the facts in the chosen tone. Short, specific, local. No lorem ipsum.
   - Unknown content: render a visible placeholder `<Todo>` component and put the literal marker
     `TODO(shingle): <what is needed>` in the source. Every TODO goes in the final list.
   - Things the category file says to NEVER invent stay TODOs even if they would "look nicer".
5. Every site gets: LocalBusiness JSON-LD, OG and Twitter tags, canonical URL, sitemap,
   robots.txt, favicon (SVG monogram), responsive layout, skip link, semantic landmarks, visible
   focus states, `prefers-reduced-motion` support, and dark mode if the palette has `dark`.
   Read `SK/references/seo-local.md` for the exact markup.
6. Images: only the owner's files, never stock or AI photos or hotlinks. With photos, follow
   `SK/references/images.md` (import, suggest alt, ONE confirmation table) and place them with
   `<Photo slot="subject">`; without, `<Photo>` shows a placeholder with a TODO naming size and subject.
7. Contact without a backend: `tel:`, `mailto:`, WhatsApp `https://wa.me/<digits>`, map link, and
   optionally a form posting to a form service chosen in the interview (Formspree, Web3Forms,
   Netlify Forms). Never invent an endpoint ID: leave it as a TODO.
8. "Built with Shingle" footer badge stays on unless `decisions.badge` is false
   (one line: `"badge": false` in business.json).
9. 2+ languages: run `sync.py <target> --init-i18n`, draft `translations` per `SK/references/i18n.md`
   (never translate prices, numbers or contact details), and write pages under `src/pages/[lang]/`.
10. Run `python3 SK/scripts/sync.py <target> --record-all` to store file hashes for safe re-runs.

## Step 6: VERIFY
1. Check `node -v` is 22.23.4 or newer (Astro 7); if not, say so and use `nvm use` (the template
   has `.nvmrc`). In the target: `npm install` then `npm run build`. Fix any build error.
2. Run `python3 SK/scripts/audit_site.py <target>/dist --business <target>/business.json`.
   Fix every `error`; fix `warning`s unless they are intended TODOs. Re-run until clean.
3. Start `npm run dev` in the background (or the app's preview tool if available) and report
   the local URL. If a browser tool is available, check every page at 375px and desktop width:
   no horizontal scroll (`document.documentElement.scrollWidth` equals the viewport width).

## Step 7: HANDOFF
Reply with, in this order:
1. **Decisions**: category, pages, direction, palette, CTA, languages, contact method.
2. **Placeholders to fill**: every `TODO(shingle)` with file:line (from the audit report). With
   several languages, include each draft translation that needs a native-speaker review.
3. **Deploy** (pick one; all are static `dist/`), see `SK/references/deploy.md` for details:
   - GitHub Pages: push, then enable Pages with the included workflow `.github/workflows/deploy.yml`.
   - Netlify: `npx netlify-cli deploy --prod --dir=dist`
   - Cloudflare Pages: `npx wrangler pages deploy dist`
   Then point the domain's DNS at the host and update `site` in `astro.config.mjs` if it changed.
4. **Next**: offer exactly 3 follow-ups that fit this business (for example: add a second
   language, connect a booking tool, add a Google Business Profile post schedule).

## Updating an existing site
Re-running with a changed business.json must not wipe manual edits. Always use `sync.py` (it
regenerates data files, and only rewrites a generated file whose hash still matches the recorded
one). Details and conflict handling: `SK/references/regeneration.md`.
