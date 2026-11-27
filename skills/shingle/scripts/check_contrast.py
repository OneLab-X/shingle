#!/usr/bin/env python3
"""WCAG 2.x AA contrast checks for Shingle palettes.

Usage:
    python3 check_contrast.py --palette harbor-blue          # check one curated palette
    python3 check_contrast.py --file custom-palette.json     # check a tweaked palette
    python3 check_contrast.py --all                          # check every curated palette (CI)
    python3 check_contrast.py --suggest --category cafe [--mood warm] [--limit 3]
    add --json for machine-readable output

A palette has "light" and optionally "dark" modes, each mapping roles (background, surface,
text, muted, primary, on_primary, accent, on_accent, border) to hex colors. Failing pairs are
reported loudly with the measured ratio and a suggested replacement color that passes.
Exit code: 0 all pass, 1 any failure, 2 bad usage. Standard library only.
"""

from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
from pathlib import Path

DEFAULT_PALETTES = Path(__file__).resolve().parent.parent / "references" / "palettes.json"

DEFAULT_RULES = [
    {"fg": "text", "bg": "background", "min": 4.5},
    {"fg": "text", "bg": "surface", "min": 4.5},
    {"fg": "muted", "bg": "background", "min": 4.5},
    {"fg": "muted", "bg": "surface", "min": 4.5},
    {"fg": "primary", "bg": "background", "min": 4.5},
    {"fg": "primary", "bg": "surface", "min": 3.0},
    {"fg": "on_primary", "bg": "primary", "min": 4.5},
    {"fg": "on_accent", "bg": "accent", "min": 4.5},
]

REQUIRED_ROLES = ["background", "surface", "text", "muted", "primary", "on_primary", "accent"]

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def parse_hex(value: str) -> tuple[float, float, float]:
    m = HEX_RE.match(value.strip())
    if not m:
        raise ValueError(f"not a hex color: {value!r}")
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in rgb)


def luminance(value: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in parse_hex(value))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def suggest_fix(fg: str, bg: str, target: float) -> str | None:
    """Move fg's lightness away from bg (keeping hue and saturation) until it passes."""
    r, g, b = parse_hex(fg)
    h, lightness, s = colorsys.rgb_to_hls(r, g, b)
    direction = -1 if luminance(bg) > 0.18 else 1
    for step in range(1, 101):
        candidate_l = lightness + direction * step * 0.01
        if not 0 <= candidate_l <= 1:
            break
        cand = to_hex(colorsys.hls_to_rgb(h, candidate_l, s))
        if contrast(cand, bg) >= target + 0.05:
            return cand
    for fallback in ("#000000", "#FFFFFF"):
        if contrast(fallback, bg) >= target:
            return fallback
    return None


def best_on(color: str, candidates: list[str]) -> str:
    return max(candidates, key=lambda c: contrast(c, color))


def check_mode(mode: dict, rules: list[dict], label: str) -> list[dict]:
    results = []
    missing = [r for r in REQUIRED_ROLES if r not in mode]
    for role in missing:
        results.append(
            {"mode": label, "pair": f"{role}", "ok": False, "ratio": None, "min": None, "message": f"missing role {role!r}"}
        )
    mode = dict(mode)
    if "on_accent" not in mode and "accent" in mode and "text" in mode and "background" in mode:
        mode["on_accent"] = best_on(mode["accent"], [mode["text"], mode["background"]])
    for rule in rules:
        fg, bg, need = rule["fg"], rule["bg"], float(rule["min"])
        if fg not in mode or bg not in mode:
            continue
        try:
            ratio = contrast(mode[fg], mode[bg])
        except ValueError as e:
            results.append({"mode": label, "pair": f"{fg}/{bg}", "ok": False, "ratio": None, "min": need, "message": str(e)})
            continue
        item = {
            "mode": label,
            "pair": f"{fg}/{bg}",
            "fg": mode[fg],
            "bg": mode[bg],
            "ratio": round(ratio, 2),
            "min": need,
            "ok": ratio >= need,
        }
        if not item["ok"]:
            fix_fg = suggest_fix(mode[fg], mode[bg], need)
            fix_bg = suggest_fix(mode[bg], mode[fg], need)
            if fix_bg and (luminance(fix_bg) > 0.18) != (luminance(mode[bg]) > 0.18):
                fix_bg = None  # would flip a light surface to dark (or vice versa): not a real fix
            item["suggestions"] = [
                s
                for s in (
                    f"change {fg} to {fix_fg}" if fix_fg else None,
                    f"or change {bg} to {fix_bg}" if fix_bg else None,
                )
                if s
            ]
        results.append(item)
    return results


