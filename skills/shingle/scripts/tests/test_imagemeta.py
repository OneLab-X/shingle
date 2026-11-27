from __future__ import annotations

import unittest

import image_fixtures as fx
from helpers import SCRIPTS  # noqa: F401  (puts scripts/ on sys.path)

import imagemeta
from imagemeta import ImageError


class HeaderParserTests(unittest.TestCase):
    def check(self, data, fmt, w, h):
        info = imagemeta.probe(data)
        self.assertEqual((info.format, info.width, info.height), (fmt, w, h))

    def test_png(self):
        self.check(fx.make_png(120, 80), "png", 120, 80)

    def test_jpeg(self):
        self.check(fx.make_jpeg(97, 41), "jpeg", 97, 41)

    def test_jpeg_with_exif_and_gps(self):
        self.check(fx.make_jpeg(64, 48, exif=fx.exif_block(1), xmp=True, comment="x"), "jpeg", 64, 48)

    def test_jpeg_orientation_swaps_display_size(self):
        info = imagemeta.probe(fx.make_jpeg(64, 48, exif=fx.exif_block(6)))
        self.assertEqual((info.width, info.height, info.orientation), (64, 48, 6))
        self.assertEqual(info.display_size, (48, 64))

    def test_webp_lossy_lossless_extended(self):
        self.check(fx.make_webp_lossy(321, 123), "webp", 321, 123)
        self.check(fx.make_webp_lossless(1600, 900), "webp", 1600, 900)
        self.check(fx.make_webp_extended(2000, 1500), "webp", 2000, 1500)

    def test_gif(self):
        self.check(fx.make_gif(30, 20), "gif", 30, 20)

    def test_avif_uses_the_largest_ispe(self):
        self.check(fx.make_avif(640, 480), "avif", 640, 480)


class RejectionTests(unittest.TestCase):
    def reject(self, data, text):
        with self.assertRaises(ImageError) as cm:
            imagemeta.probe(data)
        self.assertIn(text, str(cm.exception))

    def test_empty_and_unknown(self):
        self.reject(b"", "empty")
        self.reject(b"hello world, not a picture", "not a recognised image")

    def test_zero_size(self):
        self.reject(fx.make_png(0, 10), "zero-size")
        self.reject(fx.make_gif(0, 5), "zero-size")
        self.reject(fx.make_jpeg(0, 0), "corrupt")

    def test_truncated(self):
        self.reject(fx.make_png()[:-20], "corrupt PNG")
        self.reject(fx.make_jpeg()[:-30], "corrupt JPEG")
        self.reject(fx.make_webp_lossy()[:-4], "corrupt WebP")
        self.reject(fx.make_gif()[:-1], "corrupt GIF")
        self.reject(fx.make_avif()[:-6], "corrupt AVIF")

    def test_too_big(self):
        self.reject(b"\xff\xd8" + b"\x00" * (imagemeta.MAX_BYTES + 1), "25 MB")


class StripJpegTests(unittest.TestCase):
    def setUp(self):
        self.original = fx.make_jpeg(
            80, 60, exif=fx.exif_block(1), xmp=True, comment="shot by Sam", trailer=b"THUMBNAIL-WITH-GPS"
        )
        self.info = imagemeta.probe(self.original)
        self.clean = imagemeta.sanitize(self.original, self.info)

    def test_original_really_has_gps(self):
        self.assertTrue(imagemeta.has_gps(self.original))
        self.assertIn(fx.GPS_MARKER, self.original)

    def test_gps_is_gone_and_reported(self):
        self.assertFalse(imagemeta.has_gps(self.clean.data))
        for needle in (fx.GPS_MARKER, b"Exif", b"GPSLatitude", b"shot by Sam", b"THUMBNAIL", b"ExampleCam"):
            self.assertNotIn(needle, self.clean.data)
        report = " | ".join(self.clean.stripped)
        for word in ("GPS location", "camera make", "XMP", "comment", "after the image"):
            self.assertIn(word, report)

    def test_still_valid_same_size_same_pixels(self):
        info = imagemeta.probe(self.clean.data)
        self.assertEqual((info.width, info.height), (80, 60))
        self.assertTrue(self.clean.data.startswith(b"\xff\xd8\xff\xe0"))  # JFIF kept
        self.assertTrue(self.clean.data.endswith(b"\xff\xd9"))
        scan = lambda d: d[d.index(b"\xff\xda") : d.index(b"\xff\xd9", d.index(b"\xff\xda")) + 2]  # noqa: E731
        self.assertEqual(scan(self.clean.data), scan(self.original))

    def test_orientation_is_kept_without_location(self):
        rotated = fx.make_jpeg(80, 60, exif=fx.exif_block(6))
        clean = imagemeta.sanitize(rotated, imagemeta.probe(rotated)).data
        info = imagemeta.probe(clean)
        self.assertEqual((info.orientation, info.display_size), (6, (60, 80)))
        self.assertFalse(imagemeta.has_gps(clean))
        self.assertNotIn(b"ExampleCam", clean)

    def test_upright_photo_gets_no_exif_at_all(self):
        self.assertNotIn(b"Exif", self.clean.data)

    def test_stripping_twice_changes_nothing(self):
        again = imagemeta.sanitize(self.clean.data, imagemeta.probe(self.clean.data))
        self.assertEqual(again.data, self.clean.data)
        self.assertEqual(again.stripped, [])


