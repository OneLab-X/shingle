"""Generate test images from bytes. No stock photos, no Pillow: flat-colour pictures built by hand.

PNG and JPEG results decode in real viewers and in sharp (so the example sites can use them);
WebP, GIF and AVIF results carry valid headers only, which is all the parsers read.
"""

from __future__ import annotations

import struct
import zlib

# A recognisable GPS payload so tests can prove it is gone: latitude 38 deg 42' 4.600", longitude 9 deg 8' 20.250".
GPS_LAT = [(38, 1), (42, 1), (4600, 1000)]
GPS_LON = [(9, 1), (8, 1), (20250, 1000)]
GPS_MARKER = struct.pack(">II", 4600, 1000)  # the seconds of the latitude, as stored in the file


# ---------------------------------------------------------------- PNG


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def make_png(width: int = 64, height: int = 48, rgb=(200, 100, 50), *, text: dict[str, str] | None = None) -> bytes:
    rows = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    out = b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    for key, value in (text or {}).items():
        out += _chunk(b"tEXt", key.encode() + b"\x00" + value.encode())
    return out + _chunk(b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b"")


# ---------------------------------------------------------------- JPEG

_DC_COUNTS = [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]  # standard luminance DC table
_DC_SYMBOLS = list(range(12))


def _codes(counts, symbols) -> dict[int, str]:
    code, out, k = 0, {}, 0
    for length, n in enumerate(counts, 1):
        for _ in range(n):
            out[symbols[k]] = format(code, f"0{length}b")
            code += 1
            k += 1
        code <<= 1
    return out


