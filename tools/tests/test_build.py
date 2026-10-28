"""Build-side rules: testimonials, project data validation, placeholders."""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build  # noqa: E402

ENTRY = {"quote": "They sorted our Wi-Fi & explained it.", "name": "Sam", "business": "Acme Club",
         "approved": True, "consent": {"recorded": "2026-10-01", "method": "email"}}


class Testimonials(unittest.TestCase):
    def test_section_only_with_approved_entries(self):
        self.assertEqual(build.c_testimonials({"testimonials": []}), "")
        data = {"_example": dict(ENTRY), "entries": [dict(ENTRY, approved=False)]}
        self.assertEqual(build.approved_testimonials(data), [])
        approved = build.approved_testimonials({"entries": [ENTRY, dict(ENTRY, approved=False, quote="Hidden")]})
        out = build.c_testimonials({"testimonials": approved})
        self.assertIn("Wi-Fi &amp; explained it.", out)
        self.assertIn("<figcaption>Sam, Acme Club</figcaption>", out)
        self.assertNotIn("Hidden", out)

    def test_approved_entry_without_consent_stops_the_build(self):
        bad = dict(ENTRY)
        del bad["consent"]
        with self.assertRaises(build.BuildError):
            build.approved_testimonials({"entries": [bad]})

    def test_repo_file_ships_empty(self):
        data = json.loads((build.SRC / "data/testimonials.json").read_text(encoding="utf-8"))
        self.assertEqual(data["entries"], [])


class Projects(unittest.TestCase):
    def setUp(self):
        self.divisions = build.load_json("divisions.json")
        self.projects = build.load_json("projects.json")

    def test_repo_data_is_valid(self):
        build.check_projects(self.projects, self.divisions)
        prices = [p for p in self.projects if p.get("public_price")]
        self.assertEqual([p["id"] for p in prices], ["P-MSP-01"])  # Q28: SCUTUM only

    def test_bad_data_fails(self):
        cases = [
            dict(self.projects[0], status="Shipped"),
            dict(self.projects[0], division="nexus"),
            dict(self.projects[0], detail="gated text"),
            {k: v for k, v in self.projects[0].items() if k != "one_liner"},
        ]
        for bad in cases:
            with self.assertRaises(build.BuildError):
                build.check_projects([bad] + self.projects[1:], self.divisions)
        with self.assertRaises(build.BuildError):  # duplicate id
            build.check_projects(self.projects + [self.projects[0]], self.divisions)

    def test_placeholder_label_escaped_once(self):
        out = build.render_placeholders('<x-ph id="X" w="800" h="500">Tea &amp; towels</x-ph>', "t")
        self.assertIn("Tea &amp; towels", out)
        self.assertNotIn("&amp;amp;", out)


