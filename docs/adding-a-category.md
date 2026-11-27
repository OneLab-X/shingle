# Adding a category (under 10 minutes)

A category teaches Shingle how a kind of business works: who visits, what the page needs,
what to ask, and what must never be made up. It is one Markdown file plus one JSON entry.

## 1. Copy the template (1 min)

```bash
cp docs/category-template.md skills/shingle/references/categories/veterinary-clinic.md
```

The file name is the category id: lowercase, words joined by hyphens. Change the first line to
`# Category: veterinary-clinic`.

## 2. Fill it in (5 min)

Keep every heading from the template (the tests check them) and keep the file under 90 lines;
Claude reads it on every run for that category. Look at `restaurant.md` or `dental-clinic.md`
for the level of detail. The two sections that matter most:

- **Category questions**: at most 4, each with 2–4 options and a recommended one.
- **Never invent**: everything that must come from the owner (credentials, prices, reviews…).

Under **Design fit**, name directions from `directions.json` and palettes from `palettes.json`
in backticks; the tests check they exist.

## 3. Register it (1 min)

Add an entry to `skills/shingle/references/categories.json`:

```json
"veterinary-clinic": {
  "label": "Vet",
  "schema_type": "VeterinaryCare",
  "aliases": ["vet", "veterinarian", "animal-hospital"]
}
```

- `label`: short human name used in titles ("Vet in Leeds").
- `schema_type`: the [schema.org](https://schema.org/LocalBusiness) type for the JSON-LD.
- `aliases`: slugs people might type; `validate_input.py` maps them to your category.

## 4. Give it palettes (1 min)

In `skills/shingle/references/palettes.json`, add your id to the `categories` list of at least
two palettes that suit it.

## 5. Check (1 min)

```bash
python3 -m unittest discover -s skills/shingle/scripts/tests -t skills/shingle/scripts/tests
python3 skills/shingle/scripts/check_contrast.py --suggest --category veterinary-clinic
```

Then open a pull request using the "New category" checklist. An example site for the
category is welcome but optional; see `examples/` and CONTRIBUTING.md.
