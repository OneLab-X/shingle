## What and why

<!-- One topic per PR. Link the issue if there is one. -->

## Type

- [ ] New category
- [ ] Palette or design direction
- [ ] Example site
- [ ] Script / template / skill fix
- [ ] Docs

## Checklist

- [ ] Tests pass: `python3 -m unittest discover -s skills/shingle/scripts/tests -t skills/shingle/scripts/tests`
- [ ] `ruff check . && ruff format --check .`
- [ ] Library changes: `python3 skills/shingle/scripts/validate_library.py` passes (palettes: AA contrast; directions: table row, signature element, fonts exist)
- [ ] New direction: includes an example in `examples/` or a screenshot of a built sample
- [ ] Nothing fabricated: no invented reviews, prices, awards, staff or statistics; examples use fiction-reserved phone numbers and `.example` domains
- [ ] Visual changes: before/after screenshots below
- [ ] Changed examples: `sync.py` produces no diff and `audit_site.py dist --strict` passes
- [ ] SKILL.md still under 150 lines; reference files stay short
