"""Phase 4 static checks: n8n workflows, their JavaScript and the SQL (PLAN.md §4).

There's no JS runtime or Postgres on Pantheon, so these check structure and wiring; the
behaviour is checked against the real thing by tools/contract.py at deploy (DEPLOY.md)."""
import base64
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build  # noqa: E402
import n8n_build  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
SQL = {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "deploy/sql").glob("*.sql"))}
PUBLIC_HOOKS = {"nda-submission", "nda-login", "nda-content", "website-enquiry"}


class Workflows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = n8n_build.load_config()
        cls.wf = n8n_build.workflows(cls.cfg)

    def nodes(self, name):
        return {n["name"]: n for n in self.wf[name]["nodes"]}

    def edges(self, name):
        for src, outs in self.wf[name]["connections"].items():
            for i, targets in enumerate(outs["main"]):
                for t in targets:
                    yield src, i, t["node"]

    def test_committed_files_are_up_to_date(self):
        self.assertEqual(n8n_build.main(["--check"]), 0, "run python3 tools/n8n_build.py")

    def test_all_hooks_present(self):
        self.assertEqual(set(self.wf), PUBLIC_HOOKS | {"nda-review", "nda-retention"})
        forms = build.load_json("forms.json")
        self.assertTrue({f["hook"] for f in forms.values() if isinstance(f, dict) and "hook" in f} <= PUBLIC_HOOKS)

    def test_wiring(self):
        for name in self.wf:
            nodes = self.nodes(name)
            self.assertEqual(len(nodes), len(self.wf[name]["nodes"]), "%s: duplicate node names" % name)
            edges = list(self.edges(name))
            incoming = {dst for _, _, dst in edges}
            for src, _, dst in edges:
                self.assertIn(src, nodes, name)
                self.assertIn(dst, nodes, name)
            for n in nodes.values():
                kind = n["type"].split(".")[-1]
                if kind in ("webhook", "scheduleTrigger"):
                    self.assertNotIn(n["name"], incoming, "%s: trigger with an input" % name)
                    continue
                self.assertIn(n["name"], incoming, "%s: %s is never reached" % (name, n["name"]))
                outs = {i for src, i, _ in edges if src == n["name"]}
                if kind == "if":
                    self.assertEqual(outs, {0, 1}, "%s: %s needs both branches wired" % (name, n["name"]))
                elif kind == "respondToWebhook":
                    self.assertEqual(outs, set(), name)
                elif name != "nda-retention":
                    self.assertTrue(outs, "%s: %s is a dead end without a reply" % (name, n["name"]))

    def test_node_references_exist(self):
        for name in self.wf:
            nodes = self.nodes(name)
            text = json.dumps(self.wf[name])
            for ref in set(re.findall(r"\$\('([^']+)'\)", text)):
                self.assertIn(ref, nodes, "%s refers to missing node %r" % (name, ref))

    def test_webhooks_need_the_edge_header_and_reply_via_node(self):
        origins = ",".join(self.cfg["site_origins"] + self.cfg["preview_origins"])
        paths = set()
        for name in self.wf:
            for n in self.nodes(name).values():
                if n["type"] != "n8n-nodes-base.webhook":
                    continue
                p = n["parameters"]
                paths.add((p["path"], p["httpMethod"]))
                self.assertEqual(p["authentication"], "headerAuth", n["name"])
                self.assertEqual(p["responseMode"], "responseNode", n["name"])
                self.assertEqual(n["credentials"]["httpHeaderAuth"]["name"], self.cfg["credentials"]["edge"])
                if p["path"] in PUBLIC_HOOKS:
                    self.assertEqual(p["options"]["allowedOrigins"], origins)
                else:
                    self.assertNotIn("allowedOrigins", p["options"])
        self.assertEqual(paths, {(h, "POST") for h in PUBLIC_HOOKS} | {("nda-review", "GET"), ("nda-review", "POST")})

    def test_credentials_by_name_only_and_no_secrets(self):
        allowed = set(self.cfg["credentials"].values())
        for name in self.wf:
            for n in self.wf[name]["nodes"]:
                for cred in n.get("credentials", {}).values():
                    self.assertEqual(set(cred), {"id", "name"})
                    self.assertIn(cred["name"], allowed)
            text = json.dumps(self.wf[name])
            for bad in (r"1x0{30,}AA", r"BEGIN [A-Z ]*PRIVATE KEY", r"\bsk-[A-Za-z0-9]{10,}", r"nubius",
                        r"\"password\"\s*:\s*\"[^\"]"):
                self.assertIsNone(re.search(bad, text), "%s: %s" % (name, bad))

    def test_no_secrets_in_execution_log(self):
        for name, wf in self.wf.items():
            s = wf["settings"]
            self.assertEqual(s["saveDataSuccessExecution"], "none", name)
            self.assertFalse(s["saveManualExecutions"], name)
            if name in ("nda-login", "nda-review"):
                self.assertEqual(s["saveDataErrorExecution"], "none", name)

    def test_replies_are_no_store(self):
        for name in self.wf:
            for n in self.nodes(name).values():
                if n["type"].endswith("respondToWebhook"):
                    headers = n["parameters"]["options"]["responseHeaders"]["entries"]
                    self.assertIn({"name": "Cache-Control", "value": "no-store"}, headers)
                    if n["parameters"]["respondWith"] == "text":
                        self.assertIn({"name": "Referrer-Policy", "value": "no-referrer"}, headers)

    def test_sql_calls_match_granted_functions(self):
        granted = set(re.search(r"GRANT EXECUTE ON FUNCTION(.*?)TO it7q_web", SQL["03-functions.sql"], re.S)
                      .group(1).replace("(jsonb)", "").replace(",", " ").split())
        for name in self.wf:
            for n in self.nodes(name).values():
                if n["type"].endswith("postgres"):
                    fn = re.fullmatch(r"SELECT web\.(\w+)\((?:\$1::jsonb|'\{\}'::jsonb)\) AS r", n["parameters"]["query"])
                    self.assertTrue(fn, n["parameters"]["query"])
                    self.assertIn(fn.group(1), granted)

    def test_javascript_guards(self):
        common = (ROOT / "n8n/code/common.js").read_text(encoding="utf-8")
        self.assertIn("crypto.timingSafeEqual", common)
        self.assertIn("crypto.randomBytes(32)", common)
        for path in (ROOT / "n8n/code").rglob("*.js"):
            text = path.read_text(encoding="utf-8")
            for bad in (r"\beval\s*\(", r"new Function", r"innerHTML", r"console\.log", r"Math\.random"):
                self.assertIsNone(re.search(bad, text), "%s: %s" % (path.name, bad))
        for name in self.wf:
            for n in self.nodes(name).values():
                if n["type"].endswith(".code"):
                    js = n["parameters"]["jsCode"]
                    self.assertNotIn("__CONFIG__", js)
                    self.assertNotIn("__NDA_HTML__", js)
                    self.assertEqual(js.count("{"), js.count("}"), "%s/%s: unbalanced braces" % (name, n["name"]))
                    self.assertEqual(js.count("("), js.count(")"), "%s/%s: unbalanced brackets" % (name, n["name"]))

    def test_config_matches_the_site(self):
        js = n8n_build.js_config(self.cfg)
        forms = build.load_json("forms.json")
        for key in ("nda_request", "nda_login", "enquiry"):
            self.assertEqual([f["name"] for f in js["forms"][key]["fields"]], [f["name"] for f in forms[key]["fields"]])
        self.assertEqual(js["nda"]["sha256"], build.load_nda()["sha256"])
        self.assertEqual(js["turnstile_hostnames"], ["it7q.com.au", "www.it7q.com.au"])
        self.assertEqual(js["hook_origin"], "https://forms.it7q.com.au")
        division = next(f for f in js["forms"]["enquiry"]["fields"] if f["name"] == "division")
        self.assertIn("fabricus", division["options"])

    def test_node_versions_checked_against_n8n_2_40(self):
        # Checked against the n8n 2.40.7 source (DEPLOY.md, "Versions"). A new node or version
        # here means checking it again before Chris imports it.
        checked = {("webhook", 2), ("code", 2), ("if", 2), ("httpRequest", 4.2), ("postgres", 2.5),
                   ("emailSend", 2.1), ("respondToWebhook", 1.1), ("scheduleTrigger", 1.2)}
        for name in self.wf:
            for n in self.nodes(name).values():
                self.assertIn((n["type"].split(".")[-1], n["typeVersion"]), checked, "%s/%s" % (name, n["name"]))

    def test_review_page_policy_is_the_one_cloudflare_sets(self):
        # n8n 2.x overwrites the CSP with its sandbox; DEPLOY.md 6g puts this one back at the edge.
        csp = n8n_build.REVIEW_CSP
        self.assertIn("sandbox allow-forms allow-same-origin", csp)
        self.assertNotIn("allow-scripts", csp)
        for n in self.nodes("nda-review").values():
            if n["type"].endswith("respondToWebhook"):
                self.assertIn({"name": "Content-Security-Policy", "value": csp},
                              n["parameters"]["options"]["responseHeaders"]["entries"])
        doc = (ROOT / "deploy/DEPLOY.md").read_text(encoding="utf-8")
        self.assertIn("\n%s\n" % csp, doc)
        post = (ROOT / "n8n/code/nda-review/verify-post.js").read_text(encoding="utf-8")
        self.assertIn("origin === 'null'", post)  # refused, with a pointer to 6g

    def test_dummy_hash_is_well_formed(self):
        h = n8n_build.dummy_hash()
        check = re.search(r"password_hash ~ '(.*?)'\)", SQL["02-schema.sql"]).group(1).replace("\\$", r"\$")
        self.assertRegex(h, check)
        _, n, r, p, salt, key = h.split("$")
        again = hashlib.scrypt(b"it7q-dummy-password-never-issued", salt=base64.b64decode(salt), n=int(n), r=int(r),
                               p=int(p), dklen=32, maxmem=64 * 1024 * 1024)
        self.assertEqual(base64.b64encode(again).decode(), key)


