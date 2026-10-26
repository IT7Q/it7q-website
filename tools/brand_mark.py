#!/usr/bin/env python3
"""One-off: derive src/assets/img/brand/mark.svg from a brand-pack emblem SVG.

Keeps only the four circle shapes (drops the ring and every pack colour),
simplifies the traced outlines and writes them as colourless <symbol>s.
Colours come from the site CSS (business-card palette, PLAN.md §1).

Usage: python3 -I tools/brand_mark.py <IT7Q_emblem_full-colour.svg> <out.svg>
"""
import re
import sys

# Pack path id -> position on the emblem (checked against bounding boxes below)
CIRCLES = {
    "circle_navy": "tl",
    "circle_gold": "tr",
    "circle_red": "bl",
    "circle_orange": "br",
}
EPSILON = 0.6      # Ramer-Douglas-Peucker tolerance, in emblem units (viewBox ~708 wide)
MIN_AREA = 25.0    # drop trace specks smaller than this (square units)


def parse_subpaths(d):
    if re.search(r"[^MLZ0-9.\s-]", d):
        raise ValueError("unexpected path command; only absolute M/L/Z supported")
    subpaths = []
    for chunk in d.split("M")[1:]:
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", chunk)]
        pts = list(zip(nums[0::2], nums[1::2]))
        subpaths.append(pts)
    return subpaths


def area(pts):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))) / 2


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    dx, dy = x1 - x0, y1 - y0
    norm = (dx * dx + dy * dy) ** 0.5 or 1e-9
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        dist = abs(dy * px - dx * py + x1 * y0 - y1 * x0) / norm
        if dist > dmax:
            dmax, idx = dist, i
    if dmax <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[: idx + 1], eps)[:-1] + rdp(pts[idx:], eps)


def main(src, out):
    svg = open(src, encoding="utf-8").read()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    ox, oy, size = vb[0], vb[1], vb[2]
    symbols, stats = [], []
    for pid, pos in CIRCLES.items():
        d = re.search(r'<path id="%s"[^>]* d="([^"]+)"' % pid, svg).group(1)
        kept = []
        for pts in parse_subpaths(d):
            if area(pts) < MIN_AREA:
                continue
            # Closed loop: split at the middle so RDP never sees a zero-length baseline
            mid = len(pts) // 2
            simple = rdp(pts[: mid + 1], EPSILON)[:-1] + rdp(pts[mid:] + [pts[0]], EPSILON)[:-1]
            if len(simple) >= 3:
                kept.append(simple)
        xs = [x for sp in kept for x, _ in sp]
        ys = [y for sp in kept for _, y in sp]
        cx, cy = (min(xs) + max(xs)) / 2 - ox, (min(ys) + max(ys)) / 2 - oy
        stats.append((pid, pos, len(kept), sum(map(len, kept)), round(cx), round(cy)))
        dd = " ".join(
            "M" + " ".join("%g %g" % (round(x - ox, 1), round(y - oy, 1)) for x, y in sp) + "Z"
            for sp in kept
        )
        symbols.append('<path id="m-%s" fill-rule="evenodd" d="%s"/>' % (pos, dd))
    for s in stats:
        print("%-14s -> %s  subpaths=%d points=%d centre=(%d,%d)" % s)
    with open(out, "w", encoding="utf-8") as f:
        f.write(
            "<!-- IT7Q master mark: four circle shapes derived from the Oct 2026 brand pack emblem\n"
            "     by tools/brand_mark.py. Colourless on purpose: colours come from CSS. -->\n"
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g">\n<defs>\n%s\n</defs>\n</svg>\n'
            % (size, size, "\n".join(symbols))
        )


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
