#!/usr/bin/env python3
"""Webhook contract test (PLAN.md §4.12, DEPLOY.md steps 9-10).

Checks that a webhook base answers the way the site expects. The same script tests the local
mock (tools/preview.py, run by tools/tests/test_contract.py) and, after deploy, the real n8n
workflows through Cloudflare:

    python3 tools/contract.py https://forms.it7q.com.au/webhook --email you@example.com
    python3 tools/contract.py https://forms.it7q.com.au/webhook --login you@example.com
    python3 tools/contract.py https://forms.it7q.com.au/webhook --prod

--email   also sends one real NDA request and one enquiry from that address (emails go out).
--login   logs in as an approved viewer (asks for the password) and checks every division,
          the investor area, logout, and that the token is dead afterwards.
--password-stdin   with --login: read the password from the first line of stdin (DEPLOY.md 9b).
--prod    the Turnstile test secret must be gone: Cloudflare's dummy token must be refused.
--turnstile TOKEN  token to send (default: Cloudflare's dummy token; the mock wants "mock-token").
--origin ORIGIN    send this Origin and require it back in Access-Control-Allow-Origin.

Uses the login lockout on purpose (5 wrong passwords for a made-up address), so the calling IP
collects 5 failed logins per run (the IP limit is 20 per 15 minutes).
"""
import getpass
import json
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

DUMMY_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"
DIVISIONS = [d["slug"] for d in build.load_json("divisions.json")]


class Client:
    def __init__(self, base, origin=None, timeout=20):
        self.base, self.origin, self.timeout = base.rstrip("/"), origin, timeout

    def post(self, hook, body, content_type="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        req = urllib.request.Request(self.base + "/" + hook, data=raw, method="POST",
                                     headers={"Content-Type": content_type, "User-Agent": "it7q-contract-test"})
        if self.origin:
            req.add_header("Origin", self.origin)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                status, headers, data = res.status, res.headers, res.read()
        except urllib.error.HTTPError as e:
            with e:
                status, headers, data = e.code, e.headers, e.read()
        try:
            parsed = json.loads(data or b"null")
        except ValueError:
            parsed = None
        return status, headers, parsed


