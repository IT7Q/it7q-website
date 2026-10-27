"""Stdlib-only PNG watermarking for the IT7Q site build (PLAN.md §5.1).

- decode(): PNG bytes -> Image (8-bit RGB or RGBA, non-interlaced output)
- encode(): Image -> PNG bytes, with an IT7Q-Watermark tEXt marker
- render_mark(): rasterise the master mark (mark.svg circles, card colours)
- composite(): blend the mark into a corner of any decoded image
- watermark(): composite + return marked PNG bytes
- verify(): True only if the marker is present and matches the pixels

Anything outside what we can handle exactly (interlaced, 16-bit) raises
PNGError so the build fails closed instead of shipping an unmarked image.
"""
import hashlib
import re
import struct
import zlib

SIG = b"\x89PNG\r\n\x1a\n"
MARK_KEY = b"IT7Q-Watermark"
MARK_VERSION = "v1"

# Business-card master colours (PLAN.md §1), by circle position in mark.svg
MARK_COLOURS = {
    "tl": (0x00, 0xB4, 0xCC),  # cyan
    "tr": (0x7E, 0xC8, 0x20),  # lime
    "bl": (0x8B, 0x5C, 0xF6),  # purple
    "br": (0xF9, 0x73, 0x16),  # orange
}
OPACITY = 0.30
SIZE_FRACTION = 0.12   # mark width as a share of image width
MIN_SIZE, MAX_SIZE = 48, 160
MARGIN_FRACTION = 0.025
SUPERSAMPLE = 4        # vertical sub-rows per pixel (horizontal coverage is exact)


class PNGError(ValueError):
    pass


class Image:
    def __init__(self, width, height, channels, pixels):
        self.width, self.height, self.channels = width, height, channels
        self.pixels = pixels  # bytearray, row-major, no filter bytes

    def digest(self):
        h = hashlib.sha256()
        h.update(struct.pack(">IIB", self.width, self.height, self.channels))
        h.update(self.pixels)
        return h.hexdigest()


# ---------------------------------------------------------------- decoding

def _chunks(data):
    if not data.startswith(SIG):
        raise PNGError("not a PNG file")
    pos = len(SIG)
    while pos < len(data):
        if pos + 8 > len(data):
            raise PNGError("truncated chunk header")
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        crc = data[pos + 8 + length:pos + 12 + length]
        if len(body) != length or len(crc) != 4:
            raise PNGError("truncated chunk")
        if zlib.crc32(ctype + body) != struct.unpack(">I", crc)[0]:
            raise PNGError("bad CRC in %r chunk" % ctype)
        yield ctype, body
        pos += 12 + length
        if ctype == b"IEND":
            return
    raise PNGError("missing IEND")


def _unfilter(raw, width, height, bpp):
    stride = width * bpp
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if len(line) != stride:
            raise PNGError("truncated image data")
        if ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif ftype != 0:
            raise PNGError("unknown filter type %d" % ftype)
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def _unpack_bits(row, width, depth):
    """Expand 1/2/4-bit samples to one byte each."""
    if depth == 8:
        return row
    out = bytearray()
    per_byte = 8 // depth
    mask = (1 << depth) - 1
    for byte in row:
        for k in range(per_byte):
            out.append((byte >> (8 - depth * (k + 1))) & mask)
    return out[:width]


