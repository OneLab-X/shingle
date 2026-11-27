#!/usr/bin/env python3
"""Image header parsing, metadata stripping and alt-text rules. Standard library only.

Shared by `import_images.py` (import, sanitize, alt-text answers) and `audit_site.py` (GPS check,
alt-quality warnings). Nothing here decodes pixels: sizes come from file headers and metadata is
removed by rewriting container segments, so the image data itself is never re-encoded.

Formats: JPEG (SOF), PNG (IHDR), WebP (VP8, VP8L, VP8X), GIF, AVIF (`ispe`).
"""

from __future__ import annotations

import re
import struct
import unicodedata
import zlib
from dataclasses import dataclass, field

MAX_BYTES = 25 * 1024 * 1024
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
FORMAT_EXT = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "gif": ".gif", "avif": ".avif"}
MAX_ALT = 125


class ImageError(ValueError):
    """The file is not a usable image (the message is shown to the owner)."""


@dataclass
class ImageInfo:
    format: str
    width: int
    height: int
    orientation: int = 1  # EXIF orientation, JPEG only

    @property
    def display_size(self) -> tuple[int, int]:
        """Size as shown to a viewer: EXIF orientations 5-8 turn the picture a quarter turn."""
        return (self.height, self.width) if self.orientation in (5, 6, 7, 8) else (self.width, self.height)


@dataclass
class Sanitized:
    data: bytes
    stripped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- EXIF


def _u16(b: bytes, o: int, big: bool) -> int:
    return struct.unpack_from(">H" if big else "<H", b, o)[0]


def _u32(b: bytes, o: int, big: bool) -> int:
    return struct.unpack_from(">I" if big else "<I", b, o)[0]


EXIF_PREFIX = b"Exif\x00\x00"
XMP_PREFIX = b"http://ns.adobe.com/xap/1.0/\x00"
IFD0_NAMES = {0x010F: "camera make", 0x0110: "camera model", 0x0132: "date", 0x013B: "artist", 0x8298: "copyright"}


def exif_info(segment: bytes) -> dict:
    """Parse the parts of an APP1 Exif payload that matter: orientation, GPS and what personal tags exist."""
    info = {"orientation": 1, "gps": False, "tags": []}
    tiff = segment[len(EXIF_PREFIX) :]
    try:
        big = tiff[:2] == b"MM"
        if tiff[:2] not in (b"MM", b"II"):
            return info
        ifd = _u32(tiff, 4, big)
        count = _u16(tiff, ifd, big)
        for n in range(count):
            at = ifd + 2 + n * 12
            tag = _u16(tiff, at, big)
            if tag == 0x0112:
                info["orientation"] = _u16(tiff, at + 8, big)
            elif tag == 0x8825:
                info["gps"] = True
            elif tag in IFD0_NAMES:
                info["tags"].append(IFD0_NAMES[tag])
    except (struct.error, IndexError):
        pass
    return info


def minimal_exif(orientation: int) -> bytes:
    """APP1 segment holding nothing but the orientation, so a stripped photo still displays upright."""
    tiff = (
        b"MM\x00\x2a\x00\x00\x00\x08" + struct.pack(">H", 1) + struct.pack(">HHIHH", 0x0112, 3, 1, orientation, 0) + b"\x00" * 4
    )
    payload = EXIF_PREFIX + tiff
    return b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


# ---------------------------------------------------------------- JPEG