class StripOtherFormatsTests(unittest.TestCase):
    def test_png_text_chunks(self):
        original = fx.make_png(20, 10, text={"Comment": "taken at 38.7N 9.1W", "Author": "Sam"})
        clean = imagemeta.sanitize(original, imagemeta.probe(original))
        self.assertNotIn(b"tEXt", clean.data)
        self.assertNotIn(b"38.7N", clean.data)
        self.assertEqual(clean.stripped, ["PNG text chunks (2)"])
        self.assertEqual(imagemeta.probe(clean.data).width, 20)

    def test_png_bad_checksum_is_rejected(self):
        data = bytearray(fx.make_png())
        idat = data.index(b"IDAT")
        data[idat + 6] ^= 0xFF
        with self.assertRaises(ImageError):
            imagemeta.sanitize(bytes(data), imagemeta.probe(bytes(data)))

    def test_webp_exif_chunk_is_removed(self):
        original = fx.make_webp_extended(50, 40, exif=True)
        clean = imagemeta.sanitize(original, imagemeta.probe(original))
        self.assertEqual(clean.stripped, ["EXIF"])
        self.assertNotIn(b"EXIF", clean.data)
        self.assertNotIn(fx.GPS_MARKER, clean.data)
        info = imagemeta.probe(clean.data)
        self.assertEqual((info.width, info.height), (50, 40))
        self.assertEqual(clean.data[20] & 0x08, 0)  # VP8X "has EXIF" flag cleared

    def test_gif_and_plain_webp_unchanged(self):
        for data in (fx.make_gif(), fx.make_webp_lossy(), fx.make_webp_lossless()):
            self.assertEqual(imagemeta.sanitize(data, imagemeta.probe(data)).data, data)


class AltRuleTests(unittest.TestCase):
    def bad(self, alt, text, file=""):
        self.assertTrue(
            any(text in p for p in imagemeta.alt_problems(alt, file=file)), (alt, imagemeta.alt_problems(alt, file=file))
        )

    def test_good_alt_passes(self):
        self.assertEqual(imagemeta.alt_problems("Long wooden table set for six under a window"), [])

    def test_too_long(self):
        self.bad("a" * 126, "126 characters")
        self.assertEqual(imagemeta.alt_problems("a" * 125), [])

    def test_image_of(self):
        self.bad("Image of a dining room", "image of")
        self.bad("A photo of the shopfront", "image of")
        self.bad("Picture showing two chairs", "image of")

    def test_filename(self):
        self.bad("dining-room.jpg", "file name")
        self.bad("IMG_4521", "file name")
        self.bad("Dining room", "file name", file="dining-room.jpg")
        self.bad("DSC 0012", "file name")


class NameTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(imagemeta.slugify("Dining Room (2)!"), "dining-room-2")
        self.assertEqual(imagemeta.slugify("Café São João"), "cafe-sao-joao")
        self.assertEqual(imagemeta.slugify("日本語"), "image")

    def test_subject_from_name(self):
        self.assertEqual(imagemeta.subject_from_name("dining-room"), "Dining room")
        self.assertEqual(imagemeta.subject_from_name("IMG_4521"), "")
        self.assertEqual(imagemeta.subject_from_name("PXL_20240101_123456789"), "")


if __name__ == "__main__":
    unittest.main()