def _segment(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body


def _dc_bits(diff: int, codes: dict[int, str]) -> str:
    size = abs(diff).bit_length()
    extra = format(diff if diff >= 0 else diff + (1 << size) - 1, f"0{size}b") if size else ""
    return codes[size] + extra


def exif_block(orientation: int = 1, *, gps: bool = True, make: str = "ExampleCam", model: str = "EX-1") -> bytes:
    """An APP1 Exif segment (big-endian TIFF) with orientation, camera text and optionally a GPS IFD."""

    def rationals(values):
        return b"".join(struct.pack(">II", n, d) for n, d in values)

    make_b, model_b = make.encode() + b"\x00", model.encode() + b"\x00"
    entries = 3 + (1 if gps else 0)
    ifd0_len = 2 + entries * 12 + 4
    data_at = 8 + ifd0_len
    make_off = data_at
    model_off = make_off + len(make_b)
    gps_off = model_off + len(model_b)
    ifd0 = [
        (0x010F, 2, len(make_b), struct.pack(">I", make_off)),
        (0x0110, 2, len(model_b), struct.pack(">I", model_off)),
        (0x0112, 3, 1, struct.pack(">HH", orientation, 0)),
    ]
    if gps:
        ifd0.append((0x8825, 4, 1, struct.pack(">I", gps_off)))
    ifd0.sort()
    body = struct.pack(">H", len(ifd0)) + b"".join(struct.pack(">HHI", t, ty, c) + v for t, ty, c, v in ifd0) + b"\x00" * 4
    tail = make_b + model_b
    if gps:
        lat_off = gps_off + 2 + 4 * 12 + 4
        lon_off = lat_off + 24
        gps_ifd = [
            (1, 2, 2, b"N\x00\x00\x00"),
            (2, 5, 3, struct.pack(">I", lat_off)),
            (3, 2, 2, b"W\x00\x00\x00"),
            (4, 5, 3, struct.pack(">I", lon_off)),
        ]
        tail += struct.pack(">H", 4) + b"".join(struct.pack(">HHI", t, ty, c) + v for t, ty, c, v in gps_ifd) + b"\x00" * 4
        tail += rationals(GPS_LAT) + rationals(GPS_LON)
    tiff = b"MM\x00\x2a" + struct.pack(">I", 8) + body + tail
    return _segment(0xE1, b"Exif\x00\x00" + tiff)


def make_jpeg(
    width: int = 64,
    height: int = 48,
    rgb=(200, 100, 50),
    *,
    exif: bytes | None = None,
    xmp: bool = False,
    comment: str | None = None,
    jfif: bool = True,
    trailer: bytes = b"",
) -> bytes:
    """A flat-colour baseline JPEG (4:4:4, DC coefficients only) that real decoders open."""
    r, g, b = rgb
    ycc = (
        0.299 * r + 0.587 * g + 0.114 * b,
        -0.168736 * r - 0.331264 * g + 0.5 * b + 128,
        0.5 * r - 0.418688 * g - 0.081312 * b + 128,
    )
    dc = [round(8 * (min(255, max(0, v)) - 128)) for v in ycc]
    codes = _codes(_DC_COUNTS, _DC_SYMBOLS)
    eob = "0"
    first = "".join(_dc_bits(v, codes) + eob for v in dc)
    rest = "".join(_dc_bits(0, codes) + eob for _ in dc)
    mcus = ((width + 7) // 8) * ((height + 7) // 8)
    bits = first + rest * (mcus - 1)
    bits += "1" * (-len(bits) % 8)
    scan = int(bits, 2).to_bytes(len(bits) // 8, "big").replace(b"\xff", b"\xff\x00")

    out = b"\xff\xd8"
    if jfif:
        out += _segment(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    if exif:
        out += exif
    if xmp:
        out += _segment(
            0xE1,
            b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta><exif:GPSLatitude>38,42.0767N</exif:GPSLatitude></x:xmpmeta>",
        )
    if comment:
        out += _segment(0xFE, comment.encode())
    out += _segment(0xDB, b"\x00" + b"\x01" * 64)
    out += _segment(0xC0, struct.pack(">BHHB", 8, height, width, 3) + b"\x01\x11\x00\x02\x11\x00\x03\x11\x00")
    out += _segment(0xC4, b"\x00" + bytes(_DC_COUNTS) + bytes(_DC_SYMBOLS))
    out += _segment(0xC4, b"\x10" + bytes([1] + [0] * 15) + b"\x00")
    out += _segment(0xDA, b"\x03\x01\x00\x02\x00\x03\x00\x00\x3f\x00")
    return out + scan + b"\xff\xd9" + trailer


# ---------------------------------------------------------------- WebP, GIF, AVIF (header-only fixtures)


def _riff(chunks: bytes) -> bytes:
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WEBP" + chunks


def _wchunk(kind: bytes, body: bytes) -> bytes:
    return kind + struct.pack("<I", len(body)) + body + (b"\x00" if len(body) & 1 else b"")


def make_webp_lossy(width: int = 64, height: int = 48) -> bytes:
    return _riff(_wchunk(b"VP8 ", b"\x10\x02\x00\x9d\x01\x2a" + struct.pack("<HH", width, height) + b"\x00" * 6))


def make_webp_lossless(width: int = 64, height: int = 48) -> bytes:
    bits = (width - 1) | ((height - 1) << 14)
    return _riff(_wchunk(b"VP8L", b"\x2f" + struct.pack("<I", bits) + b"\x00" * 6))


def make_webp_extended(width: int = 64, height: int = 48, *, exif: bool = False) -> bytes:
    flags = 0x08 if exif else 0
    head = bytes([flags]) + b"\x00\x00\x00" + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
    chunks = _wchunk(b"VP8X", head) + _wchunk(
        b"VP8L", b"\x2f" + struct.pack("<I", (width - 1) | ((height - 1) << 14)) + b"\x00" * 5
    )
    if exif:
        chunks += _wchunk(b"EXIF", b"MM\x00\x2a" + GPS_MARKER)
    return _riff(chunks)


def make_gif(width: int = 64, height: int = 48) -> bytes:
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00\x00;"


def _box(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I4s", len(body) + 8, kind) + body


def make_avif(width: int = 64, height: int = 48) -> bytes:
    ispe = _box(b"ispe", b"\x00\x00\x00\x00" + struct.pack(">II", width, height))
    thumb = _box(b"ispe", b"\x00\x00\x00\x00" + struct.pack(">II", 16, 12))
    meta = _box(b"meta", b"\x00\x00\x00\x00" + _box(b"iprp", _box(b"ipco", thumb + ispe)))
    return _box(b"ftyp", b"avif\x00\x00\x00\x00avifmif1") + meta