class Sql(unittest.TestCase):
    def test_tables_from_the_plan(self):
        tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", SQL["02-schema.sql"]))
        self.assertEqual(tables, {"nda_requests", "nda_review_tokens", "nda_sessions", "nda_content", "nda_rate",
                                  "nda_audit", "enquiries"})

    def test_n8n_role_has_no_table_rights(self):
        for name, text in SQL.items():
            for grant in re.findall(r"GRANT\s+(.*?)\s+TO\s+it7q_web\b", text, re.S):
                self.assertRegex(grant, r"^(CONNECT ON DATABASE|USAGE ON SCHEMA|EXECUTE ON FUNCTION)", name)
        self.assertNotRegex(SQL["01-database.sql"], r"(?i)password\s+'")

    def test_definer_functions_are_pinned_and_granted(self):
        text = SQL["03-functions.sql"]
        definers = set(re.findall(r"CREATE OR REPLACE FUNCTION (\w+)\(p jsonb[^)]*\) RETURNS jsonb\s+"
                                  r"LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp", text))
        self.assertEqual(text.count("SECURITY DEFINER"), len(definers))
        granted = set(re.search(r"GRANT EXECUTE ON FUNCTION(.*?)TO it7q_web", text, re.S)
                      .group(1).replace("(jsonb)", "").replace(",", " ").split())
        self.assertEqual(definers, granted)
        self.assertEqual(len(granted), 9)
        for helper in re.findall(r"CREATE OR REPLACE FUNCTION (_\w+)", text):
            self.assertNotIn(helper, granted)

    def test_retention_periods(self):
        text = SQL["03-functions.sql"]
        self.assertIn("status IN ('approved', 'revoked') AND signed_at < now() - interval '5 years'", text)
        self.assertIn("status IN ('pending', 'rejected') AND created_at < now() - interval '12 months'", text)
        for table in ("nda_audit WHERE at", "enquiries WHERE at"):
            self.assertIn("DELETE FROM %s < now() - interval '12 months'" % table, text)
        self.assertIn("signed_at + interval '3 years'", text)
        self.assertIn("now() + interval '8 hours'", text)
        self.assertIn("last_seen_at < now() - interval '1 hour'", text)


