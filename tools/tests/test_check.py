"""Each guard in tools/check.py must actually fire. Builds once, then breaks a copy of dist/."""
import datetime
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import build  # noqa: E402
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
        f = check.asset(self.dist, rel)  # CSS/JS carry a content hash in dist/
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

    def test_webhook_origin_only_in_config(self):
        self.assertEqual(check.run(self.dist).failures, [])  # config.js mentions it: allowed
        out = self.failures_after("assets/js/forms.js", lambda s: s + "\n// https://hooks.nubius.com.au/webhook\n")
        self.assertIn("assets/js/forms.js: public-wording guard", out)

    def test_hashed_assets(self):
        self.assertIn("assets/css/site.css: content hash doesn't match",
                      self.failures_after("assets/css/site.css", lambda s: s + "\n/* edited in dist */"))
        nda = check.asset(self.dist, "assets/js/nda.js")
        nda.rename(nda.with_name("nda.js"))
        self.assertIn("assets/js/nda.js: not content-hashed", "\n".join(check.run(self.dist).failures))

    def test_cache_headers(self):
        out = self.failures_after("_headers", lambda s: s.replace("/assets/js/*\n  Cache-Control: public, max-age=31536000, immutable",
                                                                  "/assets/js/*\n  Cache-Control: public, max-age=86400"))
        self.assertIn("/assets/js/* needs", out)
        out = self.failures_after("_headers", lambda s: s.replace("/*\n", "/*\n  Cache-Control: public, max-age=3600\n", 1))
        self.assertIn("/* sets Cache-Control: HTML must keep Pages' default", out)

    def test_mock_config_refused_unless_mock(self):
        def to_mock(s):
            return s.replace('"mock": false', '"mock": true').replace("https://forms.it7q.com.au/webhook", "/webhook")
        self.assertIn("LOCAL MOCK build", self.failures_after("assets/js/config.js", to_mock))
        self.assertEqual([f for f in check.run(self.dist, mock=True).failures if "content hash" not in f], [])
        out = self.failures_after("assets/js/config.js", lambda s: s.replace('"mock": true', '"mock": false'))
        self.assertIn("hooks must be", out)

    def test_html_sinks_in_scripts(self):
        for sink in ("el.innerHTML = x", "el.insertAdjacentHTML('beforeend', x)", "eval(x)", "document.write(x)"):
            out = self.failures_after("assets/js/nda.js", lambda s, sink=sink: s + "\n" + sink + ";\n")
            self.assertIn("textContent only", out, sink)

    def test_unlabelled_field(self):
        self.assertIn("has no <label for>", self.inject('<input type="text" id="lonely" name="x">'))
        self.assertNotIn("field ok has", self.inject('<label for="ok">Ok</label><input id="ok" name="ok">'))

    def test_font_needs_licence(self):
        (self.dist / "assets/fonts/Rajdhani-OFL.txt").unlink()
        out = "\n".join(check.run(self.dist).failures)
        self.assertIn("Rajdhani-Bold.ttf: font licence guard", out)
        self.assertNotIn("Exo2-wght.ttf", out)

    def test_unpublished_portfolio_entry(self):
        self.assertIn("unpublished entry 'Pro Energy Solutions'", self.inject("<p>Pro Energy Solutions</p>"))

    def test_division_pages_carry_every_card(self):
        projects = json.loads((ROOT / "src/data/projects.json").read_text(encoding="utf-8"))
        self.assertEqual(len(projects), 71)
        pages = "".join(p.read_text(encoding="utf-8") for p in self.dist.glob("divisions/*/index.html"))
        for p in projects:
            self.assertIn('id="%s"' % p["id"].lower(), pages, p["id"])
        self.assertNotIn("What our clients say", (self.dist / "index.html").read_text(encoding="utf-8"))

    def test_resource_only_names(self):
        def add(s):
            return s.replace("</main>", "<p>ClamAV and WireGuard are worth a look.</p></main>")
        self.assertNotIn("public-wording guard", self.failures_after("resources/index.html", add))
        self.assertIn("public-wording guard", self.failures_after("shop/index.html", add))
        guide = self.dist / "resources/guides/clamav/index.html"  # built once Chris's file is in
        guide.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.dist / "resources/index.html", guide)
        out = self.failures_after("resources/guides/clamav/index.html",
                                  lambda s: s.replace("</main>", "<p>We use ClamAV on our servers.</p></main>"))
        self.assertIn("reads as IT7Q's own setup (Q55)", out)
        self.assertIn("'n8n'", self.failures_after("resources/index.html", lambda s: s + "<p>n8n</p>"))

    def test_download_guard(self):
        out = self.failures_after("resources/index.html", lambda s: s.replace(
            "</main>", '<a href="https://bitwarden.example.net/setup.exe" data-download="official">x</a></main>'))
        self.assertIn("is not an official download page", out)
        (self.dist / "resources/setup.exe").write_bytes(b"MZ")
        (self.dist / "assets/tool.zip").write_bytes(b"PK")
        out = "\n".join(check.run(self.dist).failures)
        self.assertIn("resources/setup.exe: download-link guard", out)
        self.assertIn("assets/tool.zip: download-link guard", out)
        self.assertTrue(check.official_download("https://www.gimp.org/downloads/", "gimp.org"))
        self.assertFalse(check.official_download("https://gimp.org.evil.example/", "gimp.org"))
        self.assertFalse(check.official_download("http://www.gimp.org/downloads/", "gimp.org"))

    def write_pdf(self, rel, body, stream=b""):
        path = self.dist / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        z = zlib.compress(stream)
        path.write_bytes(b"%PDF-1.7\n" + body + b"\n1 0 obj<</Filter/FlateDecode>>stream\n" + z + b"\nendstream\n%%EOF\n")

    def pdf_failures(self):
        return "\n".join(f for f in check.run(self.dist).failures if "PDF guard" in f)

    def test_pdf_guard(self):
        self.write_pdf("resources/guides/pdf/clamav.pdf", b"<</Title (ClamAV) /Author ()>>", b"BT (Scan with ClamAV) Tj ET")
        self.assertEqual(self.pdf_failures(), "")
        self.write_pdf("resources/guides/pdf/clamav.pdf", b"<</Author (Chris)>>")
        self.assertIn("metadata must be stripped", self.pdf_failures())
        self.write_pdf("resources/guides/pdf/clamav.pdf", b"", b"saved from /home/chris/guides")
        self.assertIn("local file path", self.pdf_failures())
        self.write_pdf("resources/guides/pdf/clamav.pdf", b"", b"BT (set up in n8n) Tj ET")
        self.assertIn("'n8n' must not appear", self.pdf_failures())
        (self.dist / "resources/guides/pdf/clamav.pdf").unlink()
        self.write_pdf("assets/brochure.pdf", b"", b"WireGuard")
        out = self.pdf_failures()
        self.assertIn("PDFs ship only as guides", out)
        self.assertIn("'WireGuard' must not appear", out)

    def test_portus_discretion_guard(self):
        self.assertNotIn("PORTUS discretion", self.inject("<p>We report abuse of this website to the police.</p>"))
        out = self.failures_after("divisions/portus/index.html",
                                  lambda s: s.replace("</main>", "<p>Help for people leaving domestic violence.</p></main>"))
        self.assertIn("PORTUS discretion guard: 'domestic'", out)
        out = self.inject("<p>PORTUS can help people escaping abuse.</p>")
        self.assertIn("PORTUS discretion guard", out)

    def test_artwork_guard(self):
        out = self.failures_after("index.html", lambda s: s.replace(
            "<main", '<div class="ph ph--1x1"><span class="ph__id">IMG-99</span></div><main', 1))
        self.assertIn("index.html: visible image placeholder left", out)
        out = self.failures_after("index.html", lambda s: re.sub(r' data-img="[^"]+"', "", s, count=1))
        self.assertIn("index.html: artwork without role, label or image id", out)

    def test_footer_guard(self):
        out = self.failures_after("index.html", lambda s: s.replace(
            '<nav id="site-nav"', '<a href="https://staff.it7q.com.au">Staff</a><nav id="site-nav"'))
        self.assertIn("index.html: footer guard: expected exactly one Staff link, found 2", out)
        site = json.loads((ROOT / "src/data/site.json").read_text(encoding="utf-8"))
        for bad in ("https://staff.nubius.com.au", "http://staff.it7q.com.au", ""):
            r = check.Report()
            check.check_footer_links(self.dist, r, dict(site, staff_url=bad))
            self.assertIn("staff_url must be", "\n".join(r.failures), bad)
        r = check.Report()
        check.check_footer_links(self.dist, r, dict(site, social=[{"key": "x", "href": "http://x.example/it7q"}]))
        self.assertIn("social link x must be https://", "\n".join(r.failures))
        r = check.Report()
        shown = next(s for s in site["social"] if s["key"] == "instagram")
        check.check_footer_links(self.dist, r, dict(site, social=[dict(shown, hidden=True)]))
        self.assertIn("hidden social link", "\n".join(r.failures))

    def test_hooks_base_is_one_value(self):
        headers = (self.dist / "_headers").read_text(encoding="utf-8")
        self.assertIn("connect-src 'self' https://forms.it7q.com.au ", headers)
        self.assertEqual(check.prod_hooks(), check.LAUNCH_HOOKS)  # Phase 6 switch (Q58)
        real = check.prod_hooks
        check.prod_hooks = lambda: "https://hooks.nubius.com.au/webhook"  # switching back is refused
        try:
            out = "\n".join(check.run(self.dist).failures)
        finally:
            check.prod_hooks = real
        self.assertIn("hooks must not be on nubius", out)
        self.assertIn("hooks must be https://hooks.nubius.com.au/webhook", out)

    def with_endpoints(self, key):
        """check.run(launch=True) failures with endpoints.json swapped for one holding this site key."""
        real = check.ENDPOINTS
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "endpoints.json").write_text(json.dumps({"hooks": check.LAUNCH_HOOKS, "turnstile_site_key": key}))
            check.ENDPOINTS = tmp / "endpoints.json"
            return "\n".join(check.run(self.dist, launch=True).failures)
        finally:
            check.ENDPOINTS = real
            shutil.rmtree(tmp)

    def test_launch_gates(self):
        self.assertEqual(check.run(self.dist).failures, [])
        self.assertEqual(check.run(self.dist, launch=True).failures, [])  # key set (Q66), launch decision made

        def launch_after(rel, transform):
            f = check.asset(self.dist, rel)
            original = f.read_text(encoding="utf-8")
            f.write_text(transform(original), encoding="utf-8")
            try:
                return "\n".join(check.run(self.dist, launch=True).failures)
            finally:
                f.write_text(original, encoding="utf-8")

        out = launch_after("legal/terms/index.html", lambda s: s.replace(
            "</main>", '<p class="draft-note">Draft. Being checked by a lawyer.</p></main>'))
        self.assertIn("legal/terms/index.html: launch: still marked as a legal draft", out)
        out = launch_after("legal/privacy/index.html", lambda s: s.replace("Last updated:", "Updated"))
        self.assertIn("legal/privacy/index.html: launch: no 'Last updated: <date>' line", out)
        out = launch_after("access/index.html", lambda s: s.replace("nda-explainer", "x"))
        self.assertIn("access/index.html: launch: no 'How access works' box", out)
        out = launch_after("portfolio/index.html", lambda s: s.replace("</main>", "<p>PLACEHOLDER: later</p></main>"))
        self.assertIn("portfolio/index.html: launch: 'PLACEHOLDER' must not appear anywhere in dist/", out)
        out = launch_after("assets/css/site.css", lambda s: s + "/* PLACEHOLDER */")
        self.assertIn("assets/css/site.css: launch: 'PLACEHOLDER'", out)
        out = self.with_endpoints("PLACEHOLDER-turnstile-site-key")
        self.assertIn("launch: turnstile_site_key is 'PLACEHOLDER-turnstile-site-key'", out)
        out = self.with_endpoints("0x4AAAAAAAexampleKey00")
        self.assertIn("built without the site key", out)  # dist was built with a different key
        self.assertNotIn("turnstile_site_key is", out)
        self.assertEqual(check.main([str(self.dist), "--mock", "--launch"]), 1)


