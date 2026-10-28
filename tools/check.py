#!/usr/bin/env python3
"""Pre-deploy checks for the IT7Q site (PLAN.md §2.3, §3, §4.9, §5.1, §6.2).

    python3 tools/check.py [dist_dir] [--mock]

--mock accepts a local mock build (tools/build.py --mock); without it the
generated config must point at the production webhooks.

Exits non-zero if anything fails. tools/build.py runs this after every build,
so a failing check also fails the Cloudflare Pages deploy.
"""
import datetime
import html
import json
import re
import sys
import zlib
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rastermark  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
GATED = ROOT / "gated"

RASTER_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff", ".ico"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
CONSENT_METHODS = ("email", "written", "form", "sms")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

# Brand-pack colours that must never be used (Q37): navy, and every pack accent
PACK_COLOURS = [
    "0E1326", "EAAE40", "BB2949", "DF6D2E", "7FB8EA", "1C4F9C", "3A86CF", "C3A6EC", "5E3496", "8B5CC9",
    "E8B04A", "8A3B12", "C8662A", "A6D86E", "22704A", "43A867", "3FC8DB", "7A2AC8", "D5479F", "F2C14E",
    "0E7470", "22A89C",
]
# §4.9: never in public pages, whatever the context
PUBLIC_FORBIDDEN = [
    r"wire\s?guard", r"\bwg0\b", r"\btunnel", r"cloudflared", r"agent\s+smith", r"\bwazuh\b",
    r"velociraptor", r"\bclamav\b", r"\bn8n\b", r"nubius", r"\bvps\d", r"pantheon",
]
# §4.9: never in gated detail either
GATED_FORBIDDEN = PUBLIC_FORBIDDEN + [
    r"\b\d{1,3}(?:\.\d{1,3}){3}\b", r"\b[0-9a-f]{1,4}(?::[0-9a-f]{1,4}){3,7}\b", r":\d{2,5}\b",
    r"\bgit\.", r"\.git\b", r"\bport\b", r"[\w-]+\.nubius\.com\.au",
    r"\b(?!(?:p\d+|www|downloads)\.)[\w-]+\.it7q\.com\.au",
]
# Q55: these two may appear only under resources/, as general recommendations for the reader
RESOURCE_ONLY = [r"wire\s?guard", r"\bclamav\b"]
RESOURCES_DIR = "resources/"
FIRST_PERSON = re.compile(
    r"\bwe(?:'re| are)? (?:use|run|rely on|deploy)\b|\bour (?:own )?(?:setup|stack|servers?|network|systems?|infrastructure)\b",
    re.I)
# §2.5: a domestic-violence use case stays gated, so nothing public near PORTUS puts a user at risk
PORTUS_SENSITIVE = re.compile(
    r"domestic|family violence|\bviolen|\babus|\brefuge|\bescap|coercive|perpetrator|\bvictim|\bstalk", re.I)
# §2.4: IT7Q never hosts installers or archives
BINARY_EXT = {".exe", ".msi", ".msix", ".dmg", ".pkg", ".apk", ".aab", ".ipa", ".deb", ".rpm", ".appimage", ".snap",
              ".flatpak", ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".xz", ".bz2", ".iso", ".img", ".bin", ".jar",
              ".bat", ".cmd", ".ps1", ".sh", ".vbs", ".scr"}
GUIDE_PDF_DIR = "resources/guides/pdf/"
PDF_META = re.compile(rb"/(?:Author|Creator)\s*(?:\((?!\))|<(?!>))|<(?:dc:creator|xmp:CreatorTool)\b")
LOCAL_PATH = re.compile(rb"[A-Za-z]:\\{1,2}\w|/home/|/Users/|/srv/|/opt/")
# §4.12 / Q58: the webhook base (endpoints.json "hooks") may appear only in the generated config and the CSP
CONFIG_JS = "assets/js/config.js"
HEADERS = "_headers"
ENDPOINTS = SRC / "data/endpoints.json"
# Rendering of gated content must use DOM APIs only (§4.6)
JS_SINKS = re.compile(r"\.innerHTML|\.outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|new\s+Function\b")
FINANCIAL = re.compile(
    r"\$\s?\d[\d,.]*\s*(?:k|m|bn|million|billion)?[^.\n]{0,60}"
    r"(?:revenue|profit|turnover|projection|forecast|valuation|\barr\b|\bmrr\b|ebitda|run[- ]rate|margin)"
    r"|(?:revenue|profit|turnover|projection|forecast|valuation|\barr\b|\bmrr\b|ebitda|run[- ]rate|margin)"
    r"[^.\n]{0,60}\$\s?\d",
    re.I,
)
PRICE = re.compile(r"\$\s?\d[\d,.]*")


