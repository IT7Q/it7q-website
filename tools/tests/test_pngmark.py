import struct
import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pngmark as pm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
MARK = (ROOT / "src/assets/img/brand/mark.svg").read_text(encoding="utf-8")


def raw_png(width, height, colour_type, rows, depth=8, filters=None, extra=b"", interlace=0):
    """Hand-build a PNG with chosen filter bytes, to exercise the decoder."""
    raw = b"".join(bytes([(filters or [0] * height)[y]]) + rows[y] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, depth, colour_type, 0, 0, interlace)
    return pm.SIG + pm._chunk(b"IHDR", ihdr) + extra + pm._chunk(b"IDAT", zlib.compress(raw)) + pm._chunk(b"IEND", b"")


def photo(w=400, h=300):
    px = bytearray()
    for y in range(h):
        for x in range(w):
            px += bytes(((x * 7) & 255, (y * 5) & 255, ((x + y) * 3) & 255))
    return pm.encode(pm.Image(w, h, 3, px))


class DecodeTests(unittest.TestCase):
    def test_round_trip_rgb_and_rgba(self):
        for ch in (3, 4):
            img = pm.Image(5, 4, ch, bytearray(range(5 * 4 * ch)))
            back = pm.decode(pm.encode(img))
            self.assertEqual((back.width, back.height, back.channels), (5, 4, ch))
            self.assertEqual(back.pixels, img.pixels)

    def test_all_filter_types(self):
        # Sub, Up, Average and Paeth rows on a constant image must decode to that constant
        w, h = 3, 5
        rows = [bytes([10, 20, 30] * w)] + [bytes(3 * w)] * (h - 1)
        img = pm.decode(raw_png(w, h, 2, rows, filters=[0, 2, 2, 2, 2]))
        self.assertEqual(bytes(img.pixels), bytes([10, 20, 30] * w * h))
        sub_row = bytes([10, 20, 30] + [0, 0, 0] * (w - 1))
        img = pm.decode(raw_png(w, 1, 2, [sub_row], filters=[1]))
        self.assertEqual(bytes(img.pixels), bytes([10, 20, 30] * w))
        for f in (3, 4):  # first row: Average/Paeth reduce to Sub-like behaviour
            img = pm.decode(raw_png(w, 1, 2, [bytes([8, 8, 8, 4, 4, 4, 0, 0, 0])], filters=[f]))
            self.assertEqual(len(img.pixels), 9)

    def test_palette_and_grey(self):
        plte = pm._chunk(b"PLTE", bytes([255, 0, 0, 0, 255, 0]))
        img = pm.decode(raw_png(2, 1, 3, [bytes([0, 1])], extra=plte))
        self.assertEqual(bytes(img.pixels), bytes([255, 0, 0, 0, 255, 0]))
        img = pm.decode(raw_png(4, 1, 3, [bytes([0b01010101])], depth=2, extra=plte))
        self.assertEqual(bytes(img.pixels), bytes([0, 255, 0] * 4))
        img = pm.decode(raw_png(2, 1, 0, [bytes([0, 255])]))
        self.assertEqual(bytes(img.pixels), bytes([0, 0, 0, 255, 255, 255]))

    def test_rejects_what_it_cannot_handle(self):
        with self.assertRaises(pm.PNGError):
            pm.decode(raw_png(1, 1, 2, [bytes(3)], interlace=1))
        with self.assertRaises(pm.PNGError):
            pm.decode(raw_png(1, 1, 2, [bytes(6)], depth=16))
        with self.assertRaises(pm.PNGError):
            pm.decode(b"\xff\xd8\xff\xe0 not a png")
        bad = bytearray(photo(10, 10))
        bad[40] ^= 0xFF  # corrupt a byte inside IDAT
        with self.assertRaises((pm.PNGError, zlib.error)):
            pm.decode(bytes(bad))


class WatermarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths, cls.size = pm.load_mark_paths(MARK)

    def test_marked_image_verifies(self):
        out = pm.watermark(photo(), self.paths, self.size)
        self.assertEqual(pm.verify(out), (True, "ok"))

    def test_unmarked_and_tampered_fail(self):
        self.assertFalse(pm.verify(photo())[0])
        img = pm.decode(pm.watermark(photo(), self.paths, self.size))
        marker = img.texts[pm.MARK_KEY].decode()
        img.pixels[0] ^= 0xFF
        ok, why = pm.verify(pm.encode(img, marker))
        self.assertFalse(ok)
        self.assertIn("does not match", why)

    def test_mark_lands_in_chosen_corner_only(self):
        src = pm.decode(photo())
        for corner in ("br", "bl", "tr", "tl"):
            out = pm.decode(pm.watermark(photo(), self.paths, self.size, corner))
            changed = [
                (i // 3) for i in range(0, len(src.pixels), 3) if src.pixels[i:i + 3] != out.pixels[i:i + 3]
            ]
            self.assertTrue(changed, corner)
            xs = {p % src.width for p in changed}
            ys = {p // src.width for p in changed}
            right, bottom = min(xs) > src.width / 2, min(ys) > src.height / 2
            self.assertEqual(right, corner[1] == "r", corner)
            self.assertEqual(bottom, corner[0] == "b", corner)
            # subtle: no pixel moves by more than the opacity allows
            diff = max(abs(a - b) for a, b in zip(src.pixels, out.pixels))
            self.assertLessEqual(diff, round(255 * pm.OPACITY) + 1)

    def test_too_small_image_fails_closed(self):
        with self.assertRaises(pm.PNGError):
            pm.watermark(photo(60, 60), self.paths, self.size)


if __name__ == "__main__":
    unittest.main()
