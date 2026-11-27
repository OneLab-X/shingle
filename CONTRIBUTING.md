# Contributing to Shingle

Thanks for helping. The most useful contributions, roughly in order:

1. **A new category** (vet, accountant, florist…): one Markdown file and one JSON entry.
   [Guide, under 10 minutes →](docs/adding-a-category.md)
2. **An interface language**: one JSON file of translated buttons and labels.
   [Guide →](docs/adding-a-language.md)
3. **A palette**: one JSON object; `validate_library.py` tells you if it passes WCAG AA.
   [Guide, about 5 minutes →](docs/adding-a-palette.md)
4. **A design direction**: two Fontsource fonts, tokens and a signature element, plus a sample built with it.
   [Guide →](docs/adding-a-direction.md)
5. **An example site** for a category that has none yet.
6. Bug fixes in the scripts, the template or the skill instructions.

## Repo map

| Path | What it is |
|---|---|
| `skills/shingle/SKILL.md` | The workflow Claude follows (keep it under 150 lines) |
| `skills/shingle/references/` | Loaded on demand: interview, categories, palettes, directions, SEO, regeneration, deploy |
| `skills/shingle/scripts/` | Standard-library Python: `validate_input`, `check_contrast`, `validate_library`, `sync`, `audit_site`, plus tests |
| `templates/astro-tailwind/` | The starter every site is copied from |
| `examples/` | Generated sites, each with its `business.json` and a design rationale |
| `commands/shingle.md` | The `/shingle` slash command |

## Local setup

```bash
# scripts and tests: Python 3.9+, no dependencies
python3 -m unittest discover -s skills/shingle/scripts/tests -t skills/shingle/scripts/tests

# lint (same version as CI)
pipx run ruff==0.17.6 check . && pipx run ruff==0.17.6 format --check .

# palettes and directions (add --check-fonts to ask npm that the fonts exist)
python3 skills/shingle/scripts/validate_library.py

# plugin manifests
claude plugin validate . --strict

# try the plugin from your checkout
claude --plugin-dir .

# build an example: Node 22.23.4+
cd examples/marigold-kitchen && npm ci && npm run build
python3 ../../skills/shingle/scripts/audit_site.py dist --strict
```

## Rules that keep Shingle trustworthy

- **Never add fabricated content** to prompts, templates or examples: reviews, ratings, awards, prices, staff, statistics. Examples must be clearly fictional and use phone numbers from ranges reserved for fiction (Ofcom drama numbers, ACMA, North American 555-0100 to 555-0199) and the `.example` TLD.
- **No stock or AI photos** in examples. Use `PlaceholderImage`.
- **Keep scripts dependency-free** (standard library only) and covered by tests.
- **Keep reference files short**: Claude loads them into context, so every line costs tokens for every user.
- **Examples must pass** `audit_site.py --strict` and have data files in sync (`sync.py` produces no diff).

## Changing an example

Edit `business.json`, then run `python3 ../../skills/shingle/scripts/sync.py .`, rebuild and audit. After changing pages by hand run `sync.py . --record <files>` so the manifest matches. CI fails if generated data files are stale.

## Pull requests

- One topic per PR; include before/after screenshots for visual changes.
- CI must be green: lint, tests on Python 3.10–3.14, every example built and audited, the template built.
- By contributing you agree your work is released under the MIT license.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).
