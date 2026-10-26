#!/usr/bin/env python3
"""Build the IT7Q site: src/ -> dist/ (stdlib only, PLAN.md §3).

    python3 tools/build.py            build, then run tools/check.py
    python3 tools/build.py --no-check build only (for debugging)

Pages are src/pages/**/*.html with a small front-matter block. Templating:
    {{site.key}} / {{d.key}}   escaped value from data
    {{> component}}            generated HTML block (see COMPONENTS)
    <x-ph id w h>text</x-ph>   visible image placeholder
Anything unresolved fails the build. Raster images are watermarked on the way
to dist/ (§5.1); sources in src/ are never modified.
"""
import html
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check  # noqa: E402
import pngmark  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DIST = ROOT / "dist"
RASTER_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff", ".ico"}
FONT_FILES = [  # (file, family, weight)
    ("rajdhani-500.woff2", "Rajdhani", 500),
    ("rajdhani-600.woff2", "Rajdhani", 600),
    ("rajdhani-700.woff2", "Rajdhani", 700),
    ("exo2-400.woff2", "Exo 2", 400),
    ("exo2-600.woff2", "Exo 2", 600),
]
PH_RATIOS = {(16, 9): "16x9", (8, 5): "16x10", (1, 1): "1x1", (40, 21): "og"}
MASTER_COLOURS = {"tl": "#00B4CC", "tr": "#7EC820", "bl": "#8B5CF6", "br": "#F97316"}


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


# ---------------------------------------------------------------- components

def mark_svg(css_class, label=None, uses=None):
    uses = uses or [("tl", "mark__tl"), ("tr", "mark__tr"), ("bl", "mark__bl"), ("br", "mark__br")]
    a11y = 'role="img" aria-label="%s"' % esc(label) if label else 'aria-hidden="true"'
    inner = "".join('<use href="#m-%s" class="%s"/>' % (pos, cls) for pos, cls in uses)
    return '<svg class="%s" viewBox="{{mark_viewbox}}" %s focusable="false">%s</svg>' % (css_class, a11y, inner)


def badge_svg(extra=""):
    uses = [("tl", "badge__t1"), ("tr", "badge__t2"), ("bl", "badge__t2"), ("br", "badge__t1")]
    return mark_svg(("badge__mark " + extra).strip(), uses=uses)


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
    return (
        '<article class="soon">'
        '<div class="soon__mark">%s</div>'
        '<div><p class="pill">%s</p>'
        '<h2 id="soon-heading" class="soon__title">%s</h2>'
        '<p>%s</p>'
        '<p class="soon__actions"><a class="btn" href="%s">%s</a> '
        '<a class="link-arrow" href="/divisions/msp/">More from MSP</a></p></div>'
        "</article>"
        % (mark_svg("soon__svg mark mark--master"), esc(cs["status"]), esc(cs["title"]),
           esc(cs["summary"]), esc(cs["cta_href"]), esc(cs["cta"]))
    )


def c_division_featured(ctx):
    d = ctx.get("d")
    if not d or d["slug"] != "msp":
        return ""
    cs = ctx["site"]["coming_soon"]
    return (
        '<div class="grid grid--3"><article class="card card--soon" id="%s">'
        '<x-ph id="%s" w="800" h="500">%s illustration</x-ph>'
        '<p class="pill">%s</p><h2 class="card__title">%s</h2><p>%s</p>'
        '<a class="link-arrow" href="%s">%s</a></article></div>'
        % (esc(cs["id"].lower()), esc(cs["id"]), esc(cs["title"]), esc(cs["status"]),
           esc(cs["title"]), esc(cs["summary"]), esc(cs["cta_href"]), esc(cs["cta"]))
    )


def c_stub(ctx):
    return '<p class="stub-note">This page is being built. Full content arrives in the next phase.</p>'


