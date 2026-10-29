"""tools/contract.py passes against the mock, and can fail (PLAN.md §4.12, DEPLOY.md step 9)."""
import contextlib
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