def decode(data):
    ihdr, idat, palette, trns, texts = None, bytearray(), None, None, {}
    for ctype, body in _chunks(data):
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif ctype == b"PLTE":
            palette = body
        elif ctype == b"tRNS":
            trns = body
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"tEXt" and b"\x00" in body:
            k, v = body.split(b"\x00", 1)
            texts[k] = v
    if ihdr is None:
        raise PNGError("missing IHDR")
    width, height, depth, ctype, _comp, _filt, interlace = ihdr
    if interlace:
        raise PNGError("interlaced PNGs are not supported; re-save without interlacing")
    if depth == 16:
        raise PNGError("16-bit PNGs are not supported; re-save as 8-bit")
    channels_in = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if channels_in is None:
        raise PNGError("unknown colour type %d" % ctype)
    if depth != 8 and ctype not in (0, 3):
        raise PNGError("unsupported bit depth %d for colour type %d" % (depth, ctype))
    raw = zlib.decompress(bytes(idat))
    if depth == 8:
        px = _unfilter(raw, width, height, channels_in)
        rows = [px[y * width * channels_in:(y + 1) * width * channels_in] for y in range(height)]
    else:
        row_bytes = (width * depth + 7) // 8
        px = _unfilter(raw, row_bytes, height, 1)
        rows = [_unpack_bits(px[y * row_bytes:(y + 1) * row_bytes], width, depth) for y in range(height)]

    has_alpha = ctype in (4, 6) or trns is not None
    channels = 4 if has_alpha else 3
    out = bytearray(width * height * channels)
    o = 0
    scale = 255 // ((1 << depth) - 1) if ctype == 0 else 1
    for row in rows:
        if ctype == 6 or (ctype == 2 and not has_alpha):
            out[o:o + len(row)] = row
            o += len(row)
            continue
        for x in range(width):
            if ctype == 2:  # RGB + tRNS colour key
                r, g, b = row[x * 3:x * 3 + 3]
                key = struct.unpack(">HHH", trns)
                a = 0 if (r, g, b) == key else 255
                out[o:o + 4] = bytes((r, g, b, a))
            elif ctype == 3:
                i = row[x]
                if palette is None or 3 * i + 3 > len(palette):
                    raise PNGError("palette index out of range")
                r, g, b = palette[3 * i:3 * i + 3]
                if has_alpha:
                    a = trns[i] if i < len(trns) else 255
                    out[o:o + 4] = bytes((r, g, b, a))
                else:
                    out[o:o + 3] = bytes((r, g, b))
            elif ctype == 0:
                v = row[x] * scale
                if has_alpha:
                    a = 0 if row[x] == struct.unpack(">H", trns[:2])[0] else 255
                    out[o:o + 4] = bytes((v, v, v, a))
                else:
                    out[o:o + 3] = bytes((v, v, v))
            else:  # ctype 4: grey + alpha
                v, a = row[x * 2], row[x * 2 + 1]
                out[o:o + 4] = bytes((v, v, v, a))
            o += channels
    img = Image(width, height, channels, out)
    img.texts = texts
    return img


# ---------------------------------------------------------------- encoding

def _chunk(ctype, body):
    return struct.pack(">I", len(body)) + ctype + body + struct.pack(">I", zlib.crc32(ctype + body))


def encode(img, marker=None):
    stride = img.width * img.channels
    raw = bytearray()
    for y in range(img.height):
        raw.append(0)
        raw += img.pixels[y * stride:(y + 1) * stride]
    colour_type = 6 if img.channels == 4 else 2
    out = SIG + _chunk(b"IHDR", struct.pack(">IIBBBBB", img.width, img.height, 8, colour_type, 0, 0, 0))
    if marker:
        out += _chunk(b"tEXt", MARK_KEY + b"\x00" + marker.encode("ascii"))
    out += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += _chunk(b"IEND", b"")
    return out


# ---------------------------------------------------------------- the mark

def load_mark_paths(svg_text):
    """Return {position: [subpath, ...]} and the viewBox size from mark.svg."""
    size = float(re.search(r'viewBox="0 0 ([\d.]+) [\d.]+"', svg_text).group(1))
    paths = {}
    for pos, d in re.findall(r'<path id="m-(\w+)"[^>]* d="([^"]+)"', svg_text):
        subs = []
        for chunk in d.split("M")[1:]:
            nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", chunk)]
            subs.append(list(zip(nums[0::2], nums[1::2])))
        paths[pos] = subs
    if set(paths) != set(MARK_COLOURS):
        raise PNGError("mark.svg must define m-tl, m-tr, m-bl and m-br")
    return paths, size