class Gated(unittest.TestCase):
    def setUp(self):
        import gated_sql
        self.g = gated_sql

    def test_every_gated_project_has_detail(self):
        rows = self.g.load(require_reviewed=False)
        ids = {p for _, p, _, _ in rows}
        gated = {p["id"] for p in build.load_json("projects.json") if p.get("gated") is not False}
        self.assertEqual(ids - {"_page"}, gated)
        self.assertNotIn("P-MSP-07", ids)  # MERCATOR is public (gated: false)

    def test_unreviewed_files_are_never_loaded(self):
        files = [json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "gated").glob("*.json")]
        if not all(f.get("reviewed") is True for f in files):
            with self.assertRaisesRegex(self.g.GatedError, "not reviewed yet"):
                self.g.load()
            self.assertEqual(self.g.main([]), 1)

    def test_sql_drops_notes_and_quotes_safely(self):
        sql = self.g.to_sql(self.g.load(require_reviewed=False))
        self.assertNotIn("notes", sql)
        self.assertIn("IT7Q''s", sql)
        self.assertIn("SET LOCAL ROLE it7q_web_owner", sql)
        body = re.search(r"\('msp', 'P-MSP-01', 1, '(.*?)'::jsonb\)", sql).group(1).replace("''", "'")
        self.assertEqual(set(json.loads(body)), {"summary", "sections"})

    def test_bad_shapes_fail(self):
        good = {"summary": "x", "sections": [{"heading": "h", "items": ["a"]}]}
        self.g.body("t", good)
        for bad in ({"summary": "x"}, dict(good, extra=1), dict(good, sections=[{"heading": "h"}]),
                    dict(good, sections=[{"heading": "h", "items": [1]}]),
                    dict(good, sections=[{"heading": "h", "items": ["a"], "html": "<b>"}])):
            with self.assertRaises(self.g.GatedError):
                self.g.body("t", bad)


