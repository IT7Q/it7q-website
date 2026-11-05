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
        specs = {"X": {"kind": "client", "name": "Tea & towels"}}
        out = build.render_placeholders('<x-ph id="X" w="800" h="500">Tea &amp; towels</x-ph>', "t", specs)
        self.assertIn("Tea &amp; towels", out)
        self.assertNotIn("&amp;amp;", out)


class Artwork(unittest.TestCase):
    """Image slots are on-brand artwork that keeps the image id for the real photo later."""

    @classmethod
    def setUpClass(cls):
        cls.specs = build.art_specs(build.load_json("projects.json"), build.load_json("portfolio.json"))

    def draw(self, pid, w=800, h=500):
        return build.render_placeholders('<x-ph id="%s" w="%d" h="%d">label</x-ph>' % (pid, w, h), "t", self.specs)

    def test_kinds(self):
        kinds = {pid: s["kind"] for pid, s in self.specs.items()}
        self.assertEqual({k for k, v in kinds.items() if v == "shield"},
                         {"P-TEM-01", "P-TEM-02", "P-TEM-03", "P-TEM-04", "P-TEM-05"})
        self.assertEqual(kinds["P-TEM-06"], "project")  # the carrier board isn't a tier
        self.assertEqual(kinds["P-FAB-001"], "soon")
        self.assertEqual(kinds["P-FAB-101"], "project")  # the FABRICUS App is software, not a photo
        self.assertEqual(kinds["IMG-19"], "client")
        self.assertNotIn("IMG-29", kinds)  # about and shop get brand artwork

    def test_id_and_ratio_kept(self):
        for pid, w, h, ratio in (("P-MSP-01", 800, 500, "16x10"), ("IMG-30", 1600, 900, "16x9"),
                                 ("IMG-29", 800, 800, "1x1")):
            out = self.draw(pid, w, h)
            self.assertIn('data-img="%s"' % pid, out)
            self.assertIn("ph--%s" % ratio, out)
            self.assertIn('role="img"', out)
            self.assertNotIn("PLACEHOLDER", out)

    def test_shield_has_one_chevron_per_tier_and_no_text(self):
        for n in range(1, 6):
            out = self.draw("P-TEM-0%d" % n)
            self.assertEqual(out.count('class="art__chev"'), n)
            self.assertNotIn("<text", out)
            self.assertIsNone(re.search(r"\$|\bGB\b|\bMHz\b|\bWi-?Fi\b", out, re.I))  # prices stay gated
            self.assertIn("d-tempestas", out)

    def test_clip_ids_unique_on_a_page(self):
        page = "".join('<x-ph id="P-TEM-0%d" w="800" h="500">x</x-ph>' % n for n in range(1, 6))
        ids = re.findall(r'clipPath id="([^"]+)"', build.render_placeholders(page, "t", self.specs))
        self.assertEqual(len(ids), len(set(ids)), ids)

    def test_project_art_is_division_badge_no_hex(self):
        out = self.draw("P-OPUS-01")
        self.assertIn("d-opus", out)
        self.assertIn('class="badge__t1"', out)
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,6}\b", out))  # colours come from CSS only

    def test_soon_and_client(self):
        self.assertIn("Photo coming soon", self.draw("P-FAB-010"))
        out = self.draw("IMG-21", 1600, 1000)
        self.assertIn('<span class="art__name">Pine Rivers RSL Sub Branch</span>', out)


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

    def test_credentials_hidden_until_the_list_is_in(self):
        self.assertEqual(build.c_credentials_link({"credentials": []}), "")
        self.assertEqual(build.c_credentials_about({"credentials": []}), "")
        entry = [{"title": "Diploma of IT"}]
        self.assertIn('href="/credentials/"', build.c_credentials_link({"credentials": entry}))
        self.assertIn('href="/credentials/"', build.c_credentials_about({"credentials": entry}))
        meta, _ = build.parse_page((build.SRC / "pages/credentials/index.html").read_text(encoding="utf-8"), "c")
        self.assertEqual(meta.get("needs"), "credentials")

    def test_published_portfolio_needs_a_one_liner(self):
        e = {"id": "px", "name": "X", "client": "current", "image": "IMG-1", "link": None, "published": True}
        with self.assertRaises(build.BuildError):
            build.portfolio_card(e)
        self.assertIn("<p>Launching soon.</p>", build.portfolio_card(dict(e, one_liner="Launching soon.")))

    def test_about_paragraph_stands_alone(self):
        """Q61: the overlapping lines are gone, Chris's paragraph and the Credentials link stay."""
        text = (build.SRC / "pages/about/index.html").read_text(encoding="utf-8")
        self.assertNotIn("started in 2020 in Kallangur", text)
        self.assertNotIn("seven divisions under one roof", text)
        self.assertIn("IT7Q was founded in 2020 by Chris Lord", text)
        self.assertIn("{{> credentials_about}}", text)  # the Credentials link, once the list is in

    def test_guide_without_files_is_a_coming_soon_card(self):
        g = dict(self.guides["harden-windows"], md=False, pdf=False)
        guides = dict(self.guides, **{"harden-windows": g})
        data = {"sections": [{"key": "m", "title": "Manuals", "intro": "i", "guides": [{"slug": "harden-windows"}]}]}
        card = build.c_guides({"guides_data": data, "guides": guides})
        self.assertIn("gcard--soon", card)
        self.assertIn("Coming soon", card)
        self.assertIn(g["title"], card)
        self.assertNotIn("href=", card)  # no page, no download until the file exists
        ready = build.c_guides({"guides_data": data, "guides": dict(guides, **{"harden-windows": dict(g, pdf=True)})})
        self.assertIn('href="/resources/guides/harden-windows/"', ready)
        res = {"entries": [{"name": "X", "what": "w", "why": "y", "download": "https://x.example/", "domain": "x.example",
                            "guide": "harden-windows"}]}
        self.assertNotIn("IT7Q guide", build.c_resources({"resources": res, "guides": guides}))
        out = build.c_guide_actions({"g": dict(g, pdf=True)})
        self.assertIn('href="/resources/guides/pdf/harden-windows.pdf" download', out)


