"""The local mock webhooks behave like the real ones must (PLAN.md §4.12), and the preview server is safe."""
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build  # noqa: E402
import preview  # noqa: E402

NDA = build.load_nda()


class MockHooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / "index.html").write_text("<p>home</p>", encoding="utf-8")
        (cls.tmp / "404.html").write_text("<p>not found</p>", encoding="utf-8")
        shutil.copyfile(build.SRC / "_headers", cls.tmp / "_headers")
        cls.mock = preview.Mock()
        cls.server = preview.serve(cls.tmp, cls.mock, 0, quiet=True)
        cls.base = "http://127.0.0.1:%d" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp)

    def setUp(self):
        self.mock.scenario = "normal"
        self.mock.fails.clear()

    def call(self, path, body=None, raw=None, ctype="application/json"):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method="POST" if data is not None else "GET")
        if data is not None:
            req.add_header("Content-Type", ctype)
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read(), dict(e.headers)

    def js(self, path, body):
        status, raw, _ = self.call(path, body)
        return status, json.loads(raw)

    def enquiry(self, **kw):
        body = {"name": "Test Person", "email": "test@example.test", "phone": "", "service": "website",
                "division": "", "message": "Hello", "turnstile": "mock-token", "website": "", "elapsed_ms": 5000}
        body.update(kw)
        return body

    def request(self, **kw):
        body = {"name": "Test Person", "email": "test@example.test", "org": "", "reason": "Partnering",
                "wants_investor": False, "signature": "test  person", "agree_nda": True, "agree_terms": True,
                "nda_version": NDA["version"], "nda_sha256": NDA["sha256"],
                "turnstile": "mock-token", "website": "", "elapsed_ms": 9000}
        body.update(kw)
        return body

    def login(self, email="approved@example.test", password=preview.MOCK_PASSWORD):
        return self.js("/webhook/nda-login", {"email": email, "password": password, "turnstile": "mock-token",
                                              "website": "", "elapsed_ms": 4000})

    def test_enquiry(self):
        before = self.mock.received["website-enquiry"]
        self.assertEqual(self.js("/webhook/website-enquiry", self.enquiry())[0], 202)
        self.assertEqual(self.mock.received["website-enquiry"], before + 1)
        for bad in (self.enquiry(message=""), self.enquiry(service="nope"), self.enquiry(division="nexus"),
                    self.enquiry(email="not-an-email"), self.enquiry(extra="x"), self.enquiry(turnstile="forged"),
                    self.enquiry(message="x" * 2001)):
            self.assertEqual(self.js("/webhook/website-enquiry", bad)[0], 400, bad)
        self.assertEqual(self.js("/webhook/website-enquiry", self.enquiry(division="tempestas"))[0], 202)

    def test_bots_get_a_neutral_reply_and_nothing_is_kept(self):
        before = dict(self.mock.received)
        self.assertEqual(self.js("/webhook/website-enquiry", self.enquiry(website="spam.example"))[0], 202)
        self.assertEqual(self.js("/webhook/website-enquiry", self.enquiry(elapsed_ms=800))[0], 202)
        self.assertEqual(self.mock.received["website-enquiry"], before["website-enquiry"])
        self.assertEqual(self.mock.received["dropped"], before["dropped"] + 2)

    def test_transport_limits(self):
        self.assertEqual(self.call("/webhook/website-enquiry", raw=b"x" * 9000)[0], 413)
        self.assertEqual(self.call("/webhook/website-enquiry", raw=b"{}", ctype="text/plain")[0], 415)
        self.assertEqual(self.call("/webhook/website-enquiry", raw=b"{not json")[0], 400)
        self.assertEqual(self.call("/webhook/nope", {})[0], 404)

    def test_nda_request(self):
        self.assertEqual(self.js("/webhook/nda-submission", self.request())[0], 202)
        for bad in (self.request(nda_sha256="0" * 64), self.request(signature="Someone Else"),
                    self.request(agree_nda=False), self.request(agree_terms="yes")):
            self.assertEqual(self.js("/webhook/nda-submission", bad)[0], 400, bad)

    def test_login_and_content(self):
        self.assertEqual(self.login("pending@example.test")[0], 401)
        self.assertEqual(self.login(password="wrong")[0], 401)
        status, d = self.login()
        self.assertEqual(status, 200)
        self.assertRegex(d["expires_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertFalse(d["investor"])
        status, c = self.js("/webhook/nda-content", {"token": d["token"], "division": "msp"})
        self.assertEqual(status, 200)
        msp = {p["id"] for p in build.load_json("projects.json") if p["division"] == "msp"}
        self.assertEqual(set(c["projects"]), msp)
        self.assertEqual(self.js("/webhook/nda-content", {"token": d["token"], "division": "investors"})[0], 403)
        self.assertEqual(self.js("/webhook/nda-content", {"token": "forged", "division": "msp"})[0], 401)
        self.assertEqual(self.js("/webhook/nda-content", {"token": d["token"], "division": "nexus"})[0], 400)
        self.assertEqual(self.js("/webhook/nda-content", {"token": d["token"], "action": "logout"})[0], 200)
        self.assertEqual(self.js("/webhook/nda-content", {"token": d["token"], "division": "msp"})[0], 401)

    def test_investor(self):
        status, d = self.login("investor@example.test")
        status, c = self.js("/webhook/nda-content", {"token": d["token"], "division": "investors"})
        self.assertEqual((status, c["division"]), (200, "investors"))
        self.assertTrue(c["sections"])

    def test_lockout(self):
        for _ in range(preview.LOCKOUT_FAILS):
            self.assertEqual(self.login(password="wrong")[0], 401)
        self.assertEqual(self.login()[0], 429)  # even the right password, until the window passes

    def test_scenarios(self):
        token = self.login()[1]["token"]
        self.assertEqual(self.call("/__mock/scenario/down")[0], 200)
        self.assertEqual(self.mock.scenario, "down")
        self.assertEqual(self.js("/webhook/website-enquiry", self.enquiry())[0], 503)
        self.mock.scenario = "content-bad-json"
        status, raw, _ = self.call("/webhook/nda-content", {"token": token, "division": "msp"})
        self.assertEqual(status, 200)
        with self.assertRaises(ValueError):
            json.loads(raw)
        self.mock.scenario = "content-wrong-division"
        self.assertEqual(self.js("/webhook/nda-content", {"token": token, "division": "msp"})[1]["division"], "opus")
        self.assertEqual(self.call("/__mock/scenario/made-up")[0], 404)

    def test_static_headers_and_404(self):
        status, _, headers = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertNotIn("upgrade-insecure-requests", headers["Content-Security-Policy"])
        self.assertNotIn("Strict-Transport-Security", headers)
        status, body, _ = self.call("/nowhere/")
        self.assertEqual((status, body), (404, b"<p>not found</p>"))

    def test_bound_to_localhost(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
