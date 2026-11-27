# Updating a site without wiping manual edits

Shingle sites are meant to be edited by hand after generation. Re-running Shingle with a changed
`business.json` must update the facts everywhere and leave hand edits alone.

## The three kinds of files
| Kind | Examples | On re-run |
|---|---|---|
| **Data** (always regenerated) | `src/data/site.json`, `src/styles/theme.css`, `public/robots.txt` | Overwritten by `sync.py`. Never edit by hand; a header comment says so. |
| **Generated** (written once by Shingle) | pages, section components, copy | Rewritten only if unchanged since Shingle last wrote them. |
| **Owned** (never touched) | anything not in the manifest, `public/images/*`, files the user created | Ignored. |

Facts (name, address, phone, hours, socials, palette, badge) live only in data files, and
components read them from there. So most business.json changes need no page rewrite at all.

## The manifest
`.shingle/manifest.json` records, for each generated file, the SHA-256 of the content Shingle
last wrote:

```json
{
  "version": 1,
  "generated_at": "2026-11-26T12:00:00Z",
  "shingle_version": "0.1.0",
  "files": { "src/pages/index.astro": "sha256:9f2c…", "src/components/Hero.astro": "sha256:41ab…" }
}
```

`sync.py <site> --record-all` creates it after the first build; `sync.py <site> --record <paths>` re-tracks files Shingle rewrote later.

## Update procedure
1. Read the new business.json and run `validate_input.py --write`.
2. Run `python3 SK/scripts/sync.py <site>`: regenerates data files and prints, for each
   generated file, `clean` (hash matches: safe to rewrite) or `edited` (user changed it).
3. Decide which generated files actually need new content (for example, a new feature section
   or a changed tone). Usually none: facts already flowed through the data files.
4. For each file that needs new content:
   - `clean`: rewrite it in place.
   - `edited`: do **not** overwrite. Write the new version to `.shingle/pending/<same path>`, and
     tell the user what changed and offer to merge it into their edited file. Merge only on yes.
5. New files (a section the old site did not have) are written normally and added to the manifest.
6. Rebuild, audit, then `sync.py <site> --record <each file you rewrote or added>`.
7. Never delete a file the user may have edited. Removed sections are unlinked from the page and
   left on disk; list them in the handoff.

## Why hashes instead of marker comments
Marker regions (`<!-- shingle:begin -->`) break when users reformat or move code and clutter the
files. A per-file hash is invisible, survives formatting by the user's editor only as "edited"
(the safe direction), and needs no parsing. The trade-off: any edit makes a whole file "edited";
the pending-file merge covers that.

## Multiple languages
Translations are data in business.json, so they follow the same rules as every other fact: edit
`translations.<lang>` and re-run `sync.py`, which rewrites `src/data/site.<lang>.json` and
`src/data/ui.json`. Page files under `src/pages/[lang]/` are ordinary generated files: edited ones
are never overwritten (`sync.py --init-i18n` also leaves an edited `index.astro` or `404.astro`
alone and tells you). Removing a language from `languages` deletes its data file but leaves any
pages you wrote.
