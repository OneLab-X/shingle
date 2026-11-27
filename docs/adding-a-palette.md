# Adding a palette (about 5 minutes)

A palette is nine colors per mode (light, and optionally dark) plus a few tags. The validator
checks the rest, so you only need to choose colors you like.

## 1. Write it (3 min)

Copy this into `my-palette.json` (anywhere, it does not need to be in the repo yet):

```json
{
  "id": "harbor-fog",
  "name": "Harbor Fog",
  "categories": ["travel-agency", "photographer"],
  "moods": ["calm", "clean"],
  "rationale": "Cool grey ground with deep blue; still and uncluttered, so photos carry the page.",
  "light": {
    "background": "#F3F6F8", "surface": "#E4EBEF", "text": "#14242C", "muted": "#475A64",
    "primary": "#1B5B78", "on_primary": "#FFFFFF", "accent": "#9CC3D3", "on_accent": "#10222B",
    "border": "#CDD8DE"
  },
  "dark": {
    "background": "#0F191F", "surface": "#17252D", "text": "#E9F0F3", "muted": "#A3B4BD",
    "primary": "#82C0DB", "on_primary": "#0B151A", "accent": "#4F8BA3", "on_accent": "#06141A",
    "border": "#27383F"
  }
}
```

- `id`: lowercase words joined by hyphens; must be new.
- `categories`: ids from `skills/shingle/references/categories.json` the palette suits. Name the
  ones it is genuinely good for; two or three is plenty.
- `moods`: one to three from the list at the top of `palettes.json` (`moods`): bold, calm, clean,
  earthy, elegant, energetic, fresh, friendly, high-contrast, hopeful, muted, playful,
  trustworthy, warm. Add a new mood to that list in the same PR only if none fits.
- `rationale`: one sentence on when it works. No claims you cannot back up.
- Colors are six-digit hex (`#RRGGBB`), all nine roles in every mode you include. The roles are
  explained at the top of `palettes.json`. `dark` is optional but welcome: sites then get a
  working dark mode and a toggle.

## 2. Check it (1 min)

```bash
python3 skills/shingle/scripts/validate_library.py --palette my-palette.json
```

It checks the id, categories, moods, hex format, that every role exists, and WCAG AA contrast
(body text 4.5:1, links and buttons too). A failing pair is printed with the ratio and a
suggested replacement color; fix it and re-run. For a quick look at a single palette's ratios
use `python3 skills/shingle/scripts/check_contrast.py --file my-palette.json`.

## 3. Add it (1 min)

Paste the object into the `palettes` array of `skills/shingle/references/palettes.json`, then run:

```bash
python3 skills/shingle/scripts/validate_library.py
python3 -m unittest discover -s skills/shingle/scripts/tests -t skills/shingle/scripts/tests
```

Open a pull request using the checklist; a screenshot of a sample page in your palette (light and
dark) helps reviewers. Missing categories? Every category needs at least two palettes, so
palettes for thinly covered categories (see `check_contrast.py --suggest --category <id>`) are
especially welcome.
