# Adding a design direction (about an hour)

A direction is a complete visual system: two fonts, spacing and shape tokens, and one **signature
element** that makes a site recognisable. It lives in two places that must agree:
`skills/shingle/references/directions.json` (machine-readable) and `design-directions.md` (the
prose Claude reads). A pull request must also include a built sample.

## 1. Pick two Fontsource fonts (10 min)

Fonts are self-hosted from [Fontsource](https://fontsource.org/); never a Google Fonts CDN link.
Prefer the variable package when it exists.

```bash
npm view @fontsource-variable/newsreader version   # prints a version if the package exists
npm view @fontsource/bevan version                  # static fallback package
```

Choose a **display** font for headings and a **body** font for reading, and make them distinct
from the existing directions' pairings. Check the font has the weights you will use and the
accented characters your target languages need (Latin Extended at least).

## 2. Add the JSON (10 min)

Add an entry to `directions.json` (copy a neighbour and edit):

```json
"my-direction": {
  "name": "My Direction",
  "fonts": {
    "display": { "family": "Newsreader Variable", "package": "@fontsource-variable/newsreader",
                 "imports": ["@fontsource-variable/newsreader"], "fallback": "Georgia, serif" },
    "body":    { "family": "Josefin Sans Variable", "package": "@fontsource-variable/josefin-sans",
                 "imports": ["@fontsource-variable/josefin-sans"], "fallback": "system-ui, sans-serif" }
  },
  "tokens": { "...": "all fourteen keys below" }
}
```

`family` is the CSS name (variable packages end in "Variable"), `imports` the CSS files `sync.py`
writes into `fonts.css` (each must start with the package name; add italic or width files only
if you use them), `fallback` a system stack close in metrics so there is little layout shift.

| Token | Meaning | Example |
|---|---|---|
| `scale` | Type scale ratio | `1.25` |
| `h1` | Hero heading size | `clamp(2.5rem, 6vw, 4.75rem)` |
| `body-size` | Body font size | `1.0625rem` |
| `line-height` | Body line height | `1.65` |
| `space-unit` | Base spacing step | `8px` |
| `section-gap` | Space between sections | `clamp(4rem, 8vw, 7rem)` |
| `radius` | Corner radius | `0px` |
| `measure` | Max line length | `66ch` |
| `heading-weight` | Heading weight | `700` |
| `heading-tracking` | Heading letter-spacing | `-0.02em` |
| `heading-case` | `none`, `uppercase`, `lowercase` or `capitalize` | `none` |
| `ui-tracking` | Letter-spacing of buttons and labels | `0.08em` |
| `border-width` | Rule and border width | `1px` |
| `transition` | Default transition duration | `150ms` |

## 3. Write the prose (15 min)

In `design-directions.md`:

1. Add a row to the table: `| \`my-direction\` | My Direction | best-for categories | avoid-for |`.
2. Add a `## my-direction: My Direction` section after the others, in the same shape as its
   neighbours: one-line mood, **Fonts**, **Scale**, **Spacing**, **Shape**, **Motion**, and a
   **Signature element**.
3. Add a pairing hint to "Pairing directions with palettes" if you know one that works.

The **signature element** is the point: a specific, buildable thing (a masthead, a route line,
ruled-paper tables), not a mood. It must work with real business facts only, respect
`prefers-reduced-motion`, and be built from CSS or inline SVG: no stock images.

**Anti-slop checklist** (the full list is in `design-directions.md`). Your direction must not need:
- purple-to-pink gradients, aurora blobs or glassmorphism;
- the centered hero + three identical icon cards + testimonial carousel layout;
- emoji icons, invented testimonials, ratings, awards or "500+ clients";
- stock or AI photos; parallax, scroll-jacking or cursor effects;
- Inter on white as the whole design.

## 4. Validate (1 min)

```bash
python3 skills/shingle/scripts/validate_library.py
python3 skills/shingle/scripts/validate_library.py --check-fonts   # asks the npm registry; needs network
```

The first run checks the token set, font fields, kebab-case id, the table row and that your
section has a signature element. `--check-fonts` confirms every package exists on npm. To check
the JSON before pasting it in, save it as a file with an extra `"id": "my-direction"` key and
use `--direction my-direction.json`.

## 5. Build a sample (20+ min)

A pull request must include **either** an example in `examples/` **or** a screenshot of a sample
page built with the direction (desktop and phone, light and dark if the palette has it).
An example is preferred: use a fictional business, a `.example` domain and a phone number from a
fiction-reserved range, no invented reviews, prices or statistics (see CONTRIBUTING.md). Then:

```bash
cd examples/my-example
python3 ../../skills/shingle/scripts/sync.py .            # theme and fonts from your direction
npm install && npm run build                              # Node 22.23.4 or newer
python3 ../../skills/shingle/scripts/audit_site.py dist --strict
```

Check that the fonts actually load (open the built page, inspect the headings) and that nothing
scrolls sideways at 375px. Add the example to `examples/README.md`, then open a pull request
with the "Palette or design direction" box ticked.