def _jpeg_segments(data: bytes):
    """Yield (marker, start, end, payload_start) for every segment; the entropy data after a scan header belongs to that scan segment."""
    n = len(data)
    if data[:2] != b"\xff\xd8":
        raise ImageError("not a JPEG (missing start marker)")
    i = 2
    while True:
        if i >= n:
            raise ImageError("corrupt JPEG: ends before the end-of-image marker")
        if data[i] != 0xFF:
            raise ImageError(f"corrupt JPEG: unexpected byte at offset {i}")
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            raise ImageError("corrupt JPEG: truncated")
        marker = data[i]
        start = i - 1
        i += 1
        if marker == 0xD9:
            yield marker, start, i, i
            return
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            yield marker, start, i, i
            continue
        if i + 2 > n:
            raise ImageError("corrupt JPEG: truncated segment header")
        length = struct.unpack_from(">H", data, i)[0]
        if length < 2 or i + length > n:
            raise ImageError("corrupt JPEG: segment runs past the end of the file")
        end = i + length
        payload = i + 2
        i = end
        if marker == 0xDA:  # entropy-coded data runs up to the next real marker; it belongs to this segment
            while True:
                if i + 1 >= n:
                    raise ImageError("corrupt JPEG: ends inside image data")
                if data[i] == 0xFF:
                    nxt = data[i + 1]
                    if nxt == 0x00 or 0xD0 <= nxt <= 0xD7:
                        i += 2
                        continue
                    if nxt == 0xFF:
                        i += 1
                        continue
                    break
                i += 1
            end = i
        yield marker, start, end, payload


def probe_jpeg(data: bytes) -> ImageInfo:
    width = height = 0
    orientation = 1
    for marker, _start, end, payload in _jpeg_segments(data):
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC) and not width:
            if end - payload < 6:
                raise ImageError("corrupt JPEG: short frame header")
            height, width = struct.unpack_from(">HH", data, payload + 1)
        elif marker == 0xE1 and data[payload : payload + 6] == EXIF_PREFIX:
            orientation = exif_info(data[payload:end])["orientation"]
        elif marker == 0xDA and not width:
            break
    if not width or not height:
        raise ImageError("corrupt JPEG: no image size found (zero-size or missing frame header)")
    return ImageInfo("jpeg", width, height, orientation if 1 <= orientation <= 8 else 1)


def strip_jpeg(data: bytes) -> Sanitized:
    """Drop EXIF, XMP, IPTC/Photoshop, comments, other APPn blocks and anything after the end marker.

    Kept: JFIF, the ICC colour profile, the Adobe colour marker, and every table/frame/scan segment, so
    pixels and colours are untouched. If the photo was rotated by an EXIF flag, a bare orientation-only
    EXIF block is written back so it still shows upright.
    """
    out = bytearray(b"\xff\xd8")
    stripped: list[str] = []
    orientation = 1
    pieces: list[bytes] = []
    for marker, start, end, payload in _jpeg_segments(data):
        seg = data[start:end]
        if marker == 0xD9:
            pieces.append(seg)
            if end < len(data) and data[end:].strip(b"\x00"):
                stripped.append(f"{len(data) - end} bytes of data after the image (embedded previews or extras)")
            break
        body = data[payload:end]
        if (
            marker == 0xE0
            or (marker == 0xE2 and body.startswith(b"ICC_PROFILE\x00"))
            or (marker == 0xEE and body.startswith(b"Adobe"))
        ):
            pieces.append(seg)
        elif marker == 0xE1 and body.startswith(EXIF_PREFIX):
            info = exif_info(body)
            orientation = info["orientation"]
            what = (["GPS location"] if info["gps"] else []) + info["tags"]
            stripped.append("EXIF" + (f" ({', '.join(what)})" if what else ""))
        elif marker == 0xE1 and body.startswith(XMP_PREFIX):
            stripped.append("XMP" + (" (GPS location)" if b"GPSLatitude" in body or b"GPSLongitude" in body else ""))
        elif marker == 0xED:
            stripped.append("Photoshop/IPTC metadata")
        elif marker == 0xFE:
            stripped.append("comment")
        elif 0xE1 <= marker <= 0xEF:
            stripped.append(f"APP{marker - 0xE0} block")
        else:
            pieces.append(seg)
    # Re-attach orientation after a leading JFIF block (or at the very start).
    insert_at = 1 if pieces and pieces[0][:2] == b"\xff\xe0" else 0
    if orientation in (2, 3, 4, 5, 6, 7, 8):
        pieces.insert(insert_at, minimal_exif(orientation))
    out += b"".join(pieces)
    return Sanitized(bytes(out), _dedupe(stripped))


