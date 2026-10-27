#!/usr/bin/env python3
"""Local preview with mock webhooks (PLAN.md §4.12, §7.1). Listens on 127.0.0.1 only.

    .venv/bin/python tools/preview.py [--port 8080] [--scenario normal] [--no-build]

Runs `tools/build.py --mock` (unless --no-build), serves dist/ with the same
security headers as Cloudflare Pages, and answers POST /webhook/<hook> the way
the real n8n workflows must (Phase 4): same fields, same checks, same replies,
including failures. Change the scenario while it runs by opening
    http://127.0.0.1:<port>/__mock/scenario/<name>
and see them all at /__mock.

Mock logins (fake data, mock only; password for all three: mock-password-123):
    approved@example.test   all seven divisions
    investor@example.test   all seven divisions + the investor area
    pending@example.test    signed but not approved yet (login refused)
"""
import datetime
import json
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAX_BODY = 8192
MIN_ELAPSED_MS = 3000
SESSION_ABSOLUTE = 8 * 3600
SESSION_IDLE = 3600
LOCKOUT_FAILS, LOCKOUT_WINDOW = 5, 15 * 60
MOCK_PASSWORD = "mock-password-123"
SYSTEM_FIELDS = {"turnstile", "website", "elapsed_ms"}
SCENARIOS = {
    "normal": "everything works",
    "down": "every webhook returns 503 (server down)",
    "slow": "every webhook waits 20 s; the site gives up after 15 s",
    "rate-limited": "every webhook returns 429",
    "content-500": "nda-content returns 500",
    "content-bad-json": "nda-content returns 200 with a broken body",
    "content-wrong-division": "nda-content returns 200 for a different division",
    "session-expired": "nda-content returns 401",
    "forbidden": "nda-content returns 403",
    "login-refused": "nda-login always returns 401",
}
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Mock:
    """In-memory stand-in for the n8n workflows and their Postgres tables."""

    def __init__(self, scenario="normal"):
        self.scenario = scenario
        self.lock = threading.Lock()
        self.forms = build.load_json("forms.json")
        self.divisions = [d["slug"] for d in build.load_json("divisions.json")]
        self.projects = build.load_json("projects.json")
        self.nda = build.load_nda()
        self.users = {
            "approved@example.test": {"status": "approved", "investor": False},
            "investor@example.test": {"status": "approved", "investor": True},
            "pending@example.test": {"status": "pending", "investor": False},
        }
        self.sessions = {}
        self.fails = {}
        self.received = {"nda-submission": 0, "website-enquiry": 0, "dropped": 0}

    # -------------------------------------------------- validation (mirrors forms.json)

    def validate(self, key, body):
        spec = self.forms[key]
        fields = {f["name"]: f for f in spec["fields"]}
        allowed = set(fields) | SYSTEM_FIELDS | set(spec.get("system", []))
        if set(body) - allowed:
            return "unexpected field(s): %s" % ", ".join(sorted(set(body) - allowed))
        for name, f in fields.items():
            v = body.get(name)
            if f["type"] == "checkbox":
                if not isinstance(v, bool) or (f.get("required") and v is not True):
                    return "%s must be ticked" % name if f.get("required") else "%s must be true/false" % name
                continue
            if v is None:
                v = ""
            if not isinstance(v, str):
                return "%s must be text" % name
            if f.get("required") and not v.strip():
                return "%s is required" % name
            if len(v) > f.get("max", 10000):
                return "%s is too long" % name
            if f["type"] == "email" and v and not EMAIL.match(v):
                return "%s is not an email" % name
            if f["type"] == "select":
                options = {o["value"] for o in f.get("options", [])}
                if f.get("options_from") == "divisions":
                    options |= set(self.divisions)
                if v not in options:
                    return "%s is not one of the options" % name
            if f.get("match") and " ".join(v.split()).lower() != " ".join(str(body.get(f["match"], "")).split()).lower():
                return "%s must match %s" % (name, f["match"])
        if key == "nda_request" and (body.get("nda_version") != self.nda["version"]
                                     or body.get("nda_sha256") != self.nda["sha256"]):
            return "NDA version or fingerprint doesn't match"
        if body.get("turnstile") != "mock-token":
            return "Turnstile token rejected"
        return None

    def is_bot(self, body):
        elapsed = body.get("elapsed_ms")
        return bool(body.get("website")) or not isinstance(elapsed, (int, float)) or elapsed < MIN_ELAPSED_MS

    # -------------------------------------------------- hooks

    def handle(self, hook, body):
        """Return (status, reply_dict_or_raw_bytes)."""
        s = self.scenario
        if s == "slow":
            time.sleep(20)
        if s == "down":
            return 503, {"error": "unavailable"}
        if s == "rate-limited":
            return 429, {"error": "rate_limited"}
        if hook == "nda-submission":
            return self.submission("nda_request", body, "nda-submission")
        if hook == "website-enquiry":
            return self.submission("enquiry", body, "website-enquiry")
        if hook == "nda-login":
            return self.login(body)
        if hook == "nda-content":
            return self.content(body)
        return 404, {"error": "not_found"}

    def submission(self, key, body, hook):
        problem = self.validate(key, body)
        if problem:
            return 400, {"error": "invalid", "detail": problem}  # the real hooks won't send detail
        with self.lock:
            if self.is_bot(body):
                self.received["dropped"] += 1  # neutral reply, nothing stored
            else:
                self.received[hook] += 1
        return 202, {"ok": True}

    def login(self, body):
        problem = self.validate("nda_login", body)
        if problem:
            return 400, {"error": "invalid", "detail": problem}
        email = body["email"].strip().lower()
        now = time.time()
        with self.lock:
            fails = [t for t in self.fails.get(email, []) if now - t < LOCKOUT_WINDOW]
            self.fails[email] = fails
            if len(fails) >= LOCKOUT_FAILS:
                return 429, {"error": "rate_limited"}
            user = self.users.get(email)
            good = (self.scenario != "login-refused" and user and user["status"] == "approved"
                    and secrets.compare_digest(body["password"], MOCK_PASSWORD))
            if not good:
                fails.append(now)
                return 401, {"error": "login_failed"}  # one reply for every failure (§4.5)
            token = secrets.token_urlsafe(32)
            self.sessions[token] = {"email": email, "created": now, "last": now, "investor": user["investor"]}
        return 200, {"token": token, "email": email, "expires_at": iso(now + SESSION_ABSOLUTE),
                     "investor": user["investor"]}

    def session(self, token):
        now = time.time()
        with self.lock:
            sess = self.sessions.get(token) if isinstance(token, str) else None
            if not sess:
                return None
            if now - sess["created"] > SESSION_ABSOLUTE or now - sess["last"] > SESSION_IDLE:
                del self.sessions[token]
                return None
            sess["last"] = now
            return sess

    def content(self, body):
        if set(body) - {"token", "division", "action"}:
            return 400, {"error": "invalid"}
        sess = self.session(body.get("token"))
        if body.get("action") == "logout":
            with self.lock:
                self.sessions.pop(body.get("token"), None)
            return 200, {"ok": True}
        division = body.get("division")
        if division not in self.divisions and division != "investors":
            return 400, {"error": "invalid"}
        s = self.scenario
        if s == "session-expired" or not sess:
            return 401, {"error": "session"}
        if s == "forbidden" or (division == "investors" and not sess["investor"]):
            return 403, {"error": "scope"}
        if s == "content-500":
            return 500, {"error": "server"}
        if s == "content-bad-json":
            return 200, b'{"division": "' + division.encode() + b'", "projects": {'
        reply_division = "opus" if s == "content-wrong-division" and division != "opus" else division
        if division == "investors":
            return 200, {"division": reply_division, "viewer": sess["email"], "sections": [
                {"heading": "Sample investor section (mock)", "paragraphs": [
                    "MOCK DATA. Real investor material is written in Phase 4 and served only by the real workflow."]},
                {"heading": "Sample list", "items": ["First sample point", "Second sample point"]},
            ]}
        projects = {
            p["id"]: {
                "summary": "MOCK: sample confidential detail for %s. Real gated text comes from gated/ in Phase 4." % p["name"],
                "sections": [
                    {"heading": "Where it's at", "items": ["Sample milestone one", "Sample milestone two"]},
                    {"heading": "What's next", "paragraphs": ["A sample paragraph about the roadmap."]},
                ],
            }
            for p in self.projects if p["division"] == division
        }
        return 200, {"division": reply_division, "viewer": sess["email"], "projects": projects}


