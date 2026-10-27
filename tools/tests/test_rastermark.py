"""JPEG/WebP marker embedding and verification (stdlib), plus the Pillow path when it's installed."""
import io
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pngmark  # noqa: E402
import rastermark as rm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
MARK = (ROOT / "src/assets/img/brand/mark.svg").read_text(encoding="utf-8")


def fake_jpeg():
    """Structurally valid JPEG header + scan bytes (not a decodable photo)."""
    app0 = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    return b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", len(app0) + 2) + app0 + b"\xff\xda\x00\x02" + b"\x12\x34" * 50 + b"\xff\xd9"


def fake_webp(fourcc=b"VP8 ", payload=b"\x00" * 31):
    pad = b"\x00" if len(payload) & 1 else b""
    body = fourcc + struct.pack("<I", len(payload)) + payload + pad
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body


class JpegMarker(unittest.TestCase):
    def test_round_trip(self):
        out = rm.embed(fake_jpeg(), "jpeg", "br")
        self.assertEqual(rm.verify(out, ".jpg"), (True, "ok"))
        self.assertEqual(rm.verify(out, ".JPEG"), (True, "ok"))
        self.assertIn(b"\xff\xfe", out[:4])  # COM straight after SOI

    def test_unmarked_tampered_and_duplicated_fail(self):
        self.assertEqual(rm.verify(fake_jpeg(), ".jpg"), (False, "no IT7Q watermark marker"))
        out = bytearray(rm.embed(fake_jpeg(), "jpeg", "br"))
        out[-10] ^= 0xFF
        ok, why = rm.verify(bytes(out), ".jpg")
        self.assertFalse(ok)
        self.assertIn("does not match", why)
        marked = rm.embed(fake_jpeg(), "jpeg", "br")
        com = marked[2:6 + len(rm._marker("br"))]
        twice = marked[:2] + com + marked[2:]
        self.assertEqual(rm.verify(twice, ".jpg"), (False, "more than one watermark marker"))

    def test_marker_outside_a_comment_is_not_enough(self):
        # marker text pasted into the scan data, not a COM segment
        sealed = rm._seal(fake_jpeg()[:-2] + rm._marker("br") + b"\xff\xd9")
        self.assertEqual(rm.verify(sealed, ".jpg"), (False, "no IT7Q watermark marker"))

    def test_not_a_jpeg(self):
        self.assertFalse(rm.verify(b"\x89PNG not really", ".jpg")[0])


class WebpMarker(unittest.TestCase):
    def test_simple_file_becomes_extended_with_xmp(self):
        out = rm.embed(fake_webp(), "webp", "tl", width=800, height=500, alpha=False)
        chunks = rm._riff_chunks(out)
        self.assertEqual([c[0] for c in chunks], [b"VP8X", b"VP8 ", b"XMP "])
        vp8x = chunks[0][1]
        self.assertEqual(vp8x[0], 0x04)  # XMP flag only
        self.assertEqual(int.from_bytes(vp8x[4:7], "little") + 1, 800)
        self.assertEqual(int.from_bytes(vp8x[7:10], "little") + 1, 500)
        self.assertEqual(rm.verify(out, ".webp"), (True, "ok"))

    def test_alpha_flag_and_existing_vp8x(self):
        out = rm.embed(fake_webp(b"VP8L"), "webp", "br", width=10, height=10, alpha=True)
        self.assertEqual(rm._riff_chunks(out)[0][1][0], 0x14)
        ext = rm._riff_build([(b"VP8X", bytes([0x10, 0, 0, 0]) + bytes(6)), (b"ALPH", b"\x00" * 3), (b"VP8 ", b"\x00" * 10)])
        out = rm.embed(ext, "webp", "br", width=1, height=1)
        chunks = rm._riff_chunks(out)
        self.assertEqual(chunks[0][1][0], 0x14)
        self.assertEqual([c[0] for c in chunks], [b"VP8X", b"ALPH", b"VP8 ", b"XMP "])
        self.assertEqual(rm.verify(out, ".webp"), (True, "ok"))

    def test_unmarked_and_tampered_fail(self):
        self.assertEqual(rm.verify(fake_webp(), ".webp"), (False, "no IT7Q watermark marker"))
        out = bytearray(rm.embed(fake_webp(), "webp", "br", width=8, height=8))
        out[40] ^= 0x01  # inside the VP8 payload
        self.assertFalse(rm.verify(bytes(out), ".webp")[0])
        self.assertFalse(rm.verify(bytes(out[:-4]), ".webp")[0])  # truncated / size mismatch


class Dispatch(unittest.TestCase):
    def setUp(self):
        self.paths, self.size = pngmark.load_mark_paths(MARK)

    def test_png_needs_no_pillow(self):
        img = pngmark.Image(300, 200, 3, bytearray(300 * 200 * 3))
        out = rm.watermark(pngmark.encode(img), ".png", self.paths, self.size)
        self.assertEqual(rm.verify(out, ".png"), (True, "ok"))

    def test_other_formats_rejected(self):
        with self.assertRaises(rm.MarkError):
            rm.watermark(b"GIF89a", ".gif", self.paths, self.size)
        self.assertFalse(rm.verify(b"GIF89a", ".gif")[0])

    @unittest.skipIf(rm.has_pillow(), "Pillow is installed")
    def test_jpeg_without_pillow_fails_with_instructions(self):
        with self.assertRaises(rm.MarkError) as cm:
            rm.watermark(fake_jpeg(), ".jpg", self.paths, self.size)
        self.assertIn("requirements.txt", str(cm.exception))


@unittest.skipUnless(rm.has_pillow(), "Pillow not installed (pip install -r requirements.txt)")
class PillowEndToEnd(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.Image = Image
        self.paths, self.size = pngmark.load_mark_paths(MARK)

    def photo(self, fmt, w=2000, h=1200, exif=True):
        im = self.Image.new("RGB", (w, h), (40, 90, 140))
        buf = io.BytesIO()
        kw = {}
        if exif:
            ex = self.Image.Exif()
            ex[0x0112] = 6  # orientation: rotate 90° on display
            kw["exif"] = ex.tobytes()
        im.save(buf, fmt, **kw)
        return buf.getvalue()

    def test_jpeg_and_webp(self):
        for fmt, ext in (("JPEG", ".jpg"), ("WEBP", ".webp")):
            out = rm.watermark(self.photo(fmt), ext, self.paths, self.size)
            self.assertEqual(rm.verify(out, ext), (True, "ok"), ext)
            im = self.Image.open(io.BytesIO(out))
            im.load()
            # rotation applied (2000x1200 shown rotated = 1200 wide), scaled to <= 1600 px, no EXIF left
            self.assertLessEqual(im.width, rm.MAX_WIDTH, ext)
            self.assertGreater(im.height, im.width, ext)
            self.assertFalse(im.getexif(), ext)


if __name__ == "__main__":
    unittest.main()