if __name__ == "__main__":
    unittest.main()


class FormPayloads(unittest.TestCase):
    """No form may send a key the webhooks don't know (the live cf-turnstile-response bug, 400 invalid).

    There's no JS runtime on Pantheon, so this checks the code paths statically: what the built
    forms contain, what config.js allows, and every key forms.js or nda.js can put in a body."""

    @classmethod
    def setUpClass(cls):
        cls.forms = {k: v for k, v in build.load_json("forms.json").items() if not k.startswith("_")}
        cls.js = (build.SRC / "assets/js/forms.js").read_text(encoding="utf-8")
        cls.nda_js = (build.SRC / "assets/js/nda.js").read_text(encoding="utf-8")
        common = (build.ROOT / "n8n/code/common.js").read_text(encoding="utf-8")
        cls.server_system = json.loads(re.search(r"const SYSTEM_FIELDS = (\[.*?\]);", common).group(1).replace("'", '"'))

    def allowed(self, key):
        return {f["name"] for f in self.forms[key]["fields"]} | set(self.server_system) | set(
            self.forms[key].get("system", []))

    def test_config_lists_exactly_the_forms_json_fields(self):
        keys = build.form_keys()
        self.assertEqual(set(keys), set(self.forms))
        for k, v in keys.items():
            self.assertEqual(v["fields"], [f["name"] for f in self.forms[k]["fields"]])
            self.assertEqual(v["system"], self.forms[k].get("system", []))

    def test_rendered_forms_hold_only_known_inputs(self):
        ctx = {"forms": self.forms, "divisions": build.load_json("divisions.json"),
               "site": build.load_json("site.json"), "nda": build.load_nda()}
        for key in self.forms:
            out = build.render_form(key, ctx)
            names = set(re.findall(r'<(?:input|select|textarea)\b[^>]*\bname="([^"]+)"', out))
            self.assertEqual(names, {f["name"] for f in self.forms[key]["fields"]} | {"website"}, key)

    def test_forms_js_never_reads_the_whole_form(self):
        self.assertNotIn("FormData", self.js + self.nda_js)
        self.assertNotRegex(self.js, r'querySelectorAll\("input\[name\]')
        self.assertIn('"response-field": false', self.js)  # Turnstile adds no cf-turnstile-response input
        js_system = json.loads(re.search(r"var SYSTEM_FIELDS = (\[.*?\]);", self.js).group(1))
        self.assertEqual(set(js_system), set(self.server_system))
        # The allowlist is the last thing applied before posting.
        submit = self.js[self.js.index('form.addEventListener("submit"'):]
        self.assertLess(submit.index("body = pick(body, key);"), submit.index("post(hook, body)"))
        self.assertGreater(submit.index("body = pick(body, key);"), submit.index("h.extra(body)"))

    def test_every_key_the_scripts_set_is_allowed(self):
        set_here = set(re.findall(r"\bbody\.(\w+) =", self.js))
        self.assertTrue(set_here <= set(self.server_system), set_here)
        parts = re.split(r'F\.register\("(\w+)"', self.nda_js)  # [before, key1, block1, key2, block2, ...]
        self.assertEqual(sorted(parts[1::2]), ["nda_login", "nda_request"])
        for key, block in zip(parts[1::2], parts[2::2]):
            extra = set(re.findall(r"\bbody\.(\w+) =", block))
            self.assertTrue(extra <= self.allowed(key), (key, extra - self.allowed(key)))