def check_palette(palette: dict, rules: list[dict] | None = None) -> list[dict]:
    rules = rules or DEFAULT_RULES
    results = []
    if "light" not in palette and "background" in palette:
        palette = {"light": palette}
    for label in ("light", "dark"):
        mode = palette.get(label)
        if mode:
            results.extend(check_mode(mode, rules, label))
    if not palette.get("light"):
        results.append(
            {"mode": "light", "pair": "-", "ok": False, "ratio": None, "min": None, "message": "palette has no light mode"}
        )
    return results


def load_palettes(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def suggest(data: dict, category: str, moods: list[str], limit: int) -> list[dict]:
    scored = []
    for p in data["palettes"]:
        cat_score = (
            2 if category in p.get("categories", []) else (1 if "generic-local-business" in p.get("categories", []) else 0)
        )
        if cat_score == 0:
            continue
        mood_score = len(set(moods) & set(p.get("moods", [])))
        scored.append((cat_score * 10 + mood_score * 3 + (1 if p.get("dark") else 0), p))
    scored.sort(key=lambda t: -t[0])
    return [p for _, p in scored[:limit]]


def print_results(name: str, results: list[dict]) -> bool:
    failures = [r for r in results if not r["ok"]]
    status = "PASS" if not failures else "FAIL"
    print(f"{status}  {name}")
    for r in failures:
        if r.get("ratio") is None:
            print(f"  !! [{r['mode']}] {r['message']}")
            continue
        print(f"  !! [{r['mode']}] {r['pair']}: {r['fg']} on {r['bg']} = {r['ratio']}:1, needs {r['min']}:1")
        for s in r.get("suggestions", []):
            print(f"       fix: {s}")
    return not failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WCAG AA contrast checks for Shingle palettes")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--palette", help="id of a palette in palettes.json")
    g.add_argument("--file", type=Path, help="JSON file with a palette object (light/dark modes)")
    g.add_argument("--all", action="store_true", help="check every palette in palettes.json")
    g.add_argument("--suggest", action="store_true", help="list palettes for a category")
    ap.add_argument("--palettes", type=Path, default=DEFAULT_PALETTES, help="path to palettes.json")
    ap.add_argument("--category", help="category for --suggest")
    ap.add_argument("--mood", action="append", default=[], help="mood/tone for --suggest (repeatable)")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        data = load_palettes(args.palettes)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.palettes}: {e}", file=sys.stderr)
        return 2
    rules = data.get("contrast_rules") or DEFAULT_RULES

    if args.suggest:
        if not args.category:
            print("error: --suggest needs --category", file=sys.stderr)
            return 2
        moods = [m.lower() for m in args.mood]
        picks = suggest(data, args.category, moods, args.limit)
        out = []
        for p in picks:
            ok = all(r["ok"] for r in check_palette(p, rules))
            out.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "moods": p.get("moods", []),
                    "rationale": p.get("rationale", ""),
                    "dark_mode": bool(p.get("dark")),
                    "passes_aa": ok,
                    "light": p["light"],
                    "dark": p.get("dark"),
                }
            )
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            if not out:
                print(f"no palettes for {args.category!r}")
            for p in out:
                lm = p["light"]
                print(
                    f"{p['id']} — {p['name']} ({', '.join(p['moods'])}; dark mode: {'yes' if p['dark_mode'] else 'no'}; AA: {'pass' if p['passes_aa'] else 'FAIL'})"
                )
                print(f"  {p['rationale']}")
                print("  light: " + "  ".join(f"{k}={lm[k]}" for k in ("background", "surface", "text", "primary", "accent")))
                if p["dark"]:
                    dm = p["dark"]
                    print("  dark:  " + "  ".join(f"{k}={dm[k]}" for k in ("background", "surface", "text", "primary", "accent")))
        return 0 if out else 1

    if args.file:
        try:
            palette = json.loads(args.file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read {args.file}: {e}", file=sys.stderr)
            return 2
        targets = [(palette.get("id", str(args.file)), palette)]
    elif args.palette:
        match = [p for p in data["palettes"] if p["id"] == args.palette]
        if not match:
            ids = ", ".join(p["id"] for p in data["palettes"])
            print(f"error: no palette {args.palette!r}. Known: {ids}", file=sys.stderr)
            return 2
        targets = [(match[0]["id"], match[0])]
    else:
        targets = [(p["id"], p) for p in data["palettes"]]
        ids = [p["id"] for p in data["palettes"]]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            print(f"error: duplicate palette ids: {', '.join(sorted(dupes))}", file=sys.stderr)
            return 1

    all_ok = True
    report = {}
    for name, palette in targets:
        results = check_palette(palette, rules)
        report[name] = results
        if not args.json:
            all_ok &= print_results(name, results)
        else:
            all_ok &= all(r["ok"] for r in results)
    if args.json:
        print(json.dumps({"ok": all_ok, "palettes": report}, indent=2))
    elif not all_ok:
        print("\nContrast check FAILED. Apply a suggested fix (or pick another palette) and re-run.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
