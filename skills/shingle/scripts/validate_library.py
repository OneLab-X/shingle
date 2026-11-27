#!/usr/bin/env python3
"""Validate the palette and design-direction libraries (and contributions to them).

Usage:
    python3 validate_library.py                      # validate everything shipped (CI)
    python3 validate_library.py --palette new.json   # check a palette before merging it
    python3 validate_library.py --direction new.json # check a direction before merging it
    python3 validate_library.py --check-fonts        # also ask the npm registry that each Fontsource package exists
    add --json for machine-readable output

Palette rules: unique kebab-case id, name, rationale, known categories (categories.json), moods from
the documented list (`moods` in palettes.json), all nine roles as #RRGGBB in `light` (and in `dark`
when present), WCAG AA on every contrast rule.
Direction rules: unique kebab-case id, name, all token keys, display and body fonts with `package`,
`imports` and `fallback`, a row in the table of design-directions.md and a `## id: Name` section
with a signature element.
A file passed with --palette/--direction is a single object (directions carry an `id` key next to
`name`, `fonts` and `tokens`). Missing prose in design-directions.md is only a reminder there,
because contributors write the JSON first.
Exit code: 0 all valid, 1 any error, 2 bad usage. Standard library only (--check-fonts needs network).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import check_contrast as cc

REFS = Path(__file__).resolve().parent.parent / "references"
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
HEX6 = re.compile(r"^#[0-9A-Fa-f]{6}$")
ROLES = ["background", "surface", "text", "muted", "primary", "on_primary", "accent", "on_accent", "border"]
TOKEN_KEYS = [
    "scale",
    "h1",
    "body-size",
    "line-height",
    "space-unit",
    "section-gap",
    "radius",
    "measure",
    "heading-weight",
    "heading-tracking",
    "heading-case",
    "ui-tracking",
    "border-width",
    "transition",
]
FONT_ROLES = ["display", "body"]
FONT_KEYS = ["family", "package", "imports", "fallback"]
HEADING_CASES = {"none", "uppercase", "lowercase", "capitalize"}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_library(refs: Path = REFS) -> dict:
    """Everything the checks compare against."""
    palettes = _read(refs / "palettes.json")
    return {
        "palettes": palettes,
        "directions": _read(refs / "directions.json"),
        "categories": set(_read(refs / "categories.json")["categories"]),
        "moods": set(palettes.get("moods", [])),
        "docs": (refs / "design-directions.md").read_text(encoding="utf-8"),
    }


# ------------------------------------------------------------------ palettes


def check_palette(p: dict, lib: dict, *, seen_ids: set[str] | None = None) -> list[str]:
    """Return error messages for one palette object."""
    errors: list[str] = []
    pid = p.get("id")
    if not isinstance(pid, str) or not KEBAB.match(pid):
        errors.append(f"id {pid!r} must be lowercase kebab-case (e.g. 'harbor-blue')")
    elif seen_ids is not None and pid in seen_ids:
        errors.append(f"duplicate palette id {pid!r}")
    if not isinstance(p.get("name"), str) or not p["name"].strip():
        errors.append("name is required")
    if not isinstance(p.get("rationale"), str) or not p["rationale"].strip():
        errors.append("rationale is required (one sentence on when and why this palette works)")

    cats = p.get("categories")
    if not isinstance(cats, list) or not cats:
        errors.append("categories must be a non-empty list")
    else:
        for c in cats:
            if c not in lib["categories"]:
                errors.append(f"unknown category {c!r}; known: {', '.join(sorted(lib['categories']))}")
    moods = p.get("moods")
    if not isinstance(moods, list) or not moods:
        errors.append("moods must be a non-empty list")
    else:
        for m in moods:
            if m not in lib["moods"]:
                errors.append(f"unknown mood {m!r}; allowed: {', '.join(sorted(lib['moods']))}")

    modes = [("light", p.get("light"))]
    if p.get("dark") is not None:  # `"dark": null` means no dark mode
        modes.append(("dark", p.get("dark")))
    for label, mode in modes:
        if not isinstance(mode, dict):
            errors.append(f"{label} mode is missing or not an object")
            continue
        for role in ROLES:
            if role not in mode:
                errors.append(f"{label}: missing role {role!r}")
            elif not isinstance(mode[role], str) or not HEX6.match(mode[role]):
                errors.append(f"{label}.{role}: {mode[role]!r} is not a #RRGGBB hex color")
        for role in mode:
            if role not in ROLES:
                errors.append(f"{label}: unknown role {role!r}")

    if not errors:  # contrast needs well-formed colors
        rules = lib["palettes"].get("contrast_rules") or cc.DEFAULT_RULES
        for r in cc.check_palette(p, rules):
            if not r["ok"]:
                msg = f"{r['mode']} {r['pair']}: {r.get('fg')} on {r.get('bg')} = {r['ratio']}:1, needs {r['min']}:1"
                if r.get("suggestions"):
                    msg += " (" + "; ".join(r["suggestions"]) + ")"
                errors.append(msg)
    return errors


def check_palettes(lib: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    seen: set[str] = set()
    for i, p in enumerate(lib["palettes"]["palettes"]):
        key = f"palette {p.get('id', f'#{i}')}"
        out[key] = check_palette(p, lib, seen_ids=seen)
        if isinstance(p.get("id"), str):
            seen.add(p["id"])
    cat_count = {c: 0 for c in lib["categories"]}
    for p in lib["palettes"]["palettes"]:
        for c in p.get("categories", []):
            if c in cat_count:
                cat_count[c] += 1
    thin = [c for c, n in sorted(cat_count.items()) if n < 2]
    if thin:
        out["palette coverage"] = [f"category {c!r} has fewer than 2 palettes" for c in thin]
    return out


# ---------------------------------------------------------------- directions


def table_ids(docs: str) -> set[str]:
    return set(re.findall(r"^\|\s*`([^`]+)`\s*\|", docs, flags=re.M))


def docs_problems(did: str, docs: str) -> list[str]:
    problems = []
    if did not in table_ids(docs):
        problems.append(f"{did!r} is missing from the table in design-directions.md")
    m = re.search(rf"^## {re.escape(did)}: .+?(?=^## |^---|\Z)", docs, flags=re.M | re.S)
    if not m:
        problems.append(f"design-directions.md has no '## {did}: <Name>' section")
    elif "**Signature element:**" not in m.group(0):
        problems.append(f"section '## {did}' has no '**Signature element:**' line")
    return problems


def check_direction(did: str, d: dict, lib: dict, *, docs: bool = True) -> list[str]:
    errors: list[str] = []
    if not KEBAB.match(did or ""):
        errors.append(f"id {did!r} must be lowercase kebab-case (e.g. 'swiss-grid')")
    if not isinstance(d.get("name"), str) or not d["name"].strip():
        errors.append("name is required")
    fonts = d.get("fonts")
    if not isinstance(fonts, dict):
        errors.append("fonts is missing")
        fonts = {}
    for role in FONT_ROLES:
        f = fonts.get(role)
        if not isinstance(f, dict):
            errors.append(f"fonts.{role} is missing")
            continue
        for k in FONT_KEYS:
            if not f.get(k):
                errors.append(f"fonts.{role}.{k} is missing or empty")
        pkg, imports = f.get("package"), f.get("imports")
        if pkg and not re.match(r"^@fontsource(-variable)?/[a-z0-9-]+$", pkg):
            errors.append(f"fonts.{role}.package {pkg!r} must be a @fontsource/<name> or @fontsource-variable/<name> package")
        if imports is not None:
            if not isinstance(imports, list) or not all(isinstance(i, str) for i in imports):
                errors.append(f"fonts.{role}.imports must be a list of strings")
            elif pkg and not all(i == pkg or i.startswith(pkg + "/") for i in imports):
                errors.append(f"fonts.{role}.imports must all start with the package name {pkg!r}")
    tokens = d.get("tokens")
    if not isinstance(tokens, dict):
        errors.append("tokens is missing")
        tokens = {}
    for k in TOKEN_KEYS:
        if k not in tokens:
            errors.append(f"tokens.{k} is missing")
        elif tokens[k] in ("", None):
            errors.append(f"tokens.{k} is empty")
    for k in tokens:
        if k not in TOKEN_KEYS:
            errors.append(f"unknown token {k!r}")
    if tokens.get("heading-case") not in HEADING_CASES and "heading-case" in tokens:
        errors.append(f"tokens.heading-case must be one of {', '.join(sorted(HEADING_CASES))}")
    if docs:
        errors.extend(docs_problems(did, lib["docs"]))
    return errors


def check_directions(lib: dict) -> dict[str, list[str]]:
    out = {}
    for did, d in lib["directions"]["directions"].items():
        out[f"direction {did}"] = check_direction(did, d, lib)
    listed = table_ids(lib["docs"])
    extra = sorted(listed - set(lib["directions"]["directions"]))
    if extra:
        out["direction table"] = [f"design-directions.md lists {i!r} but directions.json has no such direction" for i in extra]
    return out


# --------------------------------------------------------------------- fonts


def check_fonts(lib: dict, *, opener=urllib.request.urlopen) -> dict[str, list[str]]:
    """Ask the npm registry that every Fontsource package exists (network)."""
    packages = {
        d["fonts"][r]["package"]: did
        for did, d in lib["directions"]["directions"].items()
        for r in FONT_ROLES
        if d.get("fonts", {}).get(r, {}).get("package")
    }
    out = {}
    for pkg, did in sorted(packages.items()):
        url = "https://registry.npmjs.org/" + pkg.replace("/", "%2f")
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "shingle-validate-library"})
        try:
            with opener(req, timeout=15):
                errs: list[str] = []
        except urllib.error.HTTPError as e:
            errs = [f"{pkg} (used by {did}): npm registry answered {e.code}"]
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            errs = [f"{pkg} (used by {did}): could not reach the npm registry ({e})"]
        out[f"font {pkg}"] = errs
    return out


# ----------------------------------------------------------------------- CLI


def report(results: dict[str, list[str]], notes: list[str], as_json: bool) -> bool:
    ok = not any(results.values())
    if as_json:
        print(json.dumps({"ok": ok, "errors": {k: v for k, v in results.items() if v}, "notes": notes}, indent=2))
        return ok
    for name, errs in results.items():
        print(f"{'FAIL' if errs else 'PASS'}  {name}")
        for e in errs:
            print(f"  !! {e}")
    for n in notes:
        print(f"  note: {n}")
    if not ok:
        print("\nLibrary validation FAILED. Fix the lines marked !! and re-run.")
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate Shingle palettes and design directions")
    ap.add_argument("--palette", type=Path, help="JSON file with one palette object to validate before merging")
    ap.add_argument("--direction", type=Path, help="JSON file with one direction (id, name, fonts, tokens) to validate")
    ap.add_argument("--check-fonts", action="store_true", help="ask the npm registry that Fontsource packages exist (network)")
    ap.add_argument("--references", type=Path, default=REFS, help="references folder (default: the plugin's)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        lib = load_library(args.references)
    except (OSError, json.JSONDecodeError, KeyError) as e:
        print(f"error: cannot read the library in {args.references}: {e}", file=sys.stderr)
        return 2

    results: dict[str, list[str]] = {}
    notes: list[str] = []
    contribution = args.palette or args.direction
    if args.palette:
        try:
            p = _read(args.palette)
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read {args.palette}: {e}", file=sys.stderr)
            return 2
        existing = {x.get("id") for x in lib["palettes"]["palettes"]}
        results[f"palette {p.get('id', args.palette)}"] = check_palette(p, lib, seen_ids=existing)
    if args.direction:
        try:
            d = _read(args.direction)
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read {args.direction}: {e}", file=sys.stderr)
            return 2
        did = d.get("id", "")
        errs = check_direction(did, d, lib, docs=False)
        if did in lib["directions"]["directions"]:
            errs.append(f"direction id {did!r} already exists")
        results[f"direction {did or args.direction}"] = errs
        notes += [f"before merging: {p}" for p in docs_problems(did, lib["docs"])]
    if not contribution:
        results.update(check_palettes(lib))
        results.update(check_directions(lib))
    if args.check_fonts:
        fonts_lib = {"directions": {"directions": {did: d}}} if args.direction else lib
        results.update(check_fonts(fonts_lib))
    return 0 if report(results, notes, args.json) else 1


if __name__ == "__main__":
    sys.exit(main())
