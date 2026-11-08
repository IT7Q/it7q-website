#!/usr/bin/env python3
"""Build the IT7Q site: src/ -> dist/ (PLAN.md §3).

    python3 tools/build.py            build, then run tools/check.py
    python3 tools/build.py --no-check build only (for debugging)
    python3 tools/build.py --mock     local build whose forms talk to tools/preview.py
                                      (never deployed: Pages runs the plain build)

Pages are src/pages/**/*.html with a small front-matter block. Templating:
    {{site.key}} / {{d.key}}   escaped value from data
    {{> component}}            generated HTML block (see COMPONENTS)
    <x-ph id w h>text</x-ph>   image slot: on-brand SVG artwork until the real photo exists
Anything unresolved fails the build. Raster images are watermarked on the way
to dist/ (§5.1); sources in src/ are never modified. Stdlib only, except that
JPEG/WebP sources need Pillow (requirements.txt, Q43).
"""
import datetime
import hashlib
import html
import json
import re
import shutil
import sys
from math import gcd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402
import pngmark  # noqa: E402
import rastermark  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
RASTER_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff", ".ico"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
FONT_FILES = [  # (file, family, weight, style): only these ship (Q40)
    ("Rajdhani-Medium.ttf", "Rajdhani", "500", "normal"),
    ("Rajdhani-SemiBold.ttf", "Rajdhani", "600", "normal"),
    ("Rajdhani-Bold.ttf", "Rajdhani", "700", "normal"),
    ("Exo2-wght.ttf", "Exo 2", "100 900", "normal"),
    ("Exo2-Italic-wght.ttf", "Exo 2", "100 900", "italic"),
]
PH_RATIOS = {(16, 9): "16x9", (8, 5): "16x10", (1, 1): "1x1", (40, 21): "og"}
MASTER_COLOURS = {"tl": "#00B4CC", "tr": "#7EC820", "bl": "#8B5CF6", "br": "#F97316"}
STATUS_CLASS = {
    "Developed": "done", "In development": "dev", "In design": "design",
    "Documented": "doc", "Coming soon": "soon",
    "In use": "done", "In use in-house": "done", "Concept": "design",  # Chris, gated review 8 Nov
}
PROD_SCRIPTS = ("forms", "nda")  # page scripts a page may ask for in front matter
PROJECT_FIELDS = {"id", "division", "name", "status", "one_liner", "why", "who", "note",
                  "featured", "public_price", "group", "link", "link_text", "gated"}
CREDENTIAL_FIELDS = {"title", "issuer", "year", "in_progress"}  # whole qualifications only, no units (Q53)
GUIDES_SRC = SRC / "guides"  # <slug>.md (browser view) and <slug>.pdf (download), supplied by Chris
GUIDE_PDF_DIR = "resources/guides/pdf"


class BuildError(Exception):
    pass


def esc(value):
    return html.escape(str(value), quote=True)


def load_json(name):
    return json.loads((SRC / "data" / name).read_text(encoding="utf-8"))


def parse_page(text, where):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise BuildError("%s: missing front matter" % where)
    meta = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    for required in ("title", "description"):
        if not meta.get(required):
            raise BuildError("%s: front matter needs %s" % (where, required))
    return meta, text[m.end():]


# ---------------------------------------------------------------- data checks

def check_projects(projects, divisions):
    slugs = {d["slug"]: d for d in divisions}
    seen = set()
    for p in projects:
        pid = p.get("id", "?")
        unknown = set(p) - PROJECT_FIELDS
        if unknown:
            raise BuildError("projects.json %s: unknown field(s) %s" % (pid, ", ".join(sorted(unknown))))
        for field in ("id", "division", "name", "status", "one_liner"):
            if not p.get(field):
                raise BuildError("projects.json %s: missing %s" % (pid, field))
        if pid in seen:
            raise BuildError("projects.json: duplicate id %s" % pid)
        seen.add(pid)
        if p["division"] not in slugs:
            raise BuildError("projects.json %s: unknown division %r" % (pid, p["division"]))
        if p["status"] not in STATUS_CLASS:
            raise BuildError("projects.json %s: status must be one of %s" % (pid, ", ".join(STATUS_CLASS)))
        if p.get("link") and not p["link"].startswith("/"):
            raise BuildError("projects.json %s: link must be a page on this site" % pid)
        if p.get("gated", True) is not True and p.get("gated") is not False:
            raise BuildError("projects.json %s: gated must be true or false" % pid)
        groups = {g["key"] for g in slugs[p["division"]].get("groups", [])}
        if groups and p.get("group") not in groups:
            raise BuildError("projects.json %s: group must be one of %s" % (pid, ", ".join(sorted(groups))))
    for d in divisions:
        if not any(p["division"] == d["slug"] for p in projects):
            raise BuildError("projects.json: division %s has no projects" % d["slug"])


def check_resources(resources, guide_slugs):
    for e in resources["entries"]:
        name = e.get("name", "?")
        for field in ("name", "what", "why", "download", "domain"):
            if not e.get(field):
                raise BuildError("resources.json %s: missing %s" % (name, field))
        if not check.official_download(e["download"], e["domain"]):
            raise BuildError("resources.json %s: download must be https:// on %s (§2.4)" % (name, e["domain"]))
        if e.get("guide") and e["guide"] not in guide_slugs:
            raise BuildError("resources.json %s: unknown guide %r" % (name, e["guide"]))


def load_guides():
    """guides.json plus which files Chris has supplied for each guide."""
    data = load_json("guides.json")
    guides = {}
    for section in data["sections"]:
        for g in section["guides"]:
            if g["slug"] in guides or not re.fullmatch(r"[a-z0-9-]+", g["slug"]):
                raise BuildError("guides.json: bad or duplicate slug %r" % g["slug"])
            eyebrow = section["title"] + (" · Chapter %d" % g["chapter"] if g.get("chapter") else "")
            guides[g["slug"]] = dict(g, eyebrow=eyebrow,
                                     md=(GUIDES_SRC / (g["slug"] + ".md")).exists(),
                                     pdf=(GUIDES_SRC / (g["slug"] + ".pdf")).exists())
    if GUIDES_SRC.exists():
        for f in GUIDES_SRC.iterdir():
            if f.is_file() and not f.name.startswith(".") and (f.suffix not in (".md", ".pdf") or f.stem not in guides):
                raise BuildError("src/guides/%s: not <slug>.md or <slug>.pdf for a guide in guides.json" % f.name)
    return data, guides


def check_credentials(data):
    for i, e in enumerate(data["entries"], 1):
        unknown = set(e) - CREDENTIAL_FIELDS
        if unknown:
            raise BuildError("credentials.json entry %d: unknown field(s) %s (no unit details, Q53)"
                             % (i, ", ".join(sorted(unknown))))
        if not e.get("title"):
            raise BuildError("credentials.json entry %d: missing title" % i)
    return data["entries"]


NO_SOCIAL = re.compile(r"reddit|etsy", re.I)  # Q54: no Reddit or Etsy in the footer


def check_social(site):
    for s in site["social"]:
        if s.get("href") and not s["href"].startswith("https://"):
            raise BuildError("site.json social %s: link must be https://" % s["key"])
        if NO_SOCIAL.search(s["key"] + " " + s.get("href", "")):
            raise BuildError("site.json social %s: no Reddit or Etsy links in the footer (Q54)" % s["key"])


