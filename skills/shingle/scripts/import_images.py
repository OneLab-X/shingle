#!/usr/bin/env python3
"""Import the owner's photos into a Shingle site, then record the alt text the owner confirmed.

Usage:
    python3 import_images.py <folder> --site <site> [--recursive] [--dry-run] [--json]
    python3 import_images.py --list --site <site> [--json]
    python3 import_images.py --apply-alt answers.json --site <site> [--json]

Import: scans the folder for jpg, jpeg, png, webp, gif and avif files (any letter case; hidden files
and non-images are skipped; sub-folders only with --recursive), reads each size from the file header,
rejects corrupt, empty or over-25 MB files with a reason, strips location and camera metadata
(EXIF/GPS, XMP, IPTC, PNG text chunks) from a copy placed in <site>/public/images/ under a clean
unique name, and adds an `images` entry to business.json with status "needs-alt". Re-running with the
same photos changes nothing (matched by content hash). Originals are never modified or overwritten.

Alt text: Claude looks at each image, writes `suggested_alt` into the business.json entry, shows the
owner one table, then writes the confirmed answers to a JSON file and runs --apply-alt:
    [{"file": "dining-room.jpg", "alt": "...", "subject": "Dining room",
      "translations": {"en": "..."}}, {"file": "divider.png", "decorative": true}]
Rules: alt present unless decorative, at most 125 characters, no "image of / photo of", not a file
name, and different for every image. Nothing is written if any answer breaks a rule.
With several languages, `translations.<lang>.images[i].alt` is written too.

Exit code: 0 ok, 1 nothing imported because every file was rejected, or answers rejected, 2 bad usage.
Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import imagemeta  # noqa: E402
from imagemeta import ImageError  # noqa: E402

IMAGES_DIR = Path("public") / "images"


class UsageError(Exception):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_business(site: Path) -> dict:
    path = site / "business.json"
    if not path.is_file():
        raise UsageError(f"{path} not found; --site must be a Shingle site folder with a business.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise UsageError(f"{path} is not valid JSON: {e}") from e


def save_business(site: Path, business: dict) -> None:
    (site / "business.json").write_text(json.dumps(business, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- import


def scan(folder: Path, recursive: bool) -> tuple[list[Path], list[dict]]:
    found: list[Path] = []
    skipped: list[dict] = []
    for path in sorted(folder.rglob("*") if recursive else folder.glob("*")):
        rel = path.relative_to(folder)
        if any(part.startswith(".") for part in rel.parts):
            continue  # hidden files and folders (.DS_Store, ._IMG_1.jpg, .git)
        if path.is_dir():
            continue
        if path.is_symlink():
            skipped.append({"source": rel.as_posix(), "reason": "symbolic link"})
        elif path.suffix.lower() in imagemeta.EXTENSIONS:
            found.append(path)
        else:
            skipped.append({"source": rel.as_posix(), "reason": "not an image file"})
    return found, skipped


def entry_hash(site: Path, entry: dict) -> str | None:
    if entry.get("sha256"):
        return entry["sha256"]
    path = site / str(entry.get("src", ""))
    return sha256(path.read_bytes()) if path.is_file() else None


def unique_name(dest: Path, slug: str, ext: str, data: bytes) -> Path:
    """Create a new file under a clean unique name; never replaces an existing file."""
    n = 1
    while True:
        name = f"{slug}{ext}" if n == 1 else f"{slug}-{n}{ext}"
        try:
            with open(dest / name, "xb") as fh:
                fh.write(data)
            return dest / name
        except FileExistsError:
            n += 1


def import_folder(folder: Path, site: Path, *, recursive: bool = False, dry_run: bool = False) -> dict:
    business = load_business(site)
    images = business.setdefault("images", [])
    dest = site / IMAGES_DIR
    files, skipped = scan(folder, recursive)
    report: dict = {"imported": [], "skipped": skipped, "rejected": [], "warnings": []}

    known: dict[str, dict] = {}
    for entry in images:
        digest = entry_hash(site, entry) if isinstance(entry, dict) else None
        if digest:
            known[digest] = entry
    on_disk: dict[str, Path] = {}
    if dest.is_dir():
        on_disk = {sha256(p.read_bytes()): p for p in sorted(dest.iterdir()) if p.is_file() and not p.name.startswith(".")}

    batch: dict[str, str] = {}
    taken = {p.name for p in dest.iterdir()} if dest.is_dir() else set()
    for path in files:
        rel = path.relative_to(folder).as_posix()
        try:
            size = path.stat().st_size
            if size > imagemeta.MAX_BYTES:
                raise ImageError(
                    f"the file is {size / 1048576:.0f} MB; the limit is {imagemeta.MAX_BYTES // 1048576} MB. Export a smaller copy"
                )
            data = path.read_bytes()
            info = imagemeta.probe(data)
            clean = imagemeta.sanitize(data, info)
        except ImageError as e:
            report["rejected"].append({"source": rel, "reason": str(e)})
            continue
        except OSError as e:
            report["rejected"].append({"source": rel, "reason": f"cannot read the file ({e.strerror})"})
            continue
        digest = sha256(clean.data)
        if digest in batch:
            report["skipped"].append({"source": rel, "reason": f"same picture as {batch[digest]}"})
            continue
        batch[digest] = rel
        if digest in known:
            report["skipped"].append({"source": rel, "reason": f"already imported as {known[digest].get('src')}"})
            continue
        width, height = info.display_size
        if digest in on_disk:  # a file someone put there by hand: adopt it instead of copying it again
            target = on_disk[digest]
        elif dry_run:
            slug, ext = imagemeta.slugify(path.stem), imagemeta.FORMAT_EXT[info.format]
            n, name = 1, f"{slug}{ext}"
            while name in taken:
                n += 1
                name = f"{slug}-{n}{ext}"
            taken.add(name)
            target = dest / name
        else:
            dest.mkdir(parents=True, exist_ok=True)
            target = unique_name(dest, imagemeta.slugify(path.stem), imagemeta.FORMAT_EXT[info.format], clean.data)
        entry = {
            "src": (IMAGES_DIR / target.name).as_posix(),
            "alt": "",
            "subject": imagemeta.subject_from_name(path.stem),
            "width": width,
            "height": height,
            "suggested_alt": "",
            "status": "needs-alt",
            "sha256": digest,
        }
        images.append(entry)
        known[digest] = entry
        report["imported"].append(
            {
                "source": rel,
                "file": target.name,
                "src": entry["src"],
                "format": info.format,
                "width": width,
                "height": height,
                "bytes": len(clean.data),
                "stripped": clean.stripped,
                "rotated": info.orientation in (2, 3, 4, 5, 6, 7, 8),
            }
        )
        report["warnings"] += [f"{rel}: {w}" for w in clean.warnings]
    if report["imported"] and not dry_run:
        save_business(site, business)
    report["needs_alt"] = needs_alt(business)
    report["dry_run"] = dry_run
    report["ok"] = bool(report["imported"] or report["skipped"] or not report["rejected"])
    return report


def needs_alt(business: dict) -> list[dict]:
    return [
        {
            "file": Path(str(e.get("src", ""))).name,
            "src": e.get("src"),
            "subject": e.get("subject", ""),
            "suggested_alt": e.get("suggested_alt", ""),
            "width": e.get("width"),
            "height": e.get("height"),
        }
        for e in business.get("images") or []
        if isinstance(e, dict) and e.get("status") == "needs-alt"
    ]


# ---------------------------------------------------------------- confirmed alt text


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def apply_alt(site: Path, answers) -> dict:
    """Validate every answer, then write them all (or nothing). Returns {"ok", "errors", "warnings", "applied"}."""
    business = load_business(site)
    images = business.get("images") or []
    languages = business.get("languages") or []
    extra = [str(code) for code in languages[1:]]
    if isinstance(answers, dict):
        answers = answers.get("images", answers.get("answers"))
    if not isinstance(answers, list):
        raise UsageError('answers must be a JSON list of {"file", "alt", ...} objects (or {"images": [...]})')

    by_file = {Path(str(e.get("src", ""))).name: i for i, e in enumerate(images) if isinstance(e, dict)}
    errors: list[str] = []
    warnings: list[str] = []
    plan: dict[int, dict] = {}
    for n, ans in enumerate(answers):
        if not isinstance(ans, dict):
            errors.append(f"answer {n + 1}: expected an object")
            continue
        file = Path(str(ans.get("file") or ans.get("src") or "")).name
        if file not in by_file:
            errors.append(
                f"answer {n + 1}: no image named {file!r} in business.json (known: {', '.join(sorted(by_file)) or 'none'})"
            )
            continue
        i = by_file[file]
        if i in plan:
            errors.append(f"{file}: answered twice")
            continue
        decorative = ans.get("decorative") is True
        alt = str(ans.get("alt") or "").strip()
        if decorative:
            alt = ""
        elif not alt:
            errors.append(f'{file}: alt text is empty; write what the picture shows, or mark it "decorative": true')
        else:
            errors += [f"{file}: alt text {p}" for p in imagemeta.alt_problems(alt, file=file)]
        trans: dict[str, str] = {}
        for code, text in (ans.get("translations") or {}).items():
            if code not in extra:
                errors.append(
                    f"{file}: translations.{code}: the site has no extra language {code!r} (languages: {languages or ['one']})"
                )
                continue
            text = str(text or "").strip()
            if decorative:
                continue
            if not text:
                errors.append(f"{file}: translations.{code}: alt text is empty")
                continue
            errors += [f"{file}: translations.{code} alt text {p}" for p in imagemeta.alt_problems(text, file=file)]
            trans[code] = text
        if not decorative:
            warnings += [
                f"{file}: no {code} alt text; the {code} pages fall back to the default language"
                for code in extra
                if code not in trans
            ]
        subject = ans.get("subject")
        plan[i] = {"alt": alt, "decorative": decorative, "subject": subject, "translations": trans, "file": file}

    # no two images may share alt text, counting images confirmed earlier
    def final_alt(i: int, lang: str) -> str:
        e = images[i]
        if i in plan:
            return plan[i]["alt"] if not lang else plan[i]["translations"].get(lang, "")
        if not isinstance(e, dict) or e.get("decorative"):
            return ""
        if not lang:
            return str(e.get("alt") or "")
        rows = ((business.get("translations") or {}).get(lang) or {}).get("images") or []
        row = rows[i] if i < len(rows) and isinstance(rows[i], dict) else {}
        return str(row.get("alt") or "")

    for lang in ["", *extra]:
        groups: dict[str, list[int]] = {}
        for i in range(len(images)):
            text = final_alt(i, lang)
            if text:
                groups.setdefault(_norm(text), []).append(i)
        for idxs in groups.values():
            if len(idxs) > 1 and any(i in plan for i in idxs):
                names = " and ".join(Path(str(images[i].get("src", ""))).name for i in idxs)
                errors.append(
                    f"{'translations.' + lang + ': ' if lang else ''}{names} have the same alt text; give each image its own description"
                )

    result = {"ok": not errors, "errors": errors, "warnings": warnings, "applied": []}
    if errors:
        return result
    for i, p in plan.items():
        e = images[i]
        e["alt"] = p["alt"]
        e["suggested_alt"] = ""
        e["status"] = "ok"
        if p["decorative"]:
            e["decorative"] = True
        else:
            e.pop("decorative", None)
        if isinstance(p["subject"], str):
            e["subject"] = p["subject"].strip()
        elif not e.get("subject"):
            warnings.append(f"{p['file']}: no subject (page slot) yet; it shows only where a slot names it")
        for code in extra:
            overlay = business.setdefault("translations", {}).setdefault(code, {})
            rows = overlay.setdefault("images", [])
            while len(rows) < len(images):
                rows.append({})
            row = rows[i] if isinstance(rows[i], dict) else {}
            if p["decorative"] or code not in p["translations"]:
                row.pop("alt", None)
            else:
                row["alt"] = p["translations"][code]
            rows[i] = row
        result["applied"].append(p["file"])
    save_business(site, business)
    result["needs_alt"] = needs_alt(business)
    return result


# ---------------------------------------------------------------- CLI


def print_import(report: dict) -> None:
    mode = " (dry run, nothing written)" if report["dry_run"] else ""
    print(f"imported {len(report['imported'])}, skipped {len(report['skipped'])}, rejected {len(report['rejected'])}{mode}")
    for item in report["imported"]:
        extra = f"; removed {', '.join(item['stripped'])}" if item["stripped"] else ""
        turned = "; orientation kept" if item["rotated"] else ""
        print(
            f"  + {item['source']} -> {item['src']} ({item['width']}x{item['height']}, {item['bytes'] // 1024} KB){extra}{turned}"
        )
    for item in report["skipped"]:
        print(f"  - {item['source']}: skipped ({item['reason']})")
    for item in report["rejected"]:
        print(f"  ! {item['source']}: rejected ({item['reason']})")
    for w in report["warnings"]:
        print(f"  warning: {w}")
    if report["needs_alt"]:
        print(
            f"\n{len(report['needs_alt'])} image(s) need alt text: view each, set suggested_alt, confirm with the owner, then --apply-alt"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Import photos into a Shingle site and record confirmed alt text")
    ap.add_argument("folder", nargs="?", type=Path, help="folder of photos to import")
    ap.add_argument("--site", type=Path, required=True, help="the site folder (contains business.json)")
    ap.add_argument("--recursive", action="store_true", help="also read sub-folders")
    ap.add_argument("--dry-run", action="store_true", help="report what would happen; write nothing")
    ap.add_argument("--list", action="store_true", help="list images still needing alt text")
    ap.add_argument("--apply-alt", type=Path, metavar="ANSWERS.json", help="write the owner's confirmed alt text")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    modes = [bool(args.folder), args.list, bool(args.apply_alt)]
    try:
        if sum(modes) != 1:
            raise UsageError("give exactly one of: a photo folder, --list, or --apply-alt answers.json")
        if not args.site.is_dir():
            raise UsageError(f"{args.site} is not a folder")
        if args.apply_alt:
            try:
                answers = json.loads(args.apply_alt.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                raise UsageError(f"cannot read {args.apply_alt}: {e}") from e
            result = apply_alt(args.site, answers)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif result["ok"]:
                print(f"saved alt text for {len(result['applied'])} image(s); {len(result['needs_alt'])} still need alt text")
                for w in result["warnings"]:
                    print(f"  warning: {w}")
            else:
                print("nothing saved; fix these and run again:")
                for e in result["errors"]:
                    print(f"  - {e}")
            return 0 if result["ok"] else 1
        if args.list:
            pending = needs_alt(load_business(args.site))
            if args.json:
                print(json.dumps({"needs_alt": pending}, indent=2, ensure_ascii=False))
            else:
                for p in pending:
                    print(f"{p['file']}\t{p['subject'] or '(no subject)'}\t{p['suggested_alt']}")
                print(f"{len(pending)} image(s) need alt text")
            return 0
        if not args.folder.is_dir():
            raise UsageError(f"{args.folder} is not a folder")
        report = import_folder(args.folder, args.site, recursive=args.recursive, dry_run=args.dry_run)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_import(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