def has_gps(data: bytes) -> bool:
    """True when a JPEG still carries GPS coordinates in EXIF or XMP."""
    try:
        for marker, _start, end, payload in _jpeg_segments(data):
            if marker == 0xE1:
                body = data[payload:end]
                if body.startswith(EXIF_PREFIX) and exif_info(body)["gps"]:
                    return True
                if body.startswith(XMP_PREFIX) and (b"GPSLatitude" in body or b"GPSLongitude" in body):
                    return True
            elif marker == 0xDA:
                break
    except ImageError:
        return False
    return False


# ---------------------------------------------------------------- PNG

PNG_SIG = b"\x89PNG\r\n\x1a\n"
PNG_DROP = {b"tEXt": "text", b"zTXt": "text", b"iTXt": "text", b"eXIf": "EXIF", b"tIME": "timestamp"}


def _png_chunks(data: bytes):
    if data[:8] != PNG_SIG:
        raise ImageError("not a PNG (bad signature)")
    i, n = 8, len(data)
    first = True
    seen_end = False
    while i < n:
        if i + 12 > n:
            raise ImageError("corrupt PNG: truncated chunk")
        length = struct.unpack_from(">I", data, i)[0]
        kind = data[i + 4 : i + 8]
        if i + 12 + length > n:
            raise ImageError("corrupt PNG: chunk runs past the end of the file")
        if first and (kind != b"IHDR" or length != 13):
            raise ImageError("corrupt PNG: the first chunk is not a valid header")
        first = False
        body = data[i + 8 : i + 8 + length]
        crc = struct.unpack_from(">I", data, i + 8 + length)[0]
        yield kind, body, data[i : i + 12 + length], crc
        i += 12 + length
        if kind == b"IEND":
            seen_end = True
            break
    if not seen_end:
        raise ImageError("corrupt PNG: no end marker (the file is cut short)")


def probe_png(data: bytes) -> ImageInfo:
    size = None
    for kind, body, _raw, _crc in _png_chunks(data):  # walks every chunk, so a cut-short file is caught
        if kind == b"IHDR":
            size = struct.unpack_from(">II", body, 0)
    if not size or not all(size):
        raise ImageError("zero-size PNG")
    return ImageInfo("png", *size)


def strip_png(data: bytes) -> Sanitized:
    out = bytearray(PNG_SIG)
    dropped: dict[str, int] = {}
    for kind, body, raw, crc in _png_chunks(data):
        if kind in PNG_DROP:
            dropped[PNG_DROP[kind]] = dropped.get(PNG_DROP[kind], 0) + 1
            continue
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise ImageError(f"corrupt PNG: bad checksum in {kind.decode('latin-1')} chunk")
        out += raw
    labels = {"text": "PNG text chunks ({n})", "EXIF": "EXIF", "timestamp": "PNG timestamp"}
    return Sanitized(bytes(out), [labels[k].format(n=v) for k, v in dropped.items()])


# ---------------------------------------------------------------- WebP


def _webp_chunks(data: bytes):
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ImageError("not a WebP (bad header)")
    riff = struct.unpack_from("<I", data, 4)[0]
    if riff + 8 > len(data):
        raise ImageError("corrupt WebP: the file is cut short")
    i, end = 12, min(len(data), riff + 8)
    while i + 8 <= end:
        kind = data[i : i + 4]
        size = struct.unpack_from("<I", data, i + 4)[0]
        if i + 8 + size > end:
            raise ImageError("corrupt WebP: chunk runs past the end of the file")
        yield kind, data[i + 8 : i + 8 + size], i
        i += 8 + size + (size & 1)