class Deploy(unittest.TestCase):
    def test_selftest_never_keeps_anything(self):
        text = SQL["90-selftest.sql"]
        self.assertIn("\nBEGIN;\n", text)
        self.assertTrue(text.rstrip().endswith("ROLLBACK;"))
        self.assertNotIn("COMMIT", text)
        self.assertIn("SET LOCAL ROLE it7q_web;", text)  # part 1 runs with n8n's own rights

    def test_deploy_doc_names_every_credential_and_workflow(self):
        doc = (ROOT / "deploy/DEPLOY.md").read_text(encoding="utf-8")
        for name in n8n_build.load_config()["credentials"].values():
            self.assertIn("`%s`" % name, doc)
        for name in n8n_build.workflows():
            self.assertIn("`%s`" % name, doc)
        for path in SQL:
            self.assertIn(path, doc)
        counts = {}
        for div, _, _, _ in __import__("gated_sql").load(require_reviewed=False):
            counts[div] = counts.get(div, 0) + 1
        expected = ", ".join("%s %d" % kv for kv in sorted(counts.items()))
        self.assertTrue(expected in " ".join(doc.split()), "DEPLOY.md step 8 should list: " + expected)

    def test_deploy_doc_uses_pantheon_names_and_no_repo_access_for_chris(self):
        doc = (ROOT / "deploy/DEPLOY.md").read_text(encoding="utf-8")
        for placeholder in ("<postgres>", "<n8n>", "<pg-superuser>", "wget -", "python3 tools/"):
            self.assertNotIn(placeholder, doc)
        for path in SQL:
            self.assertIn("sudo cat /srv/work/it7q-website/deploy/sql/%s | sudo docker exec -i postgres psql -U it7q"
                          % path, doc)
        for script in ("n8n_build.py", "gated_sql.py", "contract.py"):
            self.assertIn("sudo -u claude /srv/work/it7q-website/.venv/bin/python /srv/work/it7q-website/tools/"
                          + script, doc)
        self.assertIn("rua=mailto:dmarc@it7q.com.au", doc)
        self.assertIn("x._domainkey", doc)
        self.assertIn("--password-stdin", doc)