def _coverage(subpaths, scale, size):
    """Even-odd fill coverage (0..1) for a size×size grid."""
    edges = []
    for sp in subpaths:
        for (x0, y0), (x1, y1) in zip(sp, sp[1:] + sp[:1]):
            if y0 != y1:
                edges.append((x0 * scale, y0 * scale, x1 * scale, y1 * scale))
    cov = [0.0] * (size * size)
    w = 1.0 / SUPERSAMPLE
    for sy in range(size * SUPERSAMPLE):
        y = (sy + 0.5) * w
        xs = sorted(
            x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            for x0, y0, x1, y1 in edges
            if (y0 <= y < y1) or (y1 <= y < y0)
        )
        row = int(y) * size
        for xa, xb in zip(xs[0::2], xs[1::2]):
            xa, xb = max(xa, 0.0), min(xb, float(size))
            if xb <= xa:
                continue
            ia, ib = int(xa), int(xb)
            if ia == ib:
                cov[row + ia] += (xb - xa) * w
                continue
            cov[row + ia] += (ia + 1 - xa) * w
            for i in range(ia + 1, min(ib, size)):
                cov[row + i] += w
            if ib < size:
                cov[row + ib] += (xb - ib) * w
    return cov


def render_mark(paths, view_size, size):
    """RGBA tile (list of (r, g, b, a) floats, a in 0..1) for a size×size mark."""
    scale = size / view_size
    tile = [(0, 0, 0, 0.0)] * (size * size)
    for pos, subs in paths.items():
        colour = MARK_COLOURS[pos]
        for i, c in enumerate(_coverage(subs, scale, size)):
            if c > 0:
                c = min(c, 1.0)
                r, g, b, a = tile[i]
                na = c + a * (1 - c)
                tile[i] = tuple(
                    (colour[k] * c + (r, g, b)[k] * a * (1 - c)) / na for k in range(3)
                ) + (na,)
    return tile


def mark_size(width):
    return max(MIN_SIZE, min(MAX_SIZE, int(width * SIZE_FRACTION)))


def watermark(png_bytes, paths, view_size, corner="br"):
    img = decode(png_bytes)
    composite(img, paths, view_size, corner)
    marker = "%s sha256=%s corner=%s" % (MARK_VERSION, img.digest(), corner)
    return encode(img, marker)


def composite(img, paths, view_size, corner="br", _cache={}):
    """Blend the mark into an 8-bit RGB/RGBA Image in place (shared by every format)."""
    if corner not in ("br", "bl", "tr", "tl"):
        raise PNGError("corner must be br, bl, tr or tl")
    size = mark_size(img.width)
    if size * 2 > min(img.width, img.height):
        raise PNGError("image too small to watermark (%dx%d)" % (img.width, img.height))
    key = (id(paths), size)
    if key not in _cache:
        _cache[key] = render_mark(paths, view_size, size)
    tile = _cache[key]
    margin = max(4, int(min(img.width, img.height) * MARGIN_FRACTION))
    x0 = img.width - size - margin if corner[1] == "r" else margin
    y0 = img.height - size - margin if corner[0] == "b" else margin
    ch, px = img.channels, img.pixels
    for ty in range(size):
        base = ((y0 + ty) * img.width + x0) * ch
        for tx in range(size):
            r, g, b, a = tile[ty * size + tx]
            if a <= 0:
                continue
            a *= OPACITY
            o = base + tx * ch
            px[o] = round(r * a + px[o] * (1 - a))
            px[o + 1] = round(g * a + px[o + 1] * (1 - a))
            px[o + 2] = round(b * a + px[o + 2] * (1 - a))


def verify(png_bytes):
    """(ok, reason). ok only if the marker exists and matches the decoded pixels."""
    try:
        img = decode(png_bytes)
    except (PNGError, zlib.error) as e:
        return False, "unreadable PNG: %s" % e
    value = img.texts.get(MARK_KEY)
    if value is None:
        return False, "no IT7Q watermark marker"
    m = re.match(r"(v\d+) sha256=([0-9a-f]{64})", value.decode("ascii", "replace"))
    if not m or m.group(1) != MARK_VERSION:
        return False, "malformed watermark marker"
    if m.group(2) != img.digest():
        return False, "marker does not match pixels (image changed after watermarking)"
    return True, "ok"