COMPONENTS = {
    "logo_anim": c_logo_anim,
    "stats": c_stats,
    "badges": c_badges,
    "badge_large": c_badge_large,
    "coming_soon": c_coming_soon,
    "division_featured": c_division_featured,
    "stub": c_stub,
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


def render_placeholders(text, where):
    def sub(m):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        label = m.group(2).strip()
        try:
            pid, w, h = attrs["id"], int(attrs["w"]), int(attrs["h"])
        except (KeyError, ValueError):
            raise BuildError("%s: <x-ph> needs id, w and h" % where)
        from math import gcd
        g = gcd(w, h)
        ratio = PH_RATIOS.get((w // g, h // g))
        if not ratio:
            raise BuildError("%s: no placeholder style for %dx%d" % (where, w, h))
        text_ = "PLACEHOLDER %s — %s (%d×%d)" % (pid, label, w, h)
        return (
            '<div class="ph ph--%s" role="img" aria-label="%s">'
            '<span class="ph__id">%s</span><span class="ph__text">%s</span></div>'
            % (ratio, esc("Placeholder: " + label), esc(pid), esc(text_))
        )
    return re.sub(r"<x-ph\s+([^>]*)>(.*?)</x-ph>", sub, text, flags=re.S)


def render_page(meta, body, ctx, partials, nav_key, where):
    body = render_components(body, ctx, where)
    body = render_placeholders(body, where)
    nav_items = "\n".join(
        '        <li><a href="%s"%s>%s</a></li>'
        % (esc(n["href"]), ' aria-current="page"' if n["key"] == nav_key else "", esc(n["label"]))
        for n in ctx["site"]["nav"]
    )
    title = meta["title"] if meta.get("full_title") == "true" else "%s | IT7Q" % meta["title"]
    page = partials["layout"]
    for key, value in (
        ("{{header}}", partials["header"].replace("{{nav_items}}", nav_items)),
        ("{{footer}}", partials["footer"]),
        ("{{sprite}}", ctx["sprite"]),
        ("{{content}}", body),
        ("{{page_title}}", esc(title)),
        ("{{description}}", esc(meta["description"])),
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
    for name, family, weight in FONT_FILES:
        if (SRC / "assets/fonts" / name).exists():
            rules.append(
                "@font-face { font-family: \"%s\"; font-weight: %d; font-style: normal; "
                "font-display: swap; src: url(\"/assets/fonts/%s\") format(\"woff2\"); }" % (family, weight, name)
            )
    if not rules:
        return "/* No self-hosted font files yet (PLAN.md Q40): system fonts are used. */\n"
    return "\n".join(rules) + "\n"


def copy_assets(mark_svg_text, image_opts):
    paths, view_size = pngmark.load_mark_paths(mark_svg_text)
    marked = 0
    for src in sorted((SRC / "assets").rglob("*")):
        if src.is_dir() or src.name.startswith("."):
            continue
        rel = src.relative_to(SRC)
        out = DIST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        ext = src.suffix.lower()
        if ext in RASTER_EXT:
            if ext != ".png":
                raise BuildError(
                    "%s: only PNG rasters can be watermarked with the stdlib build (PLAN.md §5.1, Q43)" % rel
                )
            key = str(src.relative_to(SRC / "assets/img")) if (SRC / "assets/img") in src.parents else str(rel)
            corner = image_opts.get(key, {}).get("corner", "br")
            try:
                out.write_bytes(pngmark.watermark(src.read_bytes(), paths, view_size, corner))
            except pngmark.PNGError as e:
                raise BuildError("%s: %s" % (rel, e))
            marked += 1
        else:
            shutil.copyfile(src, out)
    return marked


# ---------------------------------------------------------------- main

def build():
    if DIST.exists():
        if DIST.resolve().parent != ROOT or DIST.name != "dist":
            raise BuildError("refusing to delete unexpected path %s" % DIST)
        shutil.rmtree(DIST)
    DIST.mkdir()

    site, divisions, image_opts = load_json("site.json"), load_json("divisions.json"), load_json("images.json")
    mark_text, viewbox, sprite, favicon = load_mark()
    partials = {p.stem: p.read_text(encoding="utf-8") for p in (SRC / "partials").glob("*.html")}
    base_ctx = {"site": site, "divisions": divisions, "sprite": sprite, "mark_viewbox": viewbox}

    outputs = {}
    for src in sorted((SRC / "pages").rglob("*.html")):
        rel = src.relative_to(SRC / "pages")
        meta, body = parse_page(src.read_text(encoding="utf-8"), str(rel))
        outputs[rel] = render_page(meta, body, base_ctx, partials, meta.get("nav", ""), str(rel))

    tmpl = (SRC / "templates/division.html").read_text(encoding="utf-8")
    for d in divisions:
        rel = Path("divisions", d["slug"], "index.html")
        if rel in outputs:
            raise BuildError("%s exists in src/pages and would clash with the division template" % rel)
        ctx = dict(base_ctx, d=d)
        meta, body = parse_page(tmpl, "templates/division.html")
        meta = {k: render_vars(v, ctx, str(rel), escape=False) for k, v in meta.items()}
        outputs[rel] = render_page(meta, body, ctx, partials, meta.get("nav", ""), str(rel))

    for rel, page in outputs.items():
        out = DIST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")

    marked = copy_assets(mark_text, image_opts)
    (DIST / "assets/css/fonts.css").write_text(fonts_css(), encoding="utf-8")
    (DIST / "favicon.svg").write_text(favicon, encoding="utf-8")
    shutil.copyfile(SRC / "_headers", DIST / "_headers")
    print("built %d pages, %d watermarked images -> %s" % (len(outputs), marked, DIST.relative_to(ROOT)))


def main(argv):
    try:
        build()
    except BuildError as e:
        print("BUILD FAILED: %s" % e, file=sys.stderr)
        return 1
    if "--no-check" in argv:
        return 0
    return check.main([str(DIST)])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