def prod_hooks():
    """The one public webhook base (Q58). Moving it off nubius makes nubius fail everywhere in dist/."""
    return json.loads(ENDPOINTS.read_text(encoding="utf-8"))["hooks"]


def origin(url):
    m = re.match(r"https://[^/]+", url)
    return m.group(0) if m else url


def host(url):
    m = re.match(r"https://([^/:?#]+)(?:[/?#]|$)", url)
    return m.group(1).lower() if m else None


def official_download(url, domain):
    h = host(url)
    return h is not None and (h == domain or h.endswith("." + domain))


def visible_sentences(text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", text)))
    return [s for s in re.split(r"(?<=[.!?])\s+|\n\s*\n", re.sub(r"[ \t]+", " ", text)) if s.strip()]


def rel(path):
    """Readable path for reports, whether or not it sits inside the repo."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


class Report:
    def __init__(self):
        self.failures = []

    def fail(self, where, msg):
        self.failures.append("%s: %s" % (where, msg))


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.ids = [], [], set()
        self.links, self.h1, self.title, self.lang, self.desc = [], 0, "", None, False
        self.inline_script, self.inline_style, self.handlers = False, False, []
        self.svg_refs, self._in_title, self._in_script_src = [], False, None
        self.controls, self.label_fors = [], set()

    def handle_starttag(self, tag, attrs):
        self._attrs(tag, attrs)
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self._attrs(tag, attrs)

    def _attrs(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                self.errors.append("duplicate id %r" % a["id"])
            self.ids.add(a["id"])
        for name, _ in attrs:
            if name.startswith("on"):
                self.handlers.append("%s %s" % (tag, name))
        if "style" in a:
            self.inline_style = True
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta" and a.get("name") == "description" and a.get("content"):
            self.desc = True
        if tag == "script":
            if not a.get("src"):
                self.inline_script = True
            self.links.append(a.get("src", ""))
        if tag == "style":
            self.inline_style = True
        if tag in ("a", "link") and a.get("href"):
            self.links.append(a["href"])
        if tag in ("img", "source", "iframe") and a.get("src"):
            self.links.append(a["src"])
        if tag == "img" and not a.get("alt") and a.get("alt") != "":
            self.errors.append("<img> without alt")
        if tag == "use":
            self.svg_refs.append(a.get("href", ""))
        if tag in ("input", "select", "textarea") and a.get("type") not in ("hidden", "submit", "button"):
            self.controls.append(a.get("id") or "<%s name=%s>" % (tag, a.get("name")))
        if tag == "label" and a.get("for"):
            self.label_fors.add(a["for"])
        if tag == "foreignobject":
            self.errors.append("<foreignObject> in inline SVG")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append("unexpected </%s> (open: %s)" % (tag, "/".join(self.stack[-3:])))
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def resolve(dist, page, href):
    """Map an internal href to a dist file, or None if external/special."""
    if re.match(r"^(https?:|mailto:|tel:|data:)", href):
        return None
    path = href.split("#")[0].split("?")[0]
    if not path:
        return None
    if not path.startswith("/"):
        path = "/" + str(page.parent.relative_to(dist) / path)
    target = dist / path.lstrip("/")
    if path.endswith("/"):
        target = target / "index.html"
    return target


def check_pages(dist, r):
    for page in sorted(dist.rglob("*.html")):
        where = str(page.relative_to(dist))
        text = page.read_text(encoding="utf-8")
        p = PageParser()
        p.feed(text)
        p.close()
        for e in p.errors:
            r.fail(where, e)
        if p.stack and p.stack != ["html"]:
            r.fail(where, "unclosed tags: %s" % "/".join(p.stack))
        if p.lang != "en-AU":
            r.fail(where, "<html lang> should be en-AU")
        if not p.title.strip():
            r.fail(where, "missing <title>")
        if not p.desc:
            r.fail(where, "missing meta description")
        if p.h1 != 1:
            r.fail(where, "expected exactly one <h1>, found %d" % p.h1)
        if p.inline_script:
            r.fail(where, "inline <script> (blocked by CSP)")
        if p.inline_style:
            r.fail(where, "inline style (blocked by CSP)")
        for h in p.handlers:
            r.fail(where, "inline event handler %s (blocked by CSP)" % h)
        for control in p.controls:
            if control not in p.label_fors:
                r.fail(where, "form field %s has no <label for> (accessibility)" % control)
        for ref in p.svg_refs:
            if not ref.startswith("#") or ref[1:] not in p.ids:
                r.fail(where, "SVG <use> points at missing or external %r" % ref)
        for href in p.links:
            if href.startswith("#"):
                if href[1:] and href[1:] not in p.ids:
                    r.fail(where, "anchor %s not found" % href)
                continue
            target = resolve(dist, page, href)
            if target is not None and not target.exists():
                r.fail(where, "broken link %s" % href)
            if href.startswith("http://"):
                r.fail(where, "insecure link %s" % href)


def check_text_guards(dist, r, allowed_prices=frozenset()):
    public = [p for p in dist.rglob("*") if p.is_file() and (
        p.suffix in (".html", ".css", ".js", ".svg", ".json", ".txt") or p.name == HEADERS)]
    hooks = prod_hooks()
    for f in public:
        where = str(f.relative_to(dist))
        text = f.read_text(encoding="utf-8", errors="replace")
        if where == CONFIG_JS:
            text = text.replace(hooks, "")  # the allowed mentions (§4.12, Q58)
        elif where == HEADERS:
            text = text.replace(origin(hooks), "")
        in_resources = where.startswith(RESOURCES_DIR)
        for pat in PUBLIC_FORBIDDEN:
            if in_resources and pat in RESOURCE_ONLY:
                continue
            m = re.search(pat, text, re.I)
            if m:
                r.fail(where, "public-wording guard: %r must not appear (§4.9)" % m.group(0))
        if in_resources and where.endswith(".html"):
            for s in visible_sentences(text):
                if any(re.search(p, s, re.I) for p in RESOURCE_ONLY) and FIRST_PERSON.search(s):
                    r.fail(where, "public-wording guard: %r reads as IT7Q's own setup (Q55)" % s.strip()[:80])
        for m in PRICE.finditer(text):
            amount = m.group(0).rstrip(".,").replace(" ", "")
            if amount not in allowed_prices:
                r.fail(where, "price guard: %r is not an approved public price (Q28)" % amount)
        if FINANCIAL.search(text):
            r.fail(where, "financial guard: money figure next to a financial term")
    for base in (SRC, dist):
        for f in base.rglob("*"):
            if f.is_file() and f.suffix in (".html", ".css", ".js", ".svg", ".json"):
                text = f.read_text(encoding="utf-8", errors="replace").upper()
                for hexval in PACK_COLOURS:
                    if re.search(r"#?\b%s\b" % hexval, text):
                        r.fail(rel(f), "pack colour #%s must not be used (Q37)" % hexval)
    for f in SRC.rglob("*"):
        if f.is_file() and f.suffix in (".html", ".json") and FINANCIAL.search(f.read_text(encoding="utf-8")):
            r.fail(rel(f), "financial guard: money figure next to a financial term")


def check_svgs(dist, r):
    for base in (SRC, dist):
        for f in base.rglob("*.svg"):
            text = f.read_text(encoding="utf-8", errors="replace")
            where = rel(f)
            if re.search(r"<script|<foreignObject|<!DOCTYPE|<!ENTITY|\son\w+\s*=", text, re.I):
                r.fail(where, "SVG contains script, handler, foreignObject or DTD")
            for ref in re.findall(r'(?:xlink:)?href="([^"]*)"', text):
                if not ref.startswith("#"):
                    r.fail(where, "SVG references external %r" % ref)


def check_rasters(dist, r):
    for f in dist.rglob("*"):
        if f.is_file() and f.suffix.lower() in RASTER_EXT:
            ok, why = rastermark.verify(f.read_bytes(), f.suffix)
            if not ok:
                r.fail(str(f.relative_to(dist)), "watermark check: %s" % why)


def check_scripts(dist, r, mock=False):
    for f in dist.rglob("*.js"):
        m = JS_SINKS.search(f.read_text(encoding="utf-8", errors="replace"))
        if m:
            r.fail(str(f.relative_to(dist)), "script uses %r: build DOM with textContent only (§4.6)" % m.group(0))
    path = dist / CONFIG_JS
    if not path.exists():
        r.fail(CONFIG_JS, "missing from dist/")
        return
    m = re.fullmatch(r"//[^\n]*\nwindow\.IT7Q_CONFIG = Object\.freeze\((\{.*\})\);\n", path.read_text(encoding="utf-8"), re.S)
    try:
        cfg = json.loads(m.group(1)) if m else None
    except ValueError:
        cfg = None
    if not isinstance(cfg, dict):
        r.fail(CONFIG_JS, "not in the generated format")
        return
    if cfg.get("mock") and not mock:
        r.fail(CONFIG_JS, "this is a LOCAL MOCK build and must never be deployed; run tools/build.py without --mock")
    if not cfg.get("mock") and cfg.get("hooks") != prod_hooks():
        r.fail(CONFIG_JS, "hooks must be %s (endpoints.json)" % prod_hooks())
    if not prod_hooks().startswith("https://"):
        r.fail(rel(ENDPOINTS), "hooks must be an https:// URL")


def check_fonts(dist, r):
    for f in dist.rglob("*"):
        if f.is_file() and f.suffix.lower() in FONT_EXT:
            family = f.name.split("-")[0]
            if not (f.parent / ("%s-OFL.txt" % family)).exists():
                r.fail(str(f.relative_to(dist)), "font licence guard: %s-OFL.txt must ship beside it (Q40)" % family)


def testimonial_problems(entry, today=None):
    """Reasons an entry can't be kept (§2.3). Empty list = fine. Shared with build.py."""
    if not isinstance(entry, dict):
        return ["is not an object"]
    problems = []
    if not str(entry.get("quote", "")).strip():
        problems.append("has no quote")
    if not (str(entry.get("name", "")).strip() or str(entry.get("business", "")).strip()):
        problems.append("needs a name or a business")
    consent = entry.get("consent") if isinstance(entry.get("consent"), dict) else {}
    try:
        recorded = datetime.date.fromisoformat(str(consent.get("recorded", "")))
    except ValueError:
        problems.append("lacks recorded consent: consent.recorded must be a YYYY-MM-DD date")
    else:
        if recorded > (today or datetime.date.today()):
            problems.append("consent.recorded is in the future")
    if consent.get("method") not in CONSENT_METHODS:
        problems.append("lacks recorded consent: consent.method must be one of %s" % ", ".join(CONSENT_METHODS))
    if entry.get("approved") not in (True, False):
        problems.append("approved must be true or false")
    return problems


def check_testimonials(dist, r, path=None):
    path = path or SRC / "data/testimonials.json"
    if not path.exists():
        return
    where = rel(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        r.fail(where, 'needs an "entries" list')
        return
    public_text = html.unescape("\n".join(f.read_text(encoding="utf-8") for f in dist.rglob("*.html")))
    for i, entry in enumerate(entries, 1):
        for problem in testimonial_problems(entry):
            r.fail(where, "consent guard: entry %d %s" % (i, problem))
        if isinstance(entry, dict) and entry.get("approved") is not True:
            quote = str(entry.get("quote", "")).strip()
            if quote and quote in public_text:
                r.fail(where, "consent guard: unapproved entry %d appears in dist/" % i)


def gated_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from gated_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from gated_strings(v)


def check_gated(dist, r):
    if not GATED.exists():
        return
    public_text = "\n".join(
        f.read_text(encoding="utf-8", errors="replace") for f in dist.rglob("*") if f.is_file() and f.suffix in (".html", ".js", ".json")
    )
    for f in sorted(GATED.glob("*.json")):
        where = rel(f)
        data = json.loads(f.read_text(encoding="utf-8"))
        for s in gated_strings(data):
            for pat in GATED_FORBIDDEN:
                m = re.search(pat, s, re.I)
                if m:
                    r.fail(where, "infrastructure guard: %r (§4.9)" % m.group(0))
            if len(s) >= 20 and s in public_text:
                r.fail(where, "gated text leaked into dist/: %r" % s[:40])
            if FINANCIAL.search(s):
                r.fail(where, "financial guard: money figure next to a financial term")


def check_portfolio(dist, r):
    path = SRC / "data/portfolio.json"
    if not path.exists():
        return
    public_text = html.unescape("\n".join(
        f.read_text(encoding="utf-8", errors="replace")
        for f in dist.rglob("*") if f.is_file() and f.suffix in (".html", ".js", ".json", ".txt")
    ))
    for entry in json.loads(path.read_text(encoding="utf-8")):
        if not entry.get("published", False) and entry.get("name") and entry["name"] in public_text:
            r.fail("portfolio.json", "unpublished entry %r appears in dist/" % entry["name"])


def check_downloads(dist, r):
    """§2.4: Download buttons go only to official sites; no installers or archives ship."""
    path = SRC / "data/resources.json"
    allowed = set()
    if path.exists():
        for e in json.loads(path.read_text(encoding="utf-8"))["entries"]:
            if official_download(e.get("download", ""), e.get("domain", "")):
                allowed.add(e["download"])
            else:
                r.fail("resources.json", "download-link guard: %s must be https:// on %s" % (e.get("name"), e.get("domain")))
    for f in dist.rglob("*"):
        if f.is_file() and f.suffix.lower() in BINARY_EXT:
            r.fail(str(f.relative_to(dist)), "download-link guard: no binaries or archives on the site (§2.4)")
    for page in dist.rglob("*.html"):
        for tag in re.findall(r"<a\b[^>]*\bdata-download\b[^>]*>", page.read_text(encoding="utf-8")):
            m = re.search(r'href="([^"]*)"', tag)
            href = html.unescape(m.group(1)) if m else ""
            if href not in allowed:
                r.fail(str(page.relative_to(dist)), "download-link guard: %r is not an official download page" % href)


def check_pdfs(dist, r):
    """§2.4: guide PDFs only, with no metadata, local paths or banned words."""
    for f in dist.rglob("*"):
        if not (f.is_file() and f.suffix.lower() == ".pdf"):
            continue
        where = str(f.relative_to(dist))
        if not where.startswith(GUIDE_PDF_DIR):
            r.fail(where, "PDF guard: PDFs ship only as guides under /%s" % GUIDE_PDF_DIR)
        raw = f.read_bytes()
        chunks = [raw]
        for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
            try:
                chunks.append(zlib.decompress(m.group(1)))
            except zlib.error:
                pass
        data = b"\n".join(chunks)
        if PDF_META.search(data):
            r.fail(where, "PDF guard: author/creator metadata must be stripped before it ships")
        if LOCAL_PATH.search(data):
            r.fail(where, "PDF guard: contains a local file path")
        text = data.decode("latin-1")
        for pat in PUBLIC_FORBIDDEN:
            if pat in RESOURCE_ONLY and where.startswith(RESOURCES_DIR):
                continue
            m = re.search(pat, text, re.I)
            if m:
                r.fail(where, "PDF guard: %r must not appear (§4.9)" % m.group(0))


def check_portus(dist, r):
    """§2.5: public PORTUS wording stays on community safety."""
    for page in dist.rglob("*.html"):
        where = str(page.relative_to(dist))
        whole = where == "divisions/portus/index.html"
        for s in visible_sentences(page.read_text(encoding="utf-8")):
            if (whole or "portus" in s.lower()) and PORTUS_SENSITIVE.search(s):
                r.fail(where, "PORTUS discretion guard: %r belongs in gated detail only" % PORTUS_SENSITIVE.search(s).group(0))
    for name, pick in (("projects.json", lambda x: x.get("division") == "portus"),
                       ("divisions.json", lambda x: x.get("slug") == "portus")):
        path = SRC / "data" / name
        if path.exists():
            for entry in json.loads(path.read_text(encoding="utf-8")):
                if pick(entry):
                    for s in gated_strings(entry):
                        if PORTUS_SENSITIVE.search(s):
                            r.fail(name, "PORTUS discretion guard: %r belongs in gated detail only"
                                   % PORTUS_SENSITIVE.search(s).group(0))


def check_footer_links(dist, r, site=None):
    """One Staff link per page, in the footer only, to an it7q.com.au name; social links over https."""
    site = site or json.loads((SRC / "data/site.json").read_text(encoding="utf-8"))
    url = site.get("staff_url", "")
    if not re.fullmatch(r"https://[a-z0-9-]+\.it7q\.com\.au/?", url):
        r.fail("site.json", "footer guard: staff_url must be https://<name>.it7q.com.au")
    if any(n.get("href") == url for n in site.get("nav", [])):
        r.fail("site.json", "footer guard: the Staff link must not be in the main nav")
    for s in site.get("social", []):
        if s.get("href") and not s["href"].startswith("https://"):
            r.fail("site.json", "footer guard: social link %s must be https://" % s.get("key"))
    needle = 'href="%s"' % html.escape(url, quote=True)
    for page in dist.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        where = str(page.relative_to(dist))
        if text.count(needle) != 1:
            r.fail(where, "footer guard: expected exactly one Staff link, found %d" % text.count(needle))
        elif text.find(needle) < text.find("<footer"):
            r.fail(where, "footer guard: the Staff link must sit in the footer only")


def approved_prices():
    """Dollar amounts named in projects.json public_price fields (Q28: SCUTUM only)."""
    path = SRC / "data/projects.json"
    if not path.exists():
        return set()
    return {
        amount.rstrip(".,").replace(" ", "")
        for p in json.loads(path.read_text(encoding="utf-8")) if p.get("public_price")
        for amount in PRICE.findall(p["public_price"])
    }


def run(dist, mock=False):
    r = Report()
    for required in ("index.html", "404.html", "_headers", "favicon.svg"):
        if not (dist / required).exists():
            r.fail(required, "missing from dist/")
    check_pages(dist, r)
    check_text_guards(dist, r, approved_prices())
    check_svgs(dist, r)
    check_rasters(dist, r)
    check_scripts(dist, r, mock)
    check_fonts(dist, r)
    check_gated(dist, r)
    check_portfolio(dist, r)
    check_testimonials(dist, r)
    check_downloads(dist, r)
    check_pdfs(dist, r)
    check_portus(dist, r)
    check_footer_links(dist, r)
    return r


def main(argv):
    mock = "--mock" in argv
    argv = [a for a in argv if a != "--mock"]
    dist = Path(argv[0]) if argv else ROOT / "dist"
    if not dist.is_dir():
        print("CHECK FAILED: %s does not exist; run tools/build.py first" % dist, file=sys.stderr)
        return 1
    r = run(dist.resolve(), mock)
    if r.failures:
        print("CHECK FAILED (%d):" % len(r.failures), file=sys.stderr)
        for f in r.failures:
            print("  - " + f, file=sys.stderr)
        return 1
    pages = len(list(dist.rglob("*.html")))
    print("check passed: %d pages, links, CSP, wording, prices, pack colours, SVGs, watermarks, fonts, consent, "
          "downloads, PDFs, PORTUS, footer" % pages)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