def probe_webp(data: bytes) -> ImageInfo:
    for kind, body, _at in _webp_chunks(data):
        if kind == b"VP8X" and len(body) >= 10:
            width = int.from_bytes(body[4:7], "little") + 1
            height = int.from_bytes(body[7:10], "little") + 1
            return ImageInfo("webp", width, height)
        if kind == b"VP8 " and len(body) >= 10:
            if body[3:6] != b"\x9d\x01\x2a":
                raise ImageError("corrupt WebP: bad lossy frame header")
            width, height = struct.unpack_from("<HH", body, 6)
            return ImageInfo("webp", width & 0x3FFF, height & 0x3FFF)
        if kind == b"VP8L" and len(body) >= 5:
            if body[0] != 0x2F:
                raise ImageError("corrupt WebP: bad lossless signature")
            bits = struct.unpack_from("<I", body, 1)[0]
            return ImageInfo("webp", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
    raise ImageError("corrupt WebP: no image data")


def strip_webp(data: bytes) -> Sanitized:
    """Remove EXIF and XMP chunks of an extended WebP and fix the header flags and RIFF size."""
    chunks = list(_webp_chunks(data))
    if not any(k in (b"EXIF", b"XMP ") for k, _b, _a in chunks):
        return Sanitized(data)
    body = bytearray()
    stripped = []
    for kind, payload, _at in chunks:
        if kind in (b"EXIF", b"XMP "):
            stripped.append("EXIF" if kind == b"EXIF" else "XMP")
            continue
        if kind == b"VP8X":
            payload = bytes([payload[0] & ~0x0C & 0xFF]) + payload[1:]
        body += kind + struct.pack("<I", len(payload)) + payload + (b"\x00" if len(payload) & 1 else b"")
    return Sanitized(b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + bytes(body), stripped)


# ---------------------------------------------------------------- GIF


def probe_gif(data: bytes) -> ImageInfo:
    if data[:6] not in (b"GIF87a", b"GIF89a") or len(data) < 13:
        raise ImageError("not a GIF (bad header)")
    width, height = struct.unpack_from("<HH", data, 6)
    if not width or not height:
        raise ImageError("zero-size GIF")
    if data.rstrip(b"\x00")[-1:] != b";":
        raise ImageError("corrupt GIF: no end marker (the file is cut short)")
    return ImageInfo("gif", width, height)


# ---------------------------------------------------------------- AVIF (ISO base media)


def _boxes(data: bytes, start: int, end: int):
    i = start
    while i + 8 <= end:
        size, kind = struct.unpack_from(">I4s", data, i)
        header = 8
        if size == 1:
            if i + 16 > end:
                raise ImageError("corrupt AVIF: truncated box header")
            size = struct.unpack_from(">Q", data, i + 8)[0]
            header = 16
        elif size == 0:
            size = end - i
        if size < header or i + size > end:
            raise ImageError("corrupt AVIF: box runs past the end of the file")
        yield kind, i + header, i + size
        i += size


def probe_avif(data: bytes) -> ImageInfo:
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise ImageError("not an AVIF (no ftyp box)")
    ftyp_end = struct.unpack_from(">I", data, 0)[0]
    brands = data[8:ftyp_end]
    if b"avif" not in brands and b"avis" not in brands:
        raise ImageError("not an AVIF (brand is not avif)")
    best = (0, 0)
    for kind, s, e in _boxes(data, 0, len(data)):
        if kind != b"meta":
            continue
        for k2, s2, e2 in _boxes(data, s + 4, e):  # meta is a "full box": 4 bytes of version/flags first
            if k2 != b"iprp":
                continue
            for k3, s3, e3 in _boxes(data, s2, e2):
                if k3 != b"ipco":
                    continue
                for k4, s4, e4 in _boxes(data, s3, e3):
                    if k4 == b"ispe" and e4 - s4 >= 12:
                        w, h = struct.unpack_from(">II", data, s4 + 4)
                        if w * h > best[0] * best[1]:
                            best = (w, h)
    if not best[0] or not best[1]:
        raise ImageError("corrupt AVIF: no image size (ispe) found, or it is zero")
    return ImageInfo("avif", *best)


# ---------------------------------------------------------------- entry points


def sniff(data: bytes) -> str | None:
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    if data[:8] == PNG_SIG:
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:3] == b"GIF":
        return "gif"
    if data[4:8] == b"ftyp":
        return "avif"
    return None