class LaunchDoc(unittest.TestCase):
    def test_launch_doc_matches_the_repo(self):
        doc = (ROOT / "deploy/LAUNCH.md").read_text(encoding="utf-8")
        site = json.loads((ROOT / "src/data/site.json").read_text(encoding="utf-8"))
        self.assertEqual(site["staff_url"], "https://staff.it7q.com.au")
        for needle in ("tools/check.py --launch", check.LAUNCH_HOOKS,
                       "it7q-staff.pages.dev", "*.it7q-staff.pages.dev", "it7qqld.cloudflareaccess.com"):
            self.assertIn(needle, doc)
        for f in re.findall(r"\b(assets/(?:js|css)/[\w.-]+)", doc):
            self.assertTrue(f == check.CONFIG_JS or (ROOT / "src" / f).exists(), f)  # config.js is generated
        staff = ROOT / "deploy/staff"
        self.assertIn("noindex", (staff / "index.html").read_text(encoding="utf-8"))
        headers = (staff / "_headers").read_text(encoding="utf-8")
        self.assertIn("default-src 'none'", headers)
        self.assertIn("X-Robots-Tag: noindex", headers)


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


class NdaExplainer(unittest.TestCase):
    """The 'How access works' box quotes the NDA word for word (3 Nov launch decision)."""

    def test_quotes_are_the_ndas_own_words(self):
        nda = build.load_nda()
        plain = " ".join(nda["text"].replace("**", "").split())
        for page in ("access/index.html", "legal/nda/index.html"):
            text = (ROOT / "dist" / page).read_text(encoding="utf-8")
            box = re.search(r'<div class="panel-box nda-explainer">.*?</div>', text, re.S).group(0)
            quotes = [html.unescape(q) for q in re.findall(r"<q>(.*?)</q>", box)]
            self.assertGreaterEqual(len(quotes), 8, page)
            for q in quotes:
                self.assertIn(" ".join(q.split()), plain, page)
            for words in ("three (3) years", "two (2) years after the Term ends", "trade secret",
                          "within a few business days"):
                self.assertIn(words, box, page)

    def test_explainer_refuses_a_misquote(self):
        ctx = {"nda": build.load_nda()}
        with self.assertRaises(build.BuildError):
            build.nda_quote(ctx, "runs for five (5) years")

    def test_every_nda_version_needs_a_date(self):
        with self.assertRaises(build.BuildError):
            build.load_legal({"version": "9.9", "sha256": "", "text": ""})
        self.assertEqual(build.load_legal(build.load_nda())["nda"], "28 October 2026")
