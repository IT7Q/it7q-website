"""tools/contract.py passes against the mock, and can fail (PLAN.md §4.12, DEPLOY.md step 9)."""
import contextlib
import http.server
import io
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build  # noqa: E402
import contract  # noqa: E402
import preview  # noqa: E402


class ContractAgainstMock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / "404.html").write_text("<p>not found</p>", encoding="utf-8")
        (cls.tmp / "_headers").write_text(build.headers_text(), encoding="utf-8")
        cls.mock = preview.Mock()
        cls.server = preview.serve(cls.tmp, cls.mock, 0, quiet=True)
        cls.base = "http://127.0.0.1:%d/webhook" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp)

    def setUp(self):
        self.mock.scenario = "normal"
        self.mock.fails.clear()
        self.lines = []

    def run_contract(self, **kw):
        c = contract.Contract(contract.Client(self.base), turnstile="mock-token", out=self.lines.append)
        return c.run(**kw)

    def test_full_run_passes(self):
        failures = self.run_contract(email="tester@example.test",
                                     login=("approved@example.test", preview.MOCK_PASSWORD))
        self.assertEqual(failures, [], "\n".join(self.lines))
        self.assertTrue(any("division fabricus unlocks" in line for line in self.lines))
        self.assertTrue(any("investor area stays locked" in line for line in self.lines))

    def test_investor_login(self):
        failures = self.run_contract(login=("investor@example.test", preview.MOCK_PASSWORD))
        self.assertEqual(failures, [], "\n".join(self.lines))
        self.assertTrue(any("investor area unlocks" in line for line in self.lines))

    def test_password_from_stdin(self):
        # DEPLOY.md 9b pipes the password in through sudo -u claude.
        out = io.StringIO()
        old = sys.stdin
        sys.stdin = io.StringIO(preview.MOCK_PASSWORD + "\n")
        try:
            with contextlib.redirect_stdout(out):
                code = contract.main([self.base, "--turnstile", "mock-token", "--login", "approved@example.test",
                                      "--password-stdin"])
        finally:
            sys.stdin = old
        self.assertEqual(code, 0, out.getvalue())

    def test_it_can_fail(self):
        self.mock.scenario = "down"
        self.assertTrue(self.run_contract())
        self.mock.scenario = "normal"
        failures = self.run_contract(login=("pending@example.test", preview.MOCK_PASSWORD))
        self.assertIn("nda-login: approved login works: status 401, wanted 200", failures)

    def test_prod_check_needs_the_dummy_token_refused(self):
        # The mock refuses anything but "mock-token", like the real secret refuses the dummy token.
        self.assertEqual(self.run_contract(prod=True), [], "\n".join(self.lines))


class Pacing(unittest.TestCase):
    """The live burst rule (DEPLOY.md 6e): pace real targets, retry a 429 once, keep the mock fast."""

    def test_default_pace(self):
        self.assertEqual(contract.Client("http://127.0.0.1:8000/webhook").pace, 0)
        self.assertEqual(contract.Client("http://localhost:8000/webhook").pace, 0)
        self.assertEqual(contract.Client("https://forms.it7q.com.au/webhook").pace, contract.LIVE_PACE)
        self.assertEqual(contract.Client("https://forms.it7q.com.au/webhook", pace=1.5).pace, 1.5)

    def serve(self, statuses, json_429=False):
        hits = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                hits.append(self.path)
                status = statuses.pop(0) if statuses else 200
                cloudflare = status == 429 and not json_429
                self.send_response(status)
                self.send_header("Content-Type", "text/html" if cloudflare else "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b"<p>error code: 1015</p>" if cloudflare else b'{"error": "rate_limited"}')

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:%d/webhook" % server.server_address[1], hits

    def client(self, base, pace):
        sleeps, notes = [], []
        c = contract.Client(base, pace=pace, sleep=sleeps.append, note=notes.append)
        return c, sleeps, notes

    def test_429_waits_and_retries_once(self):
        base, hits = self.serve([429])
        c, sleeps, notes = self.client(base, pace=0)
        status, _, _ = c.post("nda-login", {})
        self.assertEqual(status, 200)
        self.assertEqual(len(hits), 2)
        self.assertEqual(sleeps, [contract.RETRY_WAIT])
        self.assertEqual(c.retries, 1)
        self.assertIn("nda-login: 429 (rate limited), waiting 11 s and retrying once", notes[0])

    def test_second_429_is_reported_not_retried_again(self):
        base, hits = self.serve([429, 429])
        c, _, _ = self.client(base, pace=0)
        status, _, _ = c.post("nda-login", {})
        self.assertEqual(status, 429)
        self.assertEqual(len(hits), 2)

    def test_our_own_json_429_is_never_retried(self):
        base, hits = self.serve([429], json_429=True)  # login lockout: the answer the check wants
        c, sleeps, _ = self.client(base, pace=0)
        status, _, data = c.post("nda-login", {})
        self.assertEqual((status, data), (429, {"error": "rate_limited"}))
        self.assertEqual((len(hits), sleeps, c.retries), (1, [], 0))

    def test_requests_are_spaced(self):
        base, hits = self.serve([])
        c, sleeps, _ = self.client(base, pace=0.6)
        for _ in range(3):
            c.post("nda-content", {})
        self.assertEqual(len(hits), 3)
        self.assertEqual(len(sleeps), 2)  # none before the first request
        self.assertTrue(all(0 < w <= 0.6 for w in sleeps), sleeps)
