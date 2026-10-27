"""Each guard in tools/check.py must actually fire. Builds once, then breaks a copy of dist/."""
import datetime
import json
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

    def test_only_scutum_price_exactly(self):
        self.assertEqual(check.approved_prices(), {"$68"})
        self.assertNotIn("price guard", self.inject("<p>SCUTUM from $68.</p>"))
        self.assertIn("'$680'", self.inject("<p>From $680</p>"))
        self.assertIn("'$149'", self.inject("<p>T1 Scout from $149</p>"))

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
        self.assertIn("photo.jpg: watermark check: unreadable JPEG", out)
        (self.dist / "assets/img/anim.gif").write_bytes(b"GIF89a")
        self.assertIn("anim.gif: watermark check: format not allowed", "\n".join(check.run(self.dist).failures))

    def test_font_needs_licence(self):
        (self.dist / "assets/fonts/Rajdhani-OFL.txt").unlink()
        out = "\n".join(check.run(self.dist).failures)
        self.assertIn("Rajdhani-Bold.ttf: font licence guard", out)
        self.assertNotIn("Exo2-wght.ttf", out)

    def test_unpublished_portfolio_entry(self):
        self.assertIn("unpublished entry 'Pro Energy Solutions'", self.inject("<p>Pro Energy Solutions</p>"))

    def test_division_pages_carry_every_card(self):
        projects = json.loads((ROOT / "src/data/projects.json").read_text(encoding="utf-8"))
        self.assertEqual(len(projects), 70)
        pages = "".join(p.read_text(encoding="utf-8") for p in self.dist.glob("divisions/*/index.html"))
        for p in projects:
            self.assertIn('id="%s"' % p["id"].lower(), pages, p["id"])
        self.assertNotIn("What our clients say", (self.dist / "index.html").read_text(encoding="utf-8"))


class ConsentGuard(unittest.TestCase):
    GOOD = {"quote": "Great work.", "name": "Sam", "approved": True,
            "consent": {"recorded": "2026-10-01", "method": "email"}}

    def problems(self, **changes):
        entry = json.loads(json.dumps(self.GOOD))
        for k, v in changes.items():
            if v is None:
                entry.pop(k, None)
            else:
                entry[k] = v
        return " | ".join(check.testimonial_problems(entry, today=datetime.date(2026, 10, 28)))

    def test_good_entry_passes(self):
        self.assertEqual(self.problems(), "")
        self.assertEqual(self.problems(name=None, business="Acme Club"), "")

    def test_missing_or_bad_consent_fails(self):
        self.assertIn("lacks recorded consent", self.problems(consent=None))
        self.assertIn("consent.recorded", self.problems(consent={"method": "email"}))
        self.assertIn("consent.method", self.problems(consent={"recorded": "2026-10-01"}))
        self.assertIn("consent.method", self.problems(consent={"recorded": "2026-10-01", "method": "verbal"}))
        self.assertIn("in the future", self.problems(consent={"recorded": "2027-01-01", "method": "email"}))
        self.assertIn("YYYY-MM-DD", self.problems(consent={"recorded": "last week", "method": "email"}))

    def test_other_fields(self):
        self.assertIn("has no quote", self.problems(quote=" "))
        self.assertIn("name or a business", self.problems(name=None))
        self.assertIn("approved must be", self.problems(approved="yes"))

    def test_file_level_guard(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            dist = tmp / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<p>&ldquo;Not yet approved&rdquo;</p>", encoding="utf-8")
            data = {"_example": {"quote": "ignored"}, "entries": [
                dict(self.GOOD, approved=False, quote="Not yet approved"),
                {"quote": "No consent here", "name": "Jo", "approved": False},
            ]}
            path = tmp / "testimonials.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            r = check.Report()
            check.check_testimonials(dist, r, path)
            out = "\n".join(r.failures)
            self.assertIn("unapproved entry 1 appears in dist/", out)
            self.assertIn("entry 2 lacks recorded consent", out)
            self.assertNotIn("entry 1 lacks", out)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