def shown_social(site):
    """Entries with a URL that aren't marked hidden (Google Business, TikTok until ready)."""
    return [s for s in site["social"] if s.get("href") and not s.get("hidden")]


def approved_testimonials(data):
    entries = data.get("entries", []) if isinstance(data, dict) else []
    approved = [e for e in entries if isinstance(e, dict) and e.get("approved") is True]
    for i, e in enumerate(approved, 1):
        problems = check.testimonial_problems(e)
        if problems:  # never publish a quote without recorded consent (§2.3)
            raise BuildError("testimonials.json: approved entry %d %s" % (i, "; ".join(problems)))
    return approved


# ---------------------------------------------------------------- legal text

def inline_md(text):
    out = esc(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", out)


def render_md(text, top=2):
    """Just enough Markdown for the legal texts: ### headings, paragraphs, - lists (two levels), bold."""
    out, para, lists = [], [], []  # lists: stack of indent levels with an open <ul>

    def close_para():
        if para:
            out.append("<p>%s</p>" % inline_md(" ".join(para)))
            para.clear()

    def close_lists(level=-1):
        while lists and lists[-1] > level:
            lists.pop()
            out.append("</li></ul>")

    for line in text.splitlines():
        m = re.match(r"^(\s*)- (.*)$", line)
        if line.startswith("#"):
            close_para()
            close_lists()
            hashes = len(line) - len(line.lstrip("#"))
            level = min(6, top + hashes - 3)
            out.append("<h%d>%s</h%d>" % (level, inline_md(line.lstrip("#").strip()), level))
        elif m:
            close_para()
            indent = len(m.group(1))
            if not lists or indent > lists[-1]:
                out.append("<ul>")
                lists.append(indent)
            else:
                close_lists(indent)
                out.append("</li>")
            out.append("<li>%s" % inline_md(m.group(2)))
        elif not line.strip():
            close_para()
            close_lists()
        else:
            if lists:
                raise BuildError("legal text: continuation lines inside lists aren't supported")
            para.append(line.strip())
    close_para()
    close_lists()
    return "\n".join(out)


def load_nda():
    files = sorted((SRC / "legal").glob("nda-*.md"))
    if not files:
        raise BuildError("src/legal/nda-<version>.md is missing")
    path = max(files, key=lambda f: [int(n) for n in re.findall(r"\d+", f.stem)])
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {"version": path.stem.split("-", 1)[1], "sha256": hashlib.sha256(raw).hexdigest(),
            "text": raw.decode("utf-8")}


# ---------------------------------------------------------------- components

def mark_svg(css_class, label=None, uses=None):
    uses = uses or [("tl", "mark__tl"), ("tr", "mark__tr"), ("bl", "mark__bl"), ("br", "mark__br")]
    a11y = 'role="img" aria-label="%s"' % esc(label) if label else 'aria-hidden="true"'
    inner = "".join('<use href="#m-%s" class="%s"/>' % (pos, cls) for pos, cls in uses)
    return '<svg class="%s" viewBox="{{mark_viewbox}}" %s focusable="false">%s</svg>' % (css_class, a11y, inner)


def badge_svg(extra=""):
    uses = [("tl", "badge__t1"), ("tr", "badge__t2"), ("bl", "badge__t2"), ("br", "badge__t1")]
    return mark_svg(("badge__mark " + extra).strip(), uses=uses)


def status_pill(status):
    return '<span class="status status--%s">%s</span>' % (STATUS_CLASS[status], esc(status))


def c_logo_anim(ctx):
    uses = [(p, "mark__%s logo-anim__c logo-anim__c--%s" % (p, p)) for p in ("tl", "tr", "bl", "br")]
    inner = "".join('<use href="#m-%s" class="%s"/>' % u for u in uses)
    return (
        '<svg class="logo-anim mark mark--master" viewBox="{{mark_viewbox}}" role="img" '
        'aria-label="IT7Q logo: four interlocking circles in cyan, lime, purple and orange" focusable="false">'
        '<g class="logo-anim__spin">%s</g></svg>' % inner
    )


def c_stats(ctx):
    items = []
    for s in ctx["site"]["stats"]:
        label = ' <span class="stat__label">%s</span>' % esc(s["label"]) if s.get("label") else ""
        items.append('<li class="stat"><span class="stat__value">%s</span>%s</li>' % (esc(s["value"]), label))
    return '<ul class="stats" aria-label="IT7Q at a glance">\n%s\n</ul>' % "\n".join(items)


def c_badges(ctx):
    items = []
    for d in ctx["divisions"]:
        items.append(
            '<li><a class="badge d-%s" href="/divisions/%s/">%s'
            '<span class="badge__name">%s</span><span class="badge__tr">%s</span></a></li>'
            % (d["slug"], d["slug"], badge_svg(), esc(d["latin"]), esc(d["translation"]))
        )
    return '<ul class="badges">\n%s\n</ul>' % "\n".join(items)


def c_badge_large(ctx):
    return badge_svg("badge__mark--large")


def c_coming_soon(ctx):
    cs = ctx["site"]["coming_soon"]
    p = ctx["project_index"][cs["project"]]
    return (
        '<article class="soon">'
        '<div class="soon__mark">%s</div>'
        '<div><p class="pill">%s</p>'
        '<h2 id="soon-heading" class="soon__title">%s</h2>'
        '<p>%s</p>'
        '<p class="soon__actions"><a class="btn" href="%s">%s</a> '
        '<a class="link-arrow" href="/divisions/%s/#%s">More from MSP</a></p></div>'
        "</article>"
        % (mark_svg("soon__svg mark mark--master"), esc(p["status"]), esc(p["name"]), esc(p["one_liner"]),
           esc(cs["cta_href"]), esc(cs["cta"]), esc(p["division"]), esc(p["id"].lower()))
    )


def project_card(p, compact=False):
    featured = p.get("featured", False)
    w, h = (1600, 1000) if featured else (800, 500)
    meta = status_pill(p["status"])
    if p.get("note"):
        meta += ' <span class="tag">%s</span>' % esc(p["note"])
    parts = [
        '<article class="pcard%s%s" id="%s">' % (" pcard--featured" if featured else "",
                                                 " pcard--compact" if compact else "", esc(p["id"].lower())),
        '<x-ph id="%s" w="%d" h="%d">%s</x-ph>' % (esc(p["id"]), w, h, esc(p["name"])),
        '<div class="pcard__body">',
        '<p class="pcard__meta">%s</p>' % meta,
        '<h3 class="pcard__title">%s</h3>' % esc(p["name"]),
        "<p>%s</p>" % esc(p["one_liner"]),
    ]
    if p.get("why"):
        parts.append('<p class="pcard__why"><strong>Why it\'s unique:</strong> %s</p>' % esc(p["why"]))
    if p.get("who"):
        parts.append('<p class="pcard__why"><strong>Who it\'s for:</strong> %s</p>' % esc(p["who"]))
    if p.get("public_price"):
        parts.append('<p class="pcard__price">%s</p>' % esc(p["public_price"]))
    if p.get("link"):
        parts.append('<p class="pcard__link"><a class="link-arrow" href="%s">%s</a></p>'
                     % (esc(p["link"]), esc(p.get("link_text", "Find out more"))))
    if p.get("gated", True):
        parts.append(
            '<div class="lock" data-project="%s"><p class="lock__locked">'
            '<a href="/access/?next=/divisions/%s/">Full details under NDA</a></p></div>' % (esc(p["id"]), esc(p["division"]))
        )
    parts.append("</div></article>")
    return "".join(parts)


def c_division_projects(ctx):
    d = ctx["d"]
    projects = [p for p in ctx["projects"] if p["division"] == d["slug"]]
    groups = d.get("groups") or [{"key": None, "title": "Projects"}]
    out = []
    for g in groups:
        items = [p for p in projects if g["key"] is None or p.get("group") == g["key"]]
        items.sort(key=lambda p: not p.get("featured", False))  # stable: featured first, then file order
        compact = g["key"] == "range"
        hid = "g-%s-%s" % (d["slug"], g["key"] or "projects")
        intro = '<p class="section__lead">%s</p>' % esc(g["intro"]) if g.get("intro") else ""
        out.append(
            '<section class="section section--tight" aria-labelledby="%s"><div class="wrap">'
            '<h2 id="%s" class="section__title">%s <span class="count">%d</span></h2>%s'
            '<div class="cards%s">%s</div></div></section>'
            % (hid, hid, esc(g["title"]), len(items), intro, " cards--compact" if compact else "",
               "\n".join(project_card(p, compact) for p in items))
        )
    return "\n".join(out)


def c_division_extra(ctx):
    if ctx["d"]["slug"] != "mentis":
        return ""
    items = "".join(
        '<li><h3 class="list-card__title">%s</h3><p>%s</p></li>' % (esc(a["title"]), esc(a["text"]))
        for a in ctx["services"]["automations"]
    )
    return (
        '<section class="section section--alt" aria-labelledby="automations-heading"><div class="wrap">'
        '<h2 id="automations-heading" class="section__title">AI automations we can set up</h2>'
        '<p class="section__lead">Real automations we run, and can build for your business too.</p>'
        '<ul class="list-cards">%s</ul>'
        '<p><a class="btn" href="/contact/">Talk to us about automation</a></p>'
        "</div></section>" % items
    )


def c_division_list(ctx):
    items = []
    for d in ctx["divisions"]:
        n = sum(1 for p in ctx["projects"] if p["division"] == d["slug"])
        items.append(
            '<li><a class="dcard d-%s" href="/divisions/%s/">%s<span class="dcard__body">'
            '<span class="dcard__name">%s</span><span class="dcard__tr">%s</span>'
            '<span class="dcard__sub">%s</span><span class="dcard__intro">%s</span>'
            '<span class="dcard__count">%d project%s</span></span></a></li>'
            % (d["slug"], d["slug"], badge_svg(), esc(d["latin"]), esc(d["translation"]), esc(d["subtitle"]),
               esc(d["intro"]), n, "" if n == 1 else "s")
        )
    return '<ul class="dcards">\n%s\n</ul>' % "\n".join(items)


def portfolio_card(e, heading="h3", with_id=True):
    current = e["client"] == "current"
    meta = '<span class="tag">%s</span>' % ("Current client" if current else "Past client")
    if e.get("status"):
        meta += " " + status_pill(e["status"])
    if not e.get("one_liner"):
        raise BuildError("portfolio.json %s: a published entry needs a one_liner" % e["id"])
    text = "<p>%s</p>" % esc(e["one_liner"])
    if current and e.get("link"):
        host = re.sub(r"^https://|/$", "", e["link"])
        link = '<a class="link-arrow" href="%s" rel="noopener">Visit %s</a>' % (esc(e["link"]), esc(host))
    elif e.get("snapshot_live"):
        link = '<a class="link-arrow" href="%s" rel="noopener">View the portfolio snapshot</a>' % esc(e["link"])
    else:
        link = '<span class="muted">Portfolio snapshot coming soon</span>'
    return (
        '<article class="pcard pfcard"%s><x-ph id="%s" w="1600" h="1000">%s website screenshot</x-ph>'
        '<div class="pcard__body"><p class="pcard__meta">%s</p><%s class="pcard__title">%s</%s>%s'
        '<p class="pfcard__link">%s</p></div></article>'
        % (' id="%s"' % esc(e["id"]) if with_id else "", esc(e["image"]), esc(e["name"]), meta,
           heading, esc(e["name"]), heading, text, link)
    )


def published_portfolio(ctx):
    return [e for e in ctx["portfolio"] if e.get("published") is True]


def c_portfolio(ctx):
    entries = published_portfolio(ctx)
    out = []
    for kind, title, lead in (
        ("current", "Current clients", "Sites we're building and looking after now."),
        ("past", "Past clients", "Earlier work. Each site is kept as a portfolio snapshot: a frozen copy with its forms "
                                 "switched off, so you can see what we built."),
    ):
        items = [e for e in entries if e["client"] == kind]
        if items:
            out.append(
                '<section class="section section--tight" aria-labelledby="pf-%s"><div class="wrap">'
                '<h2 id="pf-%s" class="section__title">%s</h2><p class="section__lead">%s</p>'
                '<div class="cards">%s</div></div></section>'
                % (kind, kind, title, lead, "\n".join(portfolio_card(e) for e in items))
            )
    return "\n".join(out)


def c_portfolio_highlight(ctx):
    index = {e["id"]: e for e in published_portfolio(ctx)}
    picks = [index[i] for i in ctx["site"]["portfolio_highlight"] if i in index]
    return '<div class="cards">%s</div>' % "\n".join(portfolio_card(e, with_id=False) for e in picks)


def c_services(ctx):
    slugs = {d["slug"]: d for d in ctx["divisions"]}
    out = []
    for g in ctx["services"]["groups"]:
        cards = []
        for s in g["items"]:
            target = s["division"]
            if target == "portfolio":
                href, label, cls = "/portfolio/", "See websites we've built", ""
            else:
                d = slugs[target]
                href, label, cls = "/divisions/%s/" % target, "More from %s" % d["latin"], " d-%s" % target
            cards.append(
                '<li class="scard%s"><h3 class="scard__title">%s</h3><p>%s</p>'
                '<a class="link-arrow" href="%s">%s</a></li>' % (cls, esc(s["title"]), esc(s["text"]), href, esc(label))
            )
        out.append(
            '<section class="section section--tight" aria-labelledby="svc-%s"><div class="wrap">'
            '<h2 id="svc-%s" class="section__title">%s</h2><ul class="scards">%s</ul></div></section>'
            % (g["key"], g["key"], esc(g["title"]), "".join(cards))
        )
    return "\n".join(out)


def c_service_steps(ctx):
    items = "".join(
        '<li><h3 class="steps__title">%s</h3><p>%s</p></li>' % (esc(s["title"]), esc(s["text"]))
        for s in ctx["services"]["steps"]
    )
    return '<ol class="steps">%s</ol>' % items


def c_testimonials(ctx):
    entries = ctx["testimonials"]
    if not entries:
        return ""
    figs = []
    for e in entries:
        who = ", ".join(esc(e[k]) for k in ("name", "business") if str(e.get(k, "")).strip())
        figs.append(
            '<figure class="quote"><blockquote><p>%s</p></blockquote><figcaption>%s</figcaption></figure>'
            % (esc(e["quote"]), who)
        )
    return (
        '<section class="section" aria-labelledby="testimonials-heading"><div class="wrap">'
        '<h2 id="testimonials-heading" class="section__title">What our clients say</h2>'
        '<div class="quotes">%s</div></div></section>' % "\n".join(figs)
    )


def c_footer_social(ctx):
    items = "".join('<li><a href="%s" rel="noopener me">%s</a></li>' % (esc(s["href"]), esc(s["label"]))
                    for s in shown_social(ctx["site"]))  # no URL yet, or hidden: not shown (§2)
    return '<ul class="plain social" aria-label="IT7Q on social media">%s</ul>' % items if items else ""


def c_resources(ctx):
    items = []
    for e in ctx["resources"]["entries"]:
        host = e["domain"]
        guide = ""
        if e.get("guide") and guide_ready(ctx["guides"][e["guide"]]):
            guide = ' <a class="link-arrow" href="/resources/guides/%s/">IT7Q guide</a>' % esc(e["guide"])
        items.append(
            '<li class="rcard"><h3 class="rcard__title">%s</h3>'
            '<p><strong>What it is:</strong> %s</p><p><strong>Why use it:</strong> %s</p>'
            '<p class="rcard__actions"><a class="btn btn--small" href="%s" rel="noopener noreferrer" data-download="official">'
            'Download<span class="visually-hidden"> %s</span></a>%s</p>'
            '<p class="rcard__src">From the official site, %s</p></li>'
            % (esc(e["name"]), esc(e["what"]), esc(e["why"]), esc(e["download"]), esc(e["name"]), guide, esc(host))
        )
    return '<ul class="rcards">%s</ul>' % "\n".join(items)


def guide_ready(g):
    """A guide gets its page and links only once Chris's .md or .pdf is in src/guides/."""
    return g["md"] or g["pdf"]


def guide_status(g):
    if guide_ready(g):
        return '<span class="status status--done">Available</span>'
    return status_pill("Coming soon")


def c_guides(ctx):
    out = []
    for section in ctx["guides_data"]["sections"]:
        cards = []
        for item in section["guides"]:
            g = ctx["guides"][item["slug"]]
            chapter = '<span class="tag">Chapter %d</span> ' % g["chapter"] if g.get("chapter") else ""
            links = ""
            if guide_ready(g):
                pdf = ""
                if g["pdf"]:
                    pdf = ' <a class="link-arrow" href="/%s/%s.pdf" download>PDF</a>' % (GUIDE_PDF_DIR, esc(g["slug"]))
                links = ('<p class="gcard__links"><a class="link-arrow" href="/resources/guides/%s/">Read in browser</a>%s</p>'
                         % (esc(g["slug"]), pdf))
            cards.append(
                '<li class="gcard%s"><p class="pcard__meta">%s%s</p><h4 class="gcard__title">%s</h4><p>%s</p>%s</li>'
                % ("" if guide_ready(g) else " gcard--soon", chapter, guide_status(g), esc(g["title"]),
                   esc(g["summary"]), links)
            )
        out.append(
            '<h3 id="guides-%s" class="guides__title">%s</h3><p class="section__lead">%s</p><ul class="gcards">%s</ul>'
            % (esc(section["key"]), esc(section["title"]), esc(section["intro"]), "".join(cards))
        )
    return "\n".join(out)


def c_guide_actions(ctx):
    g = ctx["g"]
    if not g["pdf"]:
        return '<p class="guide-actions">%s</p>' % status_pill("Coming soon")
    href = "/%s/%s.pdf" % (GUIDE_PDF_DIR, esc(g["slug"]))
    return ('<p class="guide-actions"><a class="btn" href="%s">View the PDF</a> '
            '<a class="btn btn--outline" href="%s" download>Download PDF</a></p>' % (href, href))


def c_guide_body(ctx):
    g = ctx["g"]
    if g["md"]:
        text = (GUIDES_SRC / (g["slug"] + ".md")).read_text(encoding="utf-8")
        return '<div class="legal-text">%s</div>' % render_md(text, top=2)
    return "<p>This guide is a PDF. Use the buttons above to read it in your browser or save a copy.</p>"


def c_credentials(ctx):
    entries = ctx["credentials"]
    if not entries:
        raise BuildError("credentials page built with no entries")
    items = []
    for e in entries:
        meta = " · ".join(esc(e[k]) for k in ("issuer", "year") if str(e.get(k, "")).strip())
        extra = ' <span class="tag">In progress</span>' if e.get("in_progress") else ""
        items.append('<li><h3 class="list-card__title">%s%s</h3>%s</li>'
                     % (esc(e["title"]), extra, "<p>%s</p>" % meta if meta else ""))
    return '<ul class="list-cards credentials">%s</ul>' % "".join(items)


def c_credentials_link(ctx):
    return '<li><a href="/credentials/">Credentials</a></li>' if ctx["credentials"] else ""


def c_credentials_about(ctx):
    if not ctx["credentials"]:
        return ""
    return '<p><a class="link-arrow" href="/credentials/">Qualifications and certifications</a></p>'


def c_nda_text(ctx):
    return '<div class="legal-text">%s</div>' % render_md(ctx["nda"]["text"], top=2)


def c_nda_text_embedded(ctx):
    return (
        '<div class="legal-text legal-text--scroll" id="nda-text" tabindex="0" role="region" aria-label="NDA text">%s</div>'
        % render_md(ctx["nda"]["text"], top=3)
    )


def c_nda_meta(ctx):
    return (
        '<p class="legal-meta">Version %s &middot; Fingerprint (SHA-256): <code class="hash">%s</code></p>'
        % (esc(ctx["nda"]["version"]), esc(ctx["nda"]["sha256"]))
    )


def load_legal(nda):
    """Last-updated dates for the legal texts (src/data/legal.json); every NDA version needs one."""
    legal = load_json("legal.json")
    dates = {"privacy": legal["privacy"], "terms": legal["terms"], "nda": legal["nda"].get(nda["version"])}
    if not dates["nda"]:
        raise BuildError("src/data/legal.json: no date for NDA version %s" % nda["version"])
    out = {}
    for doc, value in dates.items():
        try:
            d = datetime.date.fromisoformat(value)
        except ValueError:
            raise BuildError("src/data/legal.json: %s date %r is not YYYY-MM-DD" % (doc, value))
        out[doc] = "%d %s" % (d.day, d.strftime("%B %Y"))
    return out


def c_legal_updated(ctx):
    doc = ctx["meta"].get("legal_doc", "")
    if doc not in ctx["legal"]:
        raise BuildError("legal_updated: page needs legal_doc: privacy, terms or nda")
    return '<p class="legal-meta">Last updated: %s</p>' % esc(ctx["legal"][doc])


def nda_quote(ctx, text):
    """A phrase quoted word for word from the current NDA (the build fails if the NDA doesn't say it)."""
    plain = " ".join(ctx["nda"]["text"].replace("**", "").split())
    if " ".join(text.split()) not in plain:
        raise BuildError("nda_explainer: the NDA %s doesn't say %r; update the box" % (ctx["nda"]["version"], text))
    return "<q>%s</q>" % esc(text)


def c_nda_explainer(ctx):
    """"How access works" (§4.3): plain English, with the NDA's terms quoted from its own text."""
    q = lambda t: nda_quote(ctx, t)  # noqa: E731
    on_access_page = ctx["meta"].get("nda_explainer") == "access"
    read = ('Read <a href="#nda-text">the full NDA below</a> before you sign. You can also '
            '<a href="/legal/nda/">open it on its own page</a>.' if on_access_page else
            'The full NDA is below. To sign it, use the form on the '
            '<a href="/access/#request-heading">investors &amp; partners page</a>.')
    return (
        '<div class="panel-box nda-explainer">'
        '<h2 class="nda-explainer__title">How access works</h2>'
        '<ol class="mini-steps">'
        "<li>You read the NDA and request access by signing it online.</li>"
        "<li>We review every request manually, usually within a few business days.</li>"
        "<li>If we approve it, we email you a login.</li>"
        "<li>You log in, and the full project details unlock.</li>"
        "</ol>"
        "<h3>Why project details are locked</h3>"
        "<p>The detailed information about our projects is confidential. We only share it under a "
        "non-disclosure agreement (NDA).</p>"
        "<h3>What you agree to</h3>"
        "<p>In plain English: keep it confidential, use it only to consider working with or investing in "
        "IT7Q, and don't copy or share it. In the NDA's own words, you agree to:</p>"
        "<ul>"
        "<li>%s;</li>"
        "<li>%s, which is %s;</li>"
        "<li>%s; and</li>"
        "<li>%s.</li>"
        "</ul>"
        "<p>You can share it with your own employees or professional advisers only if they need it for the "
        "Purpose and are bound by confidentiality duties at least as strict (clause 4).</p>"
        "<h3>How long it lasts</h3>"
        "<ul>"
        "<li>The agreement %s from when you accept it (the <em>Term</em>).</li>"
        "<li>%s. IT7Q can also end access earlier (clause 6).</li>"
        "<li>Confidentiality continues after that: for trade secrets, %s, and for everything else, %s.</li>"
        "</ul>"
        "<p>%s</p>"
        "</div>"
        % (q("keep the Confidential Information confidential"),
           q("use it only for the Purpose"),
           q("to consider a possible investment, partnership, customer or supplier relationship, or other "
             "business dealing with IT7Q"),
           q("not copy, download, screenshot, record or reproduce it, except as reasonably needed for the Purpose"),
           q("not share your login, or let anyone else use your access"),
           q("runs for three (3) years"),
           q("Your access to the protected area ends when the Term ends"),
           q("for as long as it remains a trade secret"),
           q("for two (2) years after the Term ends"),
           read)
    )


def c_nda_bar(ctx):
    division = ctx["d"]["slug"] if ctx.get("d") else ctx["meta"].get("nda_division", "")
    if division not in ctx["lock_divisions"]:
        raise BuildError("nda_bar: unknown division %r" % division)
    return (
        '<div class="nda-bar" data-division="%s" hidden><div class="wrap nda-bar__inner">'
        '<p class="nda-bar__msg" role="status" aria-live="polite"></p>'
        '<button class="btn btn--small btn--outline nda-bar__retry" type="button" hidden>Try again</button>'
        '<button class="btn btn--small btn--outline nda-bar__logout" type="button">Log out</button>'
        "</div></div>" % esc(division)
    )


def form_field(key, f, ctx):
    fid = "f-%s-%s" % (key.replace("_", "-"), f["name"])
    req = f.get("required", False)
    attrs = ['id="%s"' % fid, 'name="%s"' % esc(f["name"])]
    if req:
        attrs.append("required")
    if f.get("max"):
        attrs.append('maxlength="%d"' % f["max"])
    if f.get("autocomplete"):
        attrs.append('autocomplete="%s"' % esc(f["autocomplete"]))
    if f.get("match"):
        attrs.append('data-match="f-%s-%s"' % (key.replace("_", "-"), esc(f["match"])))
    described = []
    hint = ""
    if f.get("hint"):
        hint = '<p class="field__hint" id="%s-hint">%s</p>' % (fid, esc(f["hint"]))
        described.append(fid + "-hint")
    described.append(fid + "-err")
    attrs.append('aria-describedby="%s"' % " ".join(described))
    error = '<p class="field__error" id="%s-err" hidden></p>' % fid
    label_text = esc(f["label"])
    if f.get("link"):
        label_text = label_text.replace(
            "{link}", '<a href="%s">%s</a>' % (esc(f["link"]["href"]), esc(f["link"]["text"])))
    star = ' <span class="field__req" aria-hidden="true">*</span>' if req else ""
    a = " ".join(attrs)
    if f["type"] == "checkbox":
        return ('<div class="field field--check"><input type="checkbox" value="yes" %s>'
                '<label for="%s">%s%s</label>%s%s</div>' % (a, fid, label_text, star, hint, error))
    if f["type"] == "textarea":
        control = '<textarea rows="5" %s></textarea>' % a
    elif f["type"] == "select":
        opts = list(f.get("options", []))
        if f.get("options_from") == "divisions":
            opts += [{"value": d["slug"], "label": "%s (%s)" % (d["latin"], d["translation"])} for d in ctx["divisions"]]
        control = "<select %s>%s</select>" % (a, "".join(
            '<option value="%s">%s</option>' % (esc(o["value"]), esc(o["label"])) for o in opts))
        if req:  # force a real choice
            control = control.replace(">", '><option value="">Choose one</option>', 1)
    else:
        control = '<input type="%s" %s>' % (esc(f["type"]), a)
    return ('<div class="field"><label for="%s">%s%s</label>%s%s%s</div>'
            % (fid, label_text, star, hint, control, error))


def render_form(key, ctx):
    spec = ctx["forms"][key]
    fid = "f-%s" % key.replace("_", "-")
    fields = "\n".join(form_field(key, f, ctx) for f in spec["fields"])
    return (
        '<noscript><p class="note">This form needs JavaScript. You can also call '
        '<a href="{{site.phone_href}}">{{site.phone}}</a> or email <a href="mailto:{{site.email}}">{{site.email}}</a>.</p></noscript>'
        '<form class="form needs-js" id="%s" data-form="%s" data-hook="%s" data-turnstile-action="%s" '
        'data-success="%s" novalidate>'
        '<div class="form__fields">%s'
        '<div class="hp" aria-hidden="true"><label for="%s-website">Leave this empty</label>'
        '<input type="text" id="%s-website" name="website" tabindex="-1" autocomplete="off"></div>'
        '<div class="turnstile" data-for="%s"></div>'
        '<p class="form__note">Fields marked <span aria-hidden="true">*</span><span class="visually-hidden">with a star</span> are required.</p>'
        '<button class="btn" type="submit">%s</button></div>'
        '<div class="form__status" role="status" aria-live="polite" tabindex="-1" hidden></div>'
        "</form>"
        % (fid, key, esc(spec["hook"]), esc(spec["turnstile_action"]), esc(spec["success"]), fields,
           fid, fid, key, esc(spec["submit"]))
    )


def c_form_nda_request(ctx):
    return render_form("nda_request", ctx)


def c_form_nda_login(ctx):
    return render_form("nda_login", ctx)


def c_form_enquiry(ctx):
    return render_form("enquiry", ctx)


def c_stub(ctx):
    return '<p class="stub-note">This page is being built. Full content arrives in the next phase.</p>'


COMPONENTS = {
    "logo_anim": c_logo_anim,
    "stats": c_stats,
    "badges": c_badges,
    "badge_large": c_badge_large,
    "coming_soon": c_coming_soon,
    "division_projects": c_division_projects,
    "division_extra": c_division_extra,
    "division_list": c_division_list,
    "portfolio": c_portfolio,
    "portfolio_highlight": c_portfolio_highlight,
    "services": c_services,
    "service_steps": c_service_steps,
    "testimonials": c_testimonials,
    "nda_text": c_nda_text,
    "nda_text_embedded": c_nda_text_embedded,
    "nda_meta": c_nda_meta,
    "legal_updated": c_legal_updated,
    "nda_explainer": c_nda_explainer,
    "nda_bar": c_nda_bar,
    "form_nda_request": c_form_nda_request,
    "form_nda_login": c_form_nda_login,
    "form_enquiry": c_form_enquiry,
    "stub": c_stub,
    "footer_social": c_footer_social,
    "resources": c_resources,
    "guides": c_guides,
    "guide_actions": c_guide_actions,
    "guide_body": c_guide_body,
    "credentials": c_credentials,
    "credentials_link": c_credentials_link,
    "credentials_about": c_credentials_about,
}


# ---------------------------------------------------------------- rendering

def lookup(ctx, dotted, where):
    value = ctx
    for part in dotted.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise BuildError("%s: unknown variable {{%s}}" % (where, dotted))
    if isinstance(value, (dict, list)):
        raise BuildError("%s: {{%s}} is not a plain value" % (where, dotted))
    return value


def render_components(text, ctx, where):
    def sub(m):
        name = m.group(1)
        if name not in COMPONENTS:
            raise BuildError("%s: unknown component {{> %s}}" % (where, name))
        return COMPONENTS[name](ctx)
    return re.sub(r"\{\{>\s*(\w+)\s*\}\}", sub, text)


def render_vars(text, ctx, where, escape=True):
    def sub(m):
        value = lookup(ctx, m.group(1), where)
        return esc(value) if escape else str(value)
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", sub, text)


# ---------------------------------------------------------------- artwork
# Every <x-ph> image slot is drawn as on-brand SVG artwork until a real photo or render exists.
# The image id stays on the element (data-img) and the box keeps its aspect ratio, so the photo
# replaces it later with no layout change. Colours come from CSS (tokens.css), never hex here.
TIER_NAME = re.compile(r"^T(\d) ")


def art_specs(projects, portfolio):
    """Image id -> how to draw it. Ids not listed (about, shop) get IT7Q brand artwork."""
    specs = {}
    for p in projects:
        tier = TIER_NAME.match(p["name"])
        if p["division"] == "tempestas" and tier:
            kind = "shield"
        elif p["division"] == "fabricus" and p.get("group") == "range":
            kind = "soon"
        else:
            kind = "project"
        specs[p["id"]] = {"kind": kind, "d": p["division"], "name": p["name"],
                          "tier": int(tier.group(1)) if tier else 0}
    for e in portfolio:
        specs[e["image"]] = {"kind": "client", "name": e["name"]}
    return specs


def _seed(pid, n):
    return int(hashlib.sha256(pid.encode()).hexdigest()[:8], 16) % n


def _mark_at(x, y, size, uses, css="", transform=""):
    """The four circle shapes (sprite #m-*), as a size x size square at x, y."""
    inner = "".join('<use href="#m-%s" class="%s"/>' % u for u in uses)
    t = ' transform="%s"' % transform if transform else ""
    return ('<g%s%s><svg x="%g" y="%g" width="%g" height="%g" viewBox="{{mark_viewbox}}">%s</svg></g>'
            % (' class="%s"' % css if css else "", t, x, y, size, size, inner))


BADGE_USES = [("tl", "badge__t1"), ("tr", "badge__t2"), ("bl", "badge__t2"), ("br", "badge__t1")]
MASTER_USES = [("tl", "mark__tl"), ("tr", "mark__tr"), ("bl", "mark__bl"), ("br", "mark__br")]


def _art_svg(w, h, inner):
    return ('<svg class="art__svg" viewBox="0 0 %d %d" preserveAspectRatio="xMidYMid slice" aria-hidden="true" '
            'focusable="false">%s</svg>' % (w, h, inner))


def art_project(pid, w, h):
    """Division badge on division-coloured abstract circles."""
    turn = (_seed(pid, 8) - 4) * 9
    big = h * 1.35
    deco = (_mark_at(w * 0.52 + _seed(pid, 7) * h * 0.04, -h * 0.3, big, BADGE_USES, "art__deco",
                     "rotate(%d %g %g)" % (turn, w * 0.52 + big / 2, -h * 0.3 + big / 2))
            + _mark_at(-h * 0.25, h * 0.5, h * 0.75, BADGE_USES, "art__deco art__deco--faint"))
    size = h * 0.46
    rings = "".join('<circle class="art__ring" cx="%g" cy="%g" r="%g"/>' % (w / 2, h / 2, size * k) for k in (0.68, 0.9))
    return _art_svg(w, h, deco + rings + _mark_at((w - size) / 2, (h - size) / 2, size, BADGE_USES))


SHIELD_OUTER = "M50 3 L94 15 V50 C94 84 73 104 50 117 C27 104 6 84 6 50 V15 Z"
SHIELD_FIELD = "M50 11 L86 21 V50 C86 79 68 96 50 107 C32 96 14 79 14 50 V21 Z"


def art_shield(pid, w, h, tier, clip_id):
    """A plain heraldic shield: one chevron per tier. No prices or specs, ever (gated, §4.9)."""
    sh = h * 0.8
    sw = sh * 100 / 120
    chevrons = "".join('<polyline class="art__chev" points="18,%d 50,%d 82,%d"/>' % (y + 10, y - 6, y + 10)
                       for y in (60 + 10 * i for i in range(tier)))
    rivets = "".join('<circle class="art__rivet" cx="%g" cy="%g" r="1.8"/>' % xy
                     for xy in ((10, 18), (90, 18), (50, 7), (10, 48), (90, 48), (50, 112)))
    shield = (
        '<svg x="%g" y="%g" width="%g" height="%g" viewBox="0 0 100 120">'
        '<defs><clipPath id="%s"><path d="%s"/></clipPath></defs>'
        '<path class="art__shield-rim" d="%s"/><path class="art__shield-field" d="%s"/>'
        '<g clip-path="url(#%s)"><rect class="art__shield-half" x="50" y="0" width="50" height="120"/>%s</g>'
        '%s%s</svg>'
        % ((w - sw) / 2, (h - sh) / 2, sw, sh, clip_id, SHIELD_FIELD, SHIELD_OUTER, SHIELD_FIELD, clip_id,
           chevrons, rivets, _mark_at(39, 24, 22, BADGE_USES))
    )
    rings = "".join('<circle class="art__ring" cx="%g" cy="%g" r="%g"/>' % (w / 2, h / 2, sh * k) for k in (0.55, 0.72))
    return _art_svg(w, h, _mark_at(w * 0.6, -h * 0.35, h * 1.4, BADGE_USES, "art__deco art__deco--faint") + rings + shield)


def art_brand(pid, w, h):
    """IT7Q master mark on soft circles in the four business-card colours."""
    corners = [("tl", "mark__tl"), ("tr", "mark__tr"), ("bl", "mark__bl"), ("br", "mark__br")]
    k = _seed(pid, 4)
    first, second = corners[k], corners[(k + 2) % 4]
    deco = (_mark_at(w * 0.55, -h * 0.35, h * 1.4, [first], "art__deco mark--master")
            + _mark_at(-h * 0.3, h * 0.35, h * 1.1, [second], "art__deco mark--master"))
    size = h * 0.42
    return _art_svg(w, h, deco + _mark_at((w - size) / 2, (h - size) / 2, size, MASTER_USES, "mark--master"))


CAMERA = ('<svg class="art__icon" viewBox="0 0 48 40" aria-hidden="true" focusable="false">'
          '<path d="M6 10h9l4-6h10l4 6h9a3 3 0 0 1 3 3v21a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V13a3 3 0 0 1 3-3z"/>'
          '<circle cx="24" cy="23" r="8"/></svg>')


def render_placeholders(text, where, specs=None):
    specs = specs or {}
    clips = iter(range(1, 10000))

    def sub(m):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        label = html.unescape(m.group(2).strip())  # components pass escaped text; escape exactly once below
        try:
            pid, w, h = attrs["id"], int(attrs["w"]), int(attrs["h"])
        except (KeyError, ValueError):
            raise BuildError("%s: <x-ph> needs id, w and h" % where)
        g = gcd(w, h)
        ratio = PH_RATIOS.get((w // g, h // g))
        if not ratio:
            raise BuildError("%s: no image style for %dx%d" % (where, w, h))
        spec = specs.get(pid, {"kind": "brand"})
        kind, name = spec["kind"], spec.get("name", label)
        cls = "art art--%s ph--%s" % (kind, ratio) + (" d-%s" % spec["d"] if spec.get("d") else "")
        if kind == "shield":
            aria, inner = "%s: illustrated TEMPESTAS shield" % name, art_shield(pid, w, h, spec["tier"],
                                                                               "art-clip-%d" % next(clips))
        elif kind == "project":
            aria, inner = "%s: %s artwork" % (name, spec["d"].upper()), art_project(pid, w, h)
        elif kind == "soon":
            aria = "Photo coming soon: %s" % name
            inner = '%s<span class="art__soon">Photo coming soon</span>' % CAMERA
        elif kind == "client":
            aria = "%s: IT7Q client" % name
            inner = ('<span class="art__client">%s<span class="art__name">%s</span>'
                     '<span class="art__by">Website by IT7Q</span></span>'
                     % (mark_svg("art__mark mark mark--master"), esc(name)))
        else:
            aria, inner = "IT7Q artwork", art_brand(pid, w, h)
        return '<div class="%s" role="img" aria-label="%s" data-img="%s">%s</div>' % (cls, esc(aria), esc(pid), inner)
    return re.sub(r"<x-ph\s+([^>]*)>(.*?)</x-ph>", sub, text, flags=re.S)


def page_scripts(meta, where):
    names = meta.get("scripts", "").split()
    for n in names:
        if n not in PROD_SCRIPTS:
            raise BuildError("%s: unknown script %r (allowed: %s)" % (where, n, ", ".join(PROD_SCRIPTS)))
    if "nda" in names and "forms" not in names:
        names.insert(0, "forms")  # nda.js builds on forms.js
    if not names:
        return ""
    srcs = ["config"] + [n for n in PROD_SCRIPTS if n in names]
    return "\n".join('  <script src="/assets/js/%s.js" defer></script>' % s for s in srcs)


def render_page(meta, body, ctx, partials, nav_key, where):
    ctx = dict(ctx, meta=meta)
    body = render_components(body, ctx, where)
    body = render_placeholders(body, where, ctx.get("art"))
    nav_items = "\n".join(
        '        <li><a href="%s"%s>%s</a></li>'
        % (esc(n["href"]), ' aria-current="page"' if n["key"] == nav_key else "", esc(n["label"]))
        for n in ctx["site"]["nav"]
    )
    title = meta["title"] if meta.get("full_title") == "true" else "%s | IT7Q" % meta["title"]
    page = partials["layout"]
    for key, value in (
        ("{{header}}", partials["header"].replace("{{nav_items}}", nav_items)),
        ("{{footer}}", render_components(partials["footer"], ctx, "partials/footer.html")),
        ("{{sprite}}", ctx["sprite"]),
        ("{{content}}", body),
        ("{{page_title}}", esc(title)),
        ("{{description}}", esc(meta["description"])),
        ("{{page_scripts}}", page_scripts(meta, where)),
    ):
        page = page.replace(key, value)
    page = render_vars(page, ctx, where)
    leftover = re.search(r"\{\{.*?\}\}|<x-ph", page)
    if leftover:
        raise BuildError("%s: unresolved template text %r" % (where, leftover.group(0)))
    return page


# ---------------------------------------------------------------- assets

def load_mark():
    svg = (SRC / "assets/img/brand/mark.svg").read_text(encoding="utf-8")
    viewbox = re.search(r'viewBox="([^"]+)"', svg).group(1)
    paths = re.findall(r"<path [^>]*/>", svg)
    if len(paths) != 4:
        raise BuildError("mark.svg must hold exactly four paths")
    sprite = '<svg class="sprite" aria-hidden="true" focusable="false"><defs>%s</defs></svg>' % "".join(paths)
    favicon_paths = "".join(
        p.replace("<path ", '<path fill="%s" ' % MASTER_COLOURS[re.search(r'id="m-(\w+)"', p).group(1)], 1)
        .replace(re.search(r' id="[^"]+"', p).group(0), "")
        for p in paths
    )
    size = viewbox.split()[2]
    favicon = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s">'
        '<rect width="%s" height="%s" rx="120" fill="#0D1B2A"/>%s</svg>\n' % (viewbox, size, size, favicon_paths)
    )
    return svg, viewbox, sprite, favicon


def fonts_css():
    rules = []
    for name, family, weight, style in FONT_FILES:
        if (SRC / "assets/fonts" / name).exists():
            rules.append(
                "@font-face { font-family: \"%s\"; font-weight: %s; font-style: %s; "
                "font-display: swap; src: url(\"/assets/fonts/%s\") format(\"truetype\"); }"
                % (family, weight, style, name)
            )
    if not rules:
        return "/* No self-hosted font files (Q40): system fonts are used. */\n"
    return "\n".join(rules) + "\n"


def copy_assets(mark_svg_text, image_opts):
    paths, view_size = pngmark.load_mark_paths(mark_svg_text)
    shipped_fonts = {f[0] for f in FONT_FILES}
    marked = 0
    for src in sorted((SRC / "assets").rglob("*")):
        if src.is_dir() or src.name.startswith("."):
            continue
        rel = src.relative_to(SRC)
        ext = src.suffix.lower()
        if ext in FONT_EXT and src.name not in shipped_fonts:
            continue  # unused faces stay out of dist/
        out = DIST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if ext in RASTER_EXT:
            key = str(src.relative_to(SRC / "assets/img")) if (SRC / "assets/img") in src.parents else str(rel)
            corner = image_opts.get(key, {}).get("corner", "br")
            try:
                out.write_bytes(rastermark.watermark(src.read_bytes(), ext, paths, view_size, corner))
            except rastermark.MarkError as e:
                raise BuildError("%s: %s" % (rel, e))
            marked += 1
        else:
            shutil.copyfile(src, out)
    return marked


# ---------------------------------------------------------------- main

def form_keys():
    """forms.json field names per form: forms.js sends these and nothing else (plus its system fields)."""
    forms = load_json("forms.json")
    return {k: {"fields": [f["name"] for f in v["fields"]], "system": v.get("system", [])}
            for k, v in forms.items() if not k.startswith("_")}


def config_js(nda, mock):
    endpoints = load_json("endpoints.json")
    site_key = endpoints["turnstile_site_key"]
    if site_key.startswith("PLACEHOLDER"):
        site_key = ""  # not given yet: forms fail closed, and check.py --launch refuses (LAUNCH.md step 1)
    cfg = {
        "hooks": "/webhook" if mock else endpoints["hooks"],
        "turnstileSiteKey": "mock" if mock else site_key,
        "mock": mock,
        "ndaVersion": nda["version"],
        "ndaSha256": nda["sha256"],
        "forms": form_keys(),
    }
    if not mock and not cfg["turnstileSiteKey"]:
        print("warning: no Turnstile site key yet (endpoints.json); forms stay switched off until it's set (LAUNCH.md step 1)")
    return ("// Generated by tools/build.py. Public values only (PLAN.md §4.1, §4.12).\n"
            "window.IT7Q_CONFIG = Object.freeze(%s);\n" % json.dumps(cfg, sort_keys=True))


def headers_text():
    """src/_headers with the webhook origin from endpoints.json in the CSP (Q58: one config value)."""
    hooks = load_json("endpoints.json")["hooks"]
    text = (SRC / "_headers").read_text(encoding="utf-8")
    if "{{hooks_origin}}" not in text:
        raise BuildError("src/_headers: the CSP must use {{hooks_origin}}")
    return text.replace("{{hooks_origin}}", check.origin(hooks))


def hash_assets():
    """Rename dist/ CSS and JS to name.<hash>.ext and point every page at the new names.
    src/_headers caches these for a year; a changed file gets a new name, so no purge is needed."""
    names = {}
    for d in check.HASHED_DIRS:
        for f in sorted((DIST / d).glob("*")):
            if f.suffix in (".css", ".js"):
                new = f.with_name("%s.%s%s" % (f.stem, check.content_hash(f.read_bytes()), f.suffix))
                f.rename(new)
                names['"/%s/%s"' % (d, f.name)] = '"/%s/%s"' % (d, new.name)
    for page in DIST.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        for old, new in names.items():
            text = text.replace(old, new)
        page.write_text(text, encoding="utf-8")
    return len(names)


def render_template_pages(name, items, base_ctx, partials, outputs):
    tmpl = (SRC / "templates" / name).read_text(encoding="utf-8")
    for rel, ctx in items:
        if rel in outputs:
            raise BuildError("%s exists in src/pages and would clash with templates/%s" % (rel, name))
        ctx = dict(base_ctx, **ctx)
        meta, body = parse_page(tmpl, "templates/" + name)
        meta = {k: render_vars(v, ctx, str(rel), escape=False) for k, v in meta.items()}
        outputs[rel] = render_page(meta, body, ctx, partials, meta.get("nav", ""), str(rel))


def build(mock=False):
    if DIST.exists():
        if DIST.resolve().parent != ROOT or DIST.name != "dist":
            raise BuildError("refusing to delete unexpected path %s" % DIST)
        shutil.rmtree(DIST)
    DIST.mkdir()

    site, divisions, image_opts = load_json("site.json"), load_json("divisions.json"), load_json("images.json")
    projects = load_json("projects.json")
    check_projects(projects, divisions)
    check_social(site)
    guides_data, guides = load_guides()
    resources = load_json("resources.json")
    check_resources(resources, guides)
    mark_text, viewbox, sprite, favicon = load_mark()
    partials = {p.stem: p.read_text(encoding="utf-8") for p in (SRC / "partials").glob("*.html")}
    nda = load_nda()
    base_ctx = {
        "site": site, "divisions": divisions, "sprite": sprite, "mark_viewbox": viewbox,
        "projects": projects, "project_index": {p["id"]: p for p in projects},
        "portfolio": load_json("portfolio.json"), "services": load_json("services.json"),
        "testimonials": approved_testimonials(load_json("testimonials.json")),
        "forms": load_json("forms.json"), "nda": nda, "legal": load_legal(nda),
        "lock_divisions": {d["slug"] for d in divisions} | {"investors"},
        "resources": resources, "guides_data": guides_data, "guides": guides,
        "credentials": check_credentials(load_json("credentials.json")),
    }
    base_ctx["art"] = art_specs(projects, base_ctx["portfolio"])

    outputs = {}
    for src in sorted((SRC / "pages").rglob("*.html")):
        rel = src.relative_to(SRC / "pages")
        meta, body = parse_page(src.read_text(encoding="utf-8"), str(rel))
        if meta.get("needs") and not base_ctx[meta["needs"]]:
            continue  # e.g. Credentials, until Chris's list is in (no placeholder pages)
        outputs[rel] = render_page(meta, body, base_ctx, partials, meta.get("nav", ""), str(rel))

    render_template_pages("division.html", [(Path("divisions", d["slug"], "index.html"), {"d": d}) for d in divisions],
                          base_ctx, partials, outputs)
    render_template_pages("guide.html", [(Path("resources/guides", g, "index.html"), {"g": guides[g]})
                                         for g in guides if guide_ready(guides[g])],
                          base_ctx, partials, outputs)

    for rel, page in outputs.items():
        out = DIST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")

    marked = copy_assets(mark_text, image_opts)
    (DIST / "assets/css/fonts.css").write_text(fonts_css(), encoding="utf-8")
    (DIST / "assets/js/config.js").write_text(config_js(base_ctx["nda"], mock), encoding="utf-8")
    (DIST / "favicon.svg").write_text(favicon, encoding="utf-8")
    (DIST / "_headers").write_text(headers_text(), encoding="utf-8")
    hashed = hash_assets()
    pdfs = [g for g in guides.values() if g["pdf"]]
    for g in pdfs:
        (DIST / GUIDE_PDF_DIR).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(GUIDES_SRC / (g["slug"] + ".pdf"), DIST / GUIDE_PDF_DIR / (g["slug"] + ".pdf"))
    print("built %d pages, %d project cards, %d testimonials, %d watermarked images, %d hashed CSS/JS -> %s%s"
          % (len(outputs), len(projects), len(base_ctx["testimonials"]), marked, hashed, DIST.relative_to(ROOT),
             " (LOCAL MOCK BUILD: do not deploy)" if mock else ""))


def main(argv):
    mock = "--mock" in argv
    try:
        build(mock)
    except BuildError as e:
        print("BUILD FAILED: %s" % e, file=sys.stderr)
        return 1
    if "--no-check" in argv:
        return 0
    return check.main([str(DIST)] + (["--mock"] if mock else []))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