PROBES = {"jpeg": probe_jpeg, "png": probe_png, "webp": probe_webp, "gif": probe_gif, "avif": probe_avif}


def probe(data: bytes) -> ImageInfo:
    """Format, width and height from the file header. Raises ImageError for anything unusable."""
    if not data:
        raise ImageError("the file is empty")
    if len(data) > MAX_BYTES:
        raise ImageError(
            f"the file is {len(data) / 1048576:.0f} MB; the limit is {MAX_BYTES // 1048576} MB. Export a smaller copy"
        )
    kind = sniff(data)
    if kind is None:
        raise ImageError("not a recognised image (jpg, png, webp, gif or avif)")
    info = PROBES[kind](data)
    if info.width < 1 or info.height < 1:
        raise ImageError("the image has zero width or height")
    return info


def sanitize(data: bytes, info: ImageInfo) -> Sanitized:
    """Copy of the file without personal metadata (location, camera, dates, text chunks)."""
    if info.format == "jpeg":
        return strip_jpeg(data)
    if info.format == "png":
        return strip_png(data)
    if info.format == "webp":
        return strip_webp(data)
    if info.format == "avif" and (b"Exif" in data[:65536] or b"mime\x00" in data[:65536]):
        return Sanitized(
            data,
            warnings=[
                "AVIF may carry EXIF/XMP metadata (location) and it cannot be stripped here; re-export it without metadata"
            ],
        )
    return Sanitized(data)


def _dedupe(items: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return list(seen)


# ---------------------------------------------------------------- names and alt text

CAMERA_NAME = re.compile(r"(img|dsc|dscn|dscf|pxl|mvimg|image|photo|pic|picture|screenshot|whatsapp-image)?-?[\d-]+(-[a-z]+)?")


def slugify(stem: str) -> str:
    text = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:60].strip("-") or "image"


def subject_from_name(stem: str) -> str:
    """A readable slot name from a clean file name ("Dining room"); camera names give no hint, so empty."""
    slug = slugify(stem)
    if CAMERA_NAME.fullmatch(slug):
        return ""
    return slug.replace("-", " ").capitalize()


FILENAME_ALT = re.compile(r"\.(jpe?g|png|webp|gif|avif|heic|tiff?|bmp)\b|^[\w-]+\.\w{2,4}$", re.I)
CAMERA_ALT = re.compile(r"^(img|dsc|dscn|dscf|pxl|mvimg|image|photo|pic|picture|screenshot)[-_ ]?\d[\w-]*$", re.I)
FILLER_ALT = re.compile(r"\b(image|photo|picture|photograph|pic|graphic)\s+(of|showing)\b", re.I)


def alt_problems(alt: str, *, file: str = "") -> list[str]:
    """Reasons an alt text is poor. Empty list means it passes the content rules (uniqueness is checked across images)."""
    text = alt.strip()
    problems = []
    if len(text) > MAX_ALT:
        problems.append(f"is {len(text)} characters; keep it to {MAX_ALT} or fewer")
    if FILLER_ALT.search(text):
        problems.append('says "image of" / "photo of"; screen readers already announce an image, describe the content')
    stem = file.rsplit(".", 1)[0].lower() if file else ""
    if (
        FILENAME_ALT.search(text)
        or CAMERA_ALT.match(text.replace(" ", "-").lower())
        or (stem and text.lower().replace(" ", "-") == stem)
    ):
        problems.append("looks like a file name; describe what the picture shows")
    return problems
