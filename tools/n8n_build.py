#!/usr/bin/env python3
"""Build the n8n workflow files (PLAN.md §4, Phase 4).

    python3 tools/n8n_build.py           # writes n8n/workflows/*.json
    python3 tools/n8n_build.py --check   # exits 1 if the committed files are out of date

The JavaScript lives in n8n/code/ as plain files so it can be reviewed; this script pastes
n8n/code/common.js (with CFG filled in from deploy/config.json, src/data/forms.json and the
NDA) above each step and wires the nodes together. The output is what Chris imports into n8n
(DEPLOY.md step 7). Credentials are referenced by name only; n8n links them on import.
Node versions are checked against n8n 2.40.7 (DEPLOY.md, "Versions").
"""
import base64
import hashlib
import json
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "n8n/code"
OUT = ROOT / "n8n/workflows"
CONFIG = ROOT / "deploy/config.json"
NS = uuid.UUID("6f1c2b8e-58a4-4b7e-9a51-1f0c7d3e2a10")  # stable ids, so rebuilds don't churn

TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
NO_STORE = {"name": "Cache-Control", "value": "no-store"}
# n8n 2.x replaces any CSP on a webhook reply with its own `sandbox` policy (no allow-same-origin),
# so the review form would post with Origin: null and be refused. Cloudflare sets this policy on
# the way out instead (DEPLOY.md step 6g); n8n sends it too, for when its sandbox is off.
REVIEW_CSP = ("default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; "
              "base-uri 'none'; sandbox allow-forms allow-same-origin")
PAGE_HEADERS = [
    {"name": "Content-Type", "value": "text/html; charset=utf-8"},
    NO_STORE,
    {"name": "Content-Security-Policy", "value": REVIEW_CSP},
    {"name": "X-Frame-Options", "value": "DENY"},
    {"name": "Referrer-Policy", "value": "no-referrer"},  # the review link carries its token
    {"name": "X-Content-Type-Options", "value": "nosniff"},
    {"name": "X-Robots-Tag", "value": "noindex"},
]


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def dummy_hash():
    """A fixed, well-formed scrypt hash that matches no password anyone is given (§4.5)."""
    salt = hashlib.sha256(b"it7q-dummy-salt").digest()[:16]
    key = hashlib.scrypt(b"it7q-dummy-password-never-issued", salt=salt, n=16384, r=8, p=1, dklen=32,
                         maxmem=64 * 1024 * 1024)
    return "scrypt$16384$8$1$%s$%s" % (base64.b64encode(salt).decode(), base64.b64encode(key).decode())


def js_config(cfg):
    """CFG for the Code nodes: public values only."""
    forms = build.load_json("forms.json")
    divisions = [d["slug"] for d in build.load_json("divisions.json")]
    nda = build.load_nda()
    lean, labels = {}, {}
    for key in ("nda_request", "nda_login", "enquiry"):
        fields = []
        for f in forms[key]["fields"]:
            g = {k: f[k] for k in ("name", "type", "required", "max", "match") if k in f}
            if f["type"] == "select":
                opts = [o["value"] for o in f.get("options", [])]
                names = {o["value"]: o["label"] for o in f.get("options", [])}
                if f.get("options_from") == "divisions":
                    opts += divisions
                    names.update({d["slug"]: d["latin"] for d in build.load_json("divisions.json")})
                g["options"] = opts
                labels[f["name"]] = names
            fields.append(g)
        lean[key] = {"turnstile_action": forms[key]["turnstile_action"], "fields": fields,
                     "system": forms[key].get("system", [])}
    origins = cfg["site_origins"] + cfg["preview_origins"]
    return {
        "hook_base": cfg["hook_base"],
        "hook_origin": "{0.scheme}://{0.netloc}".format(urlsplit(cfg["hook_base"])),
        "site_base": cfg["site_base"],
        "turnstile_hostnames": [urlsplit(o).hostname for o in origins],
        "mail": cfg["mail"],
        "access": cfg["access"],
        "divisions": divisions,
        "forms": lean,
        "labels": labels,
        "nda": {"version": nda["version"], "sha256": nda["sha256"]},
        "max_body": 8192,
        "min_elapsed_ms": 3000,
        "dummy_hash": dummy_hash(),
    }


