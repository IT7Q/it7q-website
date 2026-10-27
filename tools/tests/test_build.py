"""Build-side rules: testimonials, project data validation, placeholders."""
import json
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


if __name__ == "__main__":
    unittest.main()