class Contract:
    def __init__(self, client, turnstile=DUMMY_TOKEN, out=print):
        self.c, self.turnstile, self.out = client, turnstile, out
        self.failures = []
        nda = build.load_nda()
        self.nda = {"nda_version": nda["version"], "nda_sha256": nda["sha256"]}

    def expect(self, label, hook, body, statuses, check=None, content_type="application/json"):
        status, headers, data = self.c.post(hook, body, content_type)
        problems = []
        if status not in statuses:
            problems.append("status %s, wanted %s" % (status, "/".join(map(str, statuses))))
        if "no-store" not in (headers.get("Cache-Control") or ""):
            problems.append("no Cache-Control: no-store")
        if self.c.origin and headers.get("Access-Control-Allow-Origin") != self.c.origin:
            problems.append("Access-Control-Allow-Origin is %r" % headers.get("Access-Control-Allow-Origin"))
        if check and not problems:
            msg = check(data)
            if msg:
                problems.append(msg)
        self.out("%s  %s: %s" % ("FAIL" if problems else "ok  ", hook, label)
                 + ("  (%s)" % "; ".join(problems) if problems else ""))
        if problems:
            self.failures.append("%s: %s: %s" % (hook, label, "; ".join(problems)))
        return data

    # ------------------------------------------------------------------ payloads

    def system(self, **kw):
        return dict({"turnstile": self.turnstile, "website": "", "elapsed_ms": 5000}, **kw)

    def nda_body(self, email, **kw):
        body = dict(name="Contract Test", email=email, org="IT7Q", reason="Deploy check (tools/contract.py).",
                    wants_investor=False, signature="contract  test", agree_nda=True, agree_terms=True,
                    **self.nda)
        body.update(self.system())
        body.update(kw)
        return body

    def enquiry_body(self, email, **kw):
        body = dict(name="Contract Test", email=email, phone="", service="other", division="",
                    message="Deploy check from tools/contract.py. Please ignore.")
        body.update(self.system())
        body.update(kw)
        return body

    # ------------------------------------------------------------------ checks

    def envelopes(self):
        for hook in ("nda-submission", "website-enquiry", "nda-login", "nda-content"):
            self.expect("not JSON is refused", hook, b"name=x", (415,), content_type="text/plain")
            self.expect("over 8 KB is refused", hook, {"pad": "x" * 9000}, (413,))
            self.expect("a JSON array is refused", hook, [], (400,))

    def forms(self, email=None):
        probe = "contract-%s@example.invalid" % secrets.token_hex(4)
        for hook, make in (("nda-submission", self.nda_body), ("website-enquiry", self.enquiry_body)):
            self.expect("empty body is refused", hook, {}, (400,))
            self.expect("unknown field is refused", hook, make(probe, extra="x"), (400,))
            self.expect("bad Turnstile token is refused", hook, make(probe, turnstile="not-a-real-token"), (400,))
            self.expect("honeypot gets a neutral 202", hook, make(probe, website="http://spam.example"), (202,))
            self.expect("too fast gets a neutral 202", hook, make(probe, elapsed_ms=400), (202,))
        self.expect("signature must match the name", "nda-submission",
                    self.nda_body(probe, signature="Someone Else"), (400,))
        self.expect("wrong NDA fingerprint is refused", "nda-submission",
                    self.nda_body(probe, nda_sha256="0" * 64), (400,))
        self.expect("unknown service is refused", "website-enquiry", self.enquiry_body(probe, service="nope"), (400,))
        if email:
            self.expect("real NDA request is accepted (check both emails)", "nda-submission",
                        self.nda_body(email), (202,))
            self.expect("same request again gets the same 202 (no email)", "nda-submission",
                        self.nda_body(email), (202, 429))
            self.expect("real enquiry is accepted (check Chris's inbox)", "website-enquiry",
                        self.enquiry_body(email), (202,))

    def prod(self):
        probe = "contract-%s@example.invalid" % secrets.token_hex(4)
        self.expect("Turnstile dummy token is refused (test secret removed)", "website-enquiry",
                    self.enquiry_body(probe, turnstile=DUMMY_TOKEN), (400,))

    def login_lockout(self):
        probe = "contract-%s@example.invalid" % secrets.token_hex(4)
        body = self.system(email=probe, password="wrong-password-%s" % secrets.token_hex(4))
        self.expect("missing password is refused", "nda-login", self.system(email=probe), (400,))
        for i in range(5):
            self.expect("wrong login %d of 5 gets one generic 401" % (i + 1), "nda-login", body, (401,),
                        lambda d: None if d == {"error": "login_failed"} else "body %r" % (d,))
        self.expect("6th try is locked out", "nda-login", body, (429,))

    def content_without_login(self):
        self.expect("made-up token gets 401", "nda-content", {"token": secrets.token_urlsafe(32), "division": "msp"},
                    (401,))
        self.expect("no token gets 401", "nda-content", {"division": "opus"}, (401,))
        self.expect("unknown division is refused", "nda-content", {"token": "x" * 43, "division": "nope"}, (400,))
        self.expect("unknown field is refused", "nda-content", {"token": "x" * 43, "division": "msp", "x": 1}, (400,))
        self.expect("logout without a session still says ok", "nda-content", {"action": "logout"}, (200,))

    def logged_in(self, email, password):
        def login_ok(d):
            if not isinstance(d, dict) or not isinstance(d.get("token"), str) or len(d["token"]) < 20:
                return "no token"
            if d.get("email") != email.lower() or not isinstance(d.get("investor"), bool):
                return "email/investor wrong: %r" % ({k: v for k, v in d.items() if k != "token"},)
            if not str(d.get("expires_at", "")).endswith("Z"):
                return "expires_at not ISO UTC: %r" % d.get("expires_at")
            return None
        d = self.expect("approved login works", "nda-login", self.system(email=email, password=password), (200,),
                        login_ok)
        if not isinstance(d, dict) or "token" not in d:
            return
        token = d["token"]
        for div in DIVISIONS:
            self.expect("division %s unlocks" % div, "nda-content", {"token": token, "division": div}, (200,),
                        lambda r, div=div: None if isinstance(r, dict) and r.get("division") == div
                        and isinstance(r.get("projects"), dict) and r.get("viewer") == email.lower()
                        else "reply shape %r" % (str(r)[:80],))
        if d["investor"]:
            self.expect("investor area unlocks", "nda-content", {"token": token, "division": "investors"}, (200,),
                        lambda r: None if isinstance(r, dict) and isinstance(r.get("sections"), list) else "no sections")
        else:
            self.expect("investor area stays locked (403)", "nda-content", {"token": token, "division": "investors"},
                        (403,))
        self.expect("logout", "nda-content", {"token": token, "action": "logout"}, (200,))
        self.expect("token is dead after logout", "nda-content", {"token": token, "division": "msp"}, (401,))

    def run(self, email=None, login=None, prod=False):
        self.envelopes()
        self.forms(email)
        if prod:
            self.prod()
        self.content_without_login()
        self.login_lockout()
        if login:
            self.logged_in(*login)
        self.out("\n%s: %d problem(s)" % ("FAILED" if self.failures else "PASSED", len(self.failures)))
        return self.failures


def arg(argv, name):
    return argv[argv.index(name) + 1] if name in argv else None


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    turnstile = arg(argv, "--turnstile") or DUMMY_TOKEN
    login = None
    if arg(argv, "--login"):
        who = arg(argv, "--login")
        if "--password-stdin" in argv:  # run through sudo -u claude, where getpass can't reach the terminal
            login = (who, sys.stdin.readline().rstrip("\r\n"))
        else:
            login = (who, getpass.getpass("Password for %s: " % who))
    contract = Contract(Client(argv[0], origin=arg(argv, "--origin")), turnstile)
    return 1 if contract.run(email=arg(argv, "--email"), login=login, prod="--prod" in argv) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
