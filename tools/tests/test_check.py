"""Each guard in tools/check.py must actually fire. Builds once, then breaks a copy of dist/."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import check  # noqa: E402
import pngmark  # noqa: E402

ROOT = TOOLS.parent


class CheckGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        res = subprocess.run([sys.executable, str(TOOLS / "build.py")], capture_output=True, text=True)
        if res.returncode != 0:
            raise AssertionError("build/check failed on a clean tree:\n" + res.stdout + res.stderr)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dist = self.tmp / "dist"
        shutil.copytree(ROOT / "dist", self.dist)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def failures_after(self, rel, transform):
        f = self.dist / rel
        f.write_text(transform(f.read_text(encoding="utf-8")), encoding="utf-8")
        return "\n".join(check.run(self.dist).failures)

    def inject(self, html_snippet):
        return self.failures_after("index.html", lambda s: s.replace("</main>", html_snippet + "</main>"))

    def test_clean_build_passes(self):
        self.assertEqual(check.run(self.dist).failures, [])

    def test_broken_link(self):
        self.assertIn("broken link /nowhere/", self.inject('<a href="/nowhere/">x</a>'))

    def test_csp_inline_script_style_handler(self):
        out = self.inject('<script>alert(1)</script><p style="color:red" onclick="x()">x</p>')
        self.assertIn("inline <script>", out)
        self.assertIn("inline style", out)
        self.assertIn("inline event handler", out)

    def test_public_wording_guard(self):
        for word in ("WireGuard", "tunnel", "Agent Smith", "n8n", "hooks.nubius.com.au"):
            self.assertIn("public-wording guard", self.inject("<p>%s</p>" % word), word)

    def test_price_and_financial_guards(self):
        self.assertIn("price guard", self.inject("<p>Only $99 a month</p>"))
        self.assertIn("financial guard", self.inject("<p>Projected revenue of $250k</p>"))

    def test_pack_colour_guard(self):
        self.assertIn("pack colour", self.failures_after("assets/css/site.css", lambda s: s + "\na{color:#0e1326}"))

    def test_unclosed_tag_and_h1(self):
        out = self.inject("<div><h1>Second</h1>")
        self.assertIn("exactly one <h1>", out)
        self.assertIn("unexpected </main>", out)

    def test_svg_external_ref(self):
        self.assertIn("missing or external", self.inject('<svg><use href="https://evil.example/x.svg#a"/></svg>'))

    def test_unwatermarked_raster_fails(self):
        img = pngmark.Image(300, 200, 3, bytearray(300 * 200 * 3))
        (self.dist / "assets/img/raw.png").write_bytes(pngmark.encode(img))
        (self.dist / "assets/img/photo.jpg").write_bytes(b"\xff\xd8\xff\xe0")
        out = "\n".join(check.run(self.dist).failures)
        self.assertIn("raw.png: watermark check: no IT7Q watermark marker", out)
        self.assertIn("photo.jpg: raster is not a watermarked PNG", out)


if __name__ == "__main__":
    unittest.main()