class Workflow:
    def __init__(self, name, cfg, jscfg, libs=()):
        self.name, self.cfg, self.jscfg, self.libs = name, cfg, jscfg, libs
        self.nodes, self.edges = [], []

    def _id(self, node):
        return str(uuid.uuid5(NS, "%s/%s" % (self.name, node)))

    def add(self, name, type_, version, params, pos, creds=None, **extra):
        node = {"parameters": params, "id": self._id(name), "name": name, "type": "n8n-nodes-base." + type_,
                "typeVersion": version, "position": [pos[0] * 220, pos[1] * 160]}
        if creds:
            node["credentials"] = creds
        node.update(extra)
        self.nodes.append(node)
        return name

    def link(self, src, dst, out=0):
        self.edges.append((src, out, dst))

    def chain(self, *names):
        for a, b in zip(names, names[1:]):
            self.link(a, b)

    # ---------------------------------------------------------------- node kinds

    def cred(self, kind):
        types = {"edge": "httpHeaderAuth", "turnstile": "httpCustomAuth", "postgres": "postgres", "smtp": "smtp"}
        name = self.cfg["credentials"][kind]
        return {types[kind]: {"id": "it7q-" + kind, "name": name}}

    def webhook(self, name, path, method, pos, cors=True):
        options = {}
        if cors:
            options["allowedOrigins"] = ",".join(self.cfg["site_origins"] + self.cfg["preview_origins"])
        return self.add(name, "webhook", 2, {
            "httpMethod": method, "path": path, "authentication": "headerAuth",
            "responseMode": "responseNode", "options": options,
        }, pos, self.cred("edge"), webhookId=self._id(name + "/webhook"))

    def code(self, name, step, pos):
        src = (CODE / "common.js").read_text(encoding="utf-8")
        src = src.replace("__CONFIG__", json.dumps(self.jscfg, ensure_ascii=False, sort_keys=True), 1)
        parts = [src] + [(CODE / lib).read_text(encoding="utf-8") for lib in self.libs]
        body = (CODE / step).read_text(encoding="utf-8")
        if "__NDA_HTML__" in body:
            body = body.replace("__NDA_HTML__", json.dumps(build.render_md(build.load_nda()["text"], top=2)), 1)
        parts.append("// ---- step: n8n/code/%s\n%s" % (step, body))
        return self.add(name, "code", 2, {"jsCode": "\n".join(parts)}, pos)

    def go(self, name, pos, expr="={{ $json.go }}"):
        return self.add(name, "if", 2, {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [{"id": self._id(name + "/cond"), "leftValue": expr, "rightValue": "",
                                "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
                "combinator": "and",
            },
            "options": {},
        }, pos)

    def turnstile(self, name, pos):
        return self.add(name, "httpRequest", 4.2, {
            "method": "POST", "url": TURNSTILE_URL,
            "authentication": "genericCredentialType", "genericAuthType": "httpCustomAuth",
            "sendBody": True, "contentType": "json", "specifyBody": "keypair",
            "bodyParameters": {"parameters": [
                {"name": "response", "value": "={{ $json.turnstile }}"},
                {"name": "remoteip", "value": "={{ $json.ip }}"},
            ]},
            "options": {"timeout": 10000},
        }, pos, self.cred("turnstile"))

    def access_certs(self, name, pos):
        return self.add(name, "httpRequest", 4.2, {
            "method": "GET",
            "url": "https://%s.cloudflareaccess.com/cdn-cgi/access/certs" % self.cfg["access"]["team"],
            "options": {"timeout": 10000},
        }, pos)

    def sql(self, name, fn, pos):
        return self.add(name, "postgres", 2.5, {
            "operation": "executeQuery",
            "query": "SELECT web.%s($1::jsonb) AS r" % fn,
            "options": {"queryReplacement": "={{ [JSON.stringify($json.db)] }}"},
        }, pos, self.cred("postgres"))

    def email(self, name, source, key, pos, reply_to=None):
        ref = "$('%s').first().json.%s" % (source, key)
        options = {"appendAttribution": False, "replyTo": reply_to or self.cfg["mail"]["reply_to"]}
        return self.add(name, "emailSend", 2.1, {
            "fromEmail": self.cfg["mail"]["from"], "toEmail": "={{ %s.to }}" % ref,
            "subject": "={{ %s.subject }}" % ref, "emailFormat": "html", "html": "={{ %s.html }}" % ref,
            "options": options,
        }, pos, self.cred("smtp"), onError="continueRegularOutput")  # mail trouble mustn't change the reply

    def respond(self, name, pos, status=None, body=None):
        return self.add(name, "respondToWebhook", 1.1, {
            "respondWith": "json",
            "responseBody": body or "={{ JSON.stringify($json.body) }}",
            "options": {"responseCode": status or "={{ $json.status }}",
                        "responseHeaders": {"entries": [NO_STORE]}},
        }, pos)

    def respond_page(self, name, pos, source=None):
        ref = "$('%s').first().json" % source if source else "$json"
        return self.add(name, "respondToWebhook", 1.1, {
            "respondWith": "text", "responseBody": "={{ %s.html }}" % ref,
            "options": {"responseCode": "={{ %s.status }}" % ref, "responseHeaders": {"entries": PAGE_HEADERS}},
        }, pos)

    def schedule(self, name, pos):
        return self.add(name, "scheduleTrigger", 1.2, {
            "rule": {"interval": [{"field": "cronExpression", "expression": "15 3 * * *"}]},
        }, pos)

    # ---------------------------------------------------------------- output

    def json(self, secret_inputs=False):
        connections = {}
        for src, out, dst in self.edges:
            outs = connections.setdefault(src, {"main": []})["main"]
            while len(outs) <= out:
                outs.append([])
            outs[out].append({"node": dst, "type": "main", "index": 0})
        return {
            "name": "IT7Q " + self.name,
            "nodes": self.nodes,
            "connections": connections,
            "active": False,
            "settings": {
                "executionOrder": "v1",
                "timezone": self.cfg["timezone"],
                "saveManualExecutions": False,
                "saveDataSuccessExecution": "none",
                # Login passwords and review actions must never sit in n8n's execution log.
                "saveDataErrorExecution": "none" if secret_inputs else "all",
                "saveExecutionProgress": False,
            },
            "pinData": {},
            "meta": {"generatedBy": "tools/n8n_build.py; edit n8n/code/ and rebuild, not this file"},
        }


def form_hook(name, cfg, jscfg, step_dir, fn, emails):
    """nda-submission and website-enquiry share one shape."""
    w = Workflow(name, cfg, jscfg)
    w.webhook("Webhook", name, "POST", (0, 0))
    w.code("Validate", step_dir + "/validate.js", (1, 0))
    w.go("Valid?", (2, 0))
    w.turnstile("Turnstile", (3, 0))
    w.code("Check", step_dir + "/check.js", (4, 0))
    w.go("Human?", (5, 0))
    w.sql("Save", fn, (6, 0))
    w.code("After save", step_dir + "/after-save.js", (7, 0))
    w.go("Send email?", (8, 0))
    w.respond("Reply", (9, 2))
    w.respond("Reply 202", (11, 0), status=202, body='{"ok":true}')
    w.chain("Webhook", "Validate", "Valid?")
    w.link("Valid?", "Turnstile")
    w.link("Valid?", "Reply", 1)
    w.chain("Turnstile", "Check", "Human?")
    w.link("Human?", "Save")
    w.link("Human?", "Reply", 1)
    w.chain("Save", "After save", "Send email?")
    w.link("Send email?", "Reply", 1)
    prev = "Send email?"
    for i, (label, key, reply_to) in enumerate(emails):
        w.email(label, "After save", key, (9 + i, 0), reply_to)
        w.link(prev, label)
        prev = label
    w.link(prev, "Reply 202")
    return w


def workflows(cfg=None):
    cfg = cfg or load_config()
    jscfg = js_config(cfg)
    out = {}

    out["nda-submission"] = form_hook("nda-submission", cfg, jscfg, "nda-submission", "submit_nda", [
        ("Email signer", "signer", None), ("Email Chris", "chris", None)])
    out["website-enquiry"] = form_hook("website-enquiry", cfg, jscfg, "website-enquiry", "enquiry_add", [
        ("Email Chris", "mail", "={{ $('After save').first().json.mail.replyTo }}")])

    w = Workflow("nda-login", cfg, jscfg)
    w.webhook("Webhook", "nda-login", "POST", (0, 0))
    w.code("Validate", "nda-login/validate.js", (1, 0))
    w.go("Valid?", (2, 0))
    w.turnstile("Turnstile", (3, 0))
    w.code("Check", "nda-login/check.js", (4, 0))
    w.go("Human?", (5, 0))
    w.sql("Begin", "login_begin", (6, 0))
    w.code("Verify", "nda-login/verify.js", (7, 0))
    w.go("Not locked?", (8, 0))
    w.sql("Finish", "login_finish", (9, 0))
    w.code("Result", "nda-login/result.js", (10, 0))
    w.respond("Reply", (11, 1))
    w.chain("Webhook", "Validate", "Valid?", "Turnstile", "Check", "Human?", "Begin", "Verify", "Not locked?",
            "Finish", "Result", "Reply")
    for gate in ("Valid?", "Human?", "Not locked?"):
        w.link(gate, "Reply", 1)
    out["nda-login"] = w

    w = Workflow("nda-content", cfg, jscfg)
    w.webhook("Webhook", "nda-content", "POST", (0, 0))
    w.code("Validate", "nda-content/validate.js", (1, 0))
    w.go("Valid?", (2, 0))
    w.go("Logout?", (3, 0), expr="={{ $json.op === 'logout' }}")
    w.sql("Logout", "logout", (4, -1))
    w.code("Logged out", "nda-content/logged-out.js", (5, -1))
    w.sql("Content", "content_get", (4, 0))
    w.code("Shape", "nda-content/shape.js", (5, 0))
    w.respond("Reply", (6, 1))
    w.chain("Webhook", "Validate", "Valid?", "Logout?", "Logout", "Logged out", "Reply")
    w.link("Valid?", "Reply", 1)
    w.link("Logout?", "Content", 1)
    w.chain("Content", "Shape", "Reply")
    out["nda-content"] = w

    w = Workflow("nda-review", cfg, jscfg, libs=("nda-review/_page.js",))
    w.webhook("Webhook GET", "nda-review", "GET", (0, 0), cors=False)
    w.access_certs("Access keys (GET)", (1, 0))
    w.code("Verify GET", "nda-review/verify-get.js", (2, 0))
    w.go("Allowed (GET)?", (3, 0))
    w.sql("View", "review_view", (4, 0))
    w.code("Render", "nda-review/render.js", (5, 0))
    w.respond_page("Page (GET)", (6, 0))
    w.chain("Webhook GET", "Access keys (GET)", "Verify GET", "Allowed (GET)?", "View", "Render", "Page (GET)")
    w.link("Allowed (GET)?", "Page (GET)", 1)
    w.webhook("Webhook POST", "nda-review", "POST", (0, 3), cors=False)
    w.access_certs("Access keys (POST)", (1, 3))
    w.code("Verify POST", "nda-review/verify-post.js", (2, 3))
    w.go("Allowed (POST)?", (3, 3))
    w.sql("Decide", "review_post", (4, 3))
    w.code("Outcome", "nda-review/outcome.js", (5, 3))
    w.go("Send email?", (6, 3))
    w.email("Email", "Outcome", "mail", (7, 2))
    w.respond_page("Page (after email)", (8, 2), source="Outcome")
    w.respond_page("Page (POST)", (8, 4))
    w.chain("Webhook POST", "Access keys (POST)", "Verify POST", "Allowed (POST)?", "Decide", "Outcome", "Send email?",
            "Email", "Page (after email)")
    w.link("Allowed (POST)?", "Page (POST)", 1)
    w.link("Send email?", "Page (POST)", 1)
    out["nda-review"] = w

    w = Workflow("nda-retention", cfg, jscfg)
    w.schedule("Daily 03:15", (0, 0))
    w.add("Retention", "postgres", 2.5, {"operation": "executeQuery", "query": "SELECT web.retention('{}'::jsonb) AS r",
                                         "options": {}}, (1, 0), w.cred("postgres"))
    w.link("Daily 03:15", "Retention")
    out["nda-retention"] = w

    secret = {"nda-login", "nda-review"}
    return {name: wf.json(secret_inputs=name in secret) for name, wf in out.items()}


def render(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main(argv):
    built = workflows()
    stale = []
    for name, data in built.items():
        path = OUT / ("%s.json" % name)
        text = render(data)
        if "--check" in argv:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if "--check" in argv:
        if stale:
            print("out of date (run python3 tools/n8n_build.py): " + ", ".join(stale), file=sys.stderr)
            return 1
        print("n8n workflows up to date: %d" % len(built))
        return 0
    print("wrote %d workflows to %s" % (len(built), OUT.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