class LegalAndForms(unittest.TestCase):
    def test_markdown_subset(self):
        out = build.render_md("### 1. Title\n\nSome **bold** text\non two lines.\n\n- (a) one\n- (b) two:\n  - (i) nested\n  - (ii) more\n- (c) three\n", top=2)
        self.assertEqual(out, "\n".join([
            "<h2>1. Title</h2>", "<p>Some <strong>bold</strong> text on two lines.</p>",
            "<ul>", "<li>(a) one", "</li>", "<li>(b) two:", "<ul>", "<li>(i) nested", "</li>", "<li>(ii) more",
            "</li></ul>", "</li>", "<li>(c) three", "</li></ul>"]))
        self.assertIn("&lt;script&gt;", build.render_md("<script>x</script>"))

    def test_nda_fingerprint_is_the_file(self):
        import hashlib
        nda = build.load_nda()
        raw = (build.SRC / ("legal/nda-%s.md" % nda["version"])).read_bytes()
        self.assertEqual(nda["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertNotIn("Reviewer note", nda["text"])

    def test_forms_render_exactly_the_defined_fields(self):
        ctx = {"forms": build.load_json("forms.json"), "divisions": build.load_json("divisions.json")}
        for key, spec in ctx["forms"].items():
            if key.startswith("_"):
                continue
            out = build.render_form(key, ctx)
            names = re.findall(r'name="([^"]+)"', out)
            self.assertEqual(names, [f["name"] for f in spec["fields"]] + ["website"], key)
            for fid in re.findall(r'<(?:input|select|textarea)[^>]* id="([^"]+)"', out):
                self.assertIn('for="%s"' % fid, out, fid)
        enquiry = build.render_form("enquiry", ctx)
        self.assertIn('<option value="">Choose one</option><option value="home-help">', enquiry)
        self.assertIn('<option value="tempestas">TEMPESTAS (Storm &amp; Hardware)</option>', enquiry)

    def test_page_scripts(self):
        self.assertEqual(build.page_scripts({}, "t"), "")
        out = build.page_scripts({"scripts": "nda"}, "t")
        self.assertEqual(re.findall(r"js/(\w+)\.js", out), ["config", "forms", "nda"])
        with self.assertRaises(build.BuildError):
            build.page_scripts({"scripts": "evil"}, "t")


class Phase3b(unittest.TestCase):
    def setUp(self):
        self.resources = build.load_json("resources.json")
        self.guides = build.load_guides()[1]

    def test_repo_data_is_valid(self):
        build.check_resources(self.resources, self.guides)
        self.assertEqual(len(self.resources["entries"]), 15)
        self.assertEqual(len(self.guides), 20)  # 11 chapters + 9 manuals (Q57)
        build.check_credentials(build.load_json("credentials.json"))
        build.check_social(build.load_json("site.json"))

    def test_bad_data_fails(self):
        entry = self.resources["entries"][0]
        for bad in (dict(entry, download="https://bitwarden.example.net/download/"),
                    dict(entry, download="http://bitwarden.com/download/"),
                    dict(entry, guide="nope"), {k: v for k, v in entry.items() if k != "why"}):
            with self.assertRaises(build.BuildError):
                build.check_resources({"entries": [bad]}, self.guides)
        with self.assertRaises(build.BuildError):  # no unit details (Q53)
            build.check_credentials({"entries": [{"title": "Diploma", "units": ["ICTSAS"]}]})
        with self.assertRaises(build.BuildError):
            build.check_social({"social": [{"key": "x", "href": "http://x.example/"}]})
        project = build.load_json("projects.json")[0]
        for bad in (dict(project, link="https://elsewhere.example/"), dict(project, gated="no")):
            with self.assertRaises(build.BuildError):
                build.check_projects([bad], [{"slug": project["division"]}])

    def test_mercator_card_links_shop_without_lock(self):
        p = next(x for x in build.load_json("projects.json") if x["id"] == "P-MSP-07")
        self.assertEqual(p["division"], "msp")
        out = build.project_card(p)
        self.assertIn('href="/shop/"', out)
        self.assertNotIn('class="lock"', out)
        self.assertIn('class="lock"', build.project_card(dict(p, gated=True)))

    def test_social_links_skip_empty(self):
        site = {"social": [{"key": "a", "label": "A", "href": ""}, {"key": "b", "label": "B", "href": "https://b.example/"}]}
        out = build.c_footer_social({"site": site})
        self.assertIn('href="https://b.example/"', out)
        self.assertNotIn(">A<", out)
        self.assertEqual(build.c_footer_social({"site": {"social": [{"key": "a", "label": "A", "href": ""}]}}), "")
        hidden = {"social": [{"key": "g", "label": "G", "href": "https://g.example/", "hidden": True}]}
        self.assertEqual(build.c_footer_social({"site": hidden}), "")

    def test_social_row_phase3c(self):
        """Q54: five links in Chris's order, LinkedIn labelled as his, Google/TikTok hidden, no Reddit/Etsy."""
        site = build.load_json("site.json")
        out = build.c_footer_social({"site": site})
        hrefs = re.findall(r'href="([^"]+)"', out)
        self.assertEqual(hrefs, ["https://www.instagram.com/it7q_qld/", "https://x.com/it7qqld",
                                 "https://www.youtube.com/@IT7Q-KITS",
                                 "https://www.linkedin.com/in/chris-lord-b53731102/",
                                 "https://www.facebook.com/InfiniteQld"])
        self.assertIn("Chris&#x27;s LinkedIn", out)
        self.assertNotIn("Google", out)
        self.assertNotIn("TikTok", out)
        for key in ("google", "tiktok"):
            self.assertTrue(next(s for s in site["social"] if s["key"] == key).get("hidden"))
        for bad in ({"key": "reddit", "href": ""}, {"key": "shop", "href": "https://www.etsy.com/shop/x"}):
            with self.assertRaises(build.BuildError):
                build.check_social({"social": [bad]})

    def test_about_paragraph_stands_alone(self):
        """Q61: the overlapping lines are gone, Chris's paragraph and the Credentials link stay."""
        text = (build.SRC / "pages/about/index.html").read_text(encoding="utf-8")
        self.assertNotIn("started in 2020 in Kallangur", text)
        self.assertNotIn("seven divisions under one roof", text)
        self.assertIn("IT7Q was founded in 2020 by Chris Lord", text)
        self.assertIn('href="/credentials/"', text)

    def test_guide_without_files_is_a_placeholder(self):
        g = dict(self.guides["harden-windows"], md=False, pdf=False)
        self.assertIn("Coming soon", build.c_guide_actions({"g": g}))
        self.assertIn("PLACEHOLDER", build.c_guide_body({"g": g}))
        out = build.c_guide_actions({"g": dict(g, pdf=True)})
        self.assertIn('href="/resources/guides/pdf/harden-windows.pdf" download', out)


if __name__ == "__main__":
    unittest.main()
