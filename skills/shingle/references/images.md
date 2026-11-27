# Photos: import, alt text, show

Read this when the owner has photos (interview `imagery`: "I have photos now") or adds some later.
Scripts: `SK/scripts/import_images.py`. Never use stock or AI-generated pictures, never hotlink.

## 1. Import
`python3 SK/scripts/import_images.py <folder> --site <target> --json` (add `--recursive` for sub-folders).
- Reads jpg, jpeg, png, webp, gif, avif; skips hidden files and anything else. HEIC/TIFF are not
  supported: ask the owner to export them as JPG.
- Copies into `<target>/public/images/` under clean names (`dining-room.jpg`), never overwriting,
  and **removes location, camera and date metadata** (EXIF/GPS, XMP, IPTC, PNG text) from the copies;
  originals are untouched. Tell the owner which items were removed (`stripped`), especially GPS.
- Rejected files (corrupt, empty, over 25 MB) come back with a reason: say which and why.
- Adds `images` entries with `status: "needs-alt"`. Re-running with the same photos changes nothing.
- AVIF files may keep metadata (a warning says so): ask for a re-export without it.

## 2. Suggest alt text
View every imported image (the Read tool shows images), then write `suggested_alt` into its
business.json entry. A suggestion describes **only what is visible**, in the owner's language:
- One plain sentence, at most 125 characters, no "image of" or "photo of", not the file name.
- Say what it is and what matters: "Long wooden table set for six beside a tall window".
- Never name people, brands, businesses or places you cannot read in the picture; never add claims
  ("freshly baked", "award-winning", "family-run"). If unsure, describe less and flag it.
- Quote text that is visible and meaningful (a shop sign). Purely decorative picture: propose `decorative`.
- Different images get different text.

## 3. One confirmation
Show ONE table: `file | suggested alt | proposed slot`. A slot is the `subject` a page asks for
(`Hero`, `Dining room`, `Entrance`), chosen from the category's required sections and what is shown;
the best wide image is the hero. Say plainly: only the owner can tell whether the text is accurate.
Ask a single question (AskUserQuestion): use these as they are (Recommended), or let me edit some.
Edits arrive as free text; apply them without asking per image.

## 4. Save the answers
Write `answers.json` outside the site (scratchpad), then run `import_images.py --apply-alt answers.json --site <target>`:
```json
[{"file": "dining-room.jpg", "alt": "Long wooden table set for six beside a tall window", "subject": "Dining room"},
 {"file": "divider.png", "decorative": true}]
```
With 2+ languages add `"translations": {"en": "..."}` per image (drafts, like other translations).
It refuses (writes nothing) if alt is empty without `decorative`, over 125 characters, says
"image of / photo of", looks like a file name, or repeats another image's text. Fix and re-run.

## 5. Show them
Run `sync.py <target>` (it passes confirmed images into `src/data/site*.json`), then in pages use
`<Photo slot="Dining room" width={1200} height={800} />`; the first above-the-fold image gets `eager`.
`Photo` resizes, serves responsive WebP and takes alt from the site data of the page's language.
A slot with no photo stays a visible placeholder with its TODO. Imported but unused photos are
reported by `audit_site.py`; a photo still `needs-alt` is an audit error.