def pages_headers(dist):
    """Headers from dist/_headers' "/*" block, minus what breaks plain-http localhost."""
    headers, active = [], False
    path = dist / "_headers"
    if not path.exists():
        return headers
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            active = False
        elif not line.startswith(" "):
            active = line.strip() == "/*"
        elif active:
            name, _, value = line.strip().partition(":")
            if name == "Strict-Transport-Security":
                continue
            if name == "Content-Security-Policy":
                value = value.replace("; upgrade-insecure-requests", "")
            headers.append((name, value.strip()))
    return headers


def make_handler(dist, mock, quiet=False):
    extra = pages_headers(dist)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(dist), **kw)

        def end_headers(self):
            for name, value in extra:
                self.send_header(name, value)
            super().end_headers()

        def log_message(self, fmt, *args):
            if not quiet and "/webhook/" in self.path:
                sys.stderr.write("  %s\n" % (fmt % args))

        def reply(self, status, payload):
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def text(self, status, body):
            raw = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path.startswith("/__mock"):
                m = re.fullmatch(r"/__mock/scenario/([\w-]+)", path)
                if m:
                    if m.group(1) not in SCENARIOS:
                        return self.text(404, "unknown scenario\n")
                    mock.scenario = m.group(1)
                return self.text(200, "scenario: %s\n\n%s\n\nreceived: %s\n" % (
                    mock.scenario, "\n".join("  %-24s %s" % kv for kv in SCENARIOS.items()), mock.received))
            if path.startswith("/webhook/"):
                return self.reply(405, {"error": "method"})
            target = Path(self.translate_path(self.path))
            if not target.exists():
                body = (dist / "404.html").read_bytes()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def do_POST(self):
            m = re.fullmatch(r"/webhook/([\w-]+)", unquote(urlsplit(self.path).path))
            if not m:
                return self.reply(404, {"error": "not_found"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self.reply(413, {"error": "too_large"})
            if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                return self.reply(415, {"error": "json_only"})
            try:
                body = json.loads(self.rfile.read(length) or b"null")
            except ValueError:
                return self.reply(400, {"error": "invalid"})
            if not isinstance(body, dict):
                return self.reply(400, {"error": "invalid"})
            self.reply(*mock.handle(m.group(1), body))

    return Handler


def serve(dist, mock, port=0, quiet=False):
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(dist, mock, quiet))
    server.daemon_threads = True
    return server


def main(argv):
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8080
    scenario = argv[argv.index("--scenario") + 1] if "--scenario" in argv else "normal"
    if scenario not in SCENARIOS:
        print("unknown scenario %r; choose from: %s" % (scenario, ", ".join(SCENARIOS)), file=sys.stderr)
        return 2
    if "--no-build" not in argv:
        res = subprocess.run([sys.executable, str(ROOT / "tools/build.py"), "--mock"])
        if res.returncode:
            return res.returncode
    dist = ROOT / "dist"
    server = serve(dist, Mock(scenario), port)
    print("\nPreview with mock webhooks: http://127.0.0.1:%d/  (scenario: %s)" % (port, scenario))
    print("Scenarios: http://127.0.0.1:%d/__mock   Mock logins: see tools/preview.py   Ctrl+C stops it." % port)
    print("Rebuild without --mock before deploying anything: dist/ now holds a LOCAL MOCK build.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
