"""Watermarking for every raster format the site allows (PLAN.md §5.1, Q43).

- PNG: pure stdlib (pngmark). Pillow is only a fallback decoder for PNGs the
  stdlib decoder refuses (interlaced, 16-bit), and only if it's installed.
- JPEG and WebP: Pillow decodes and re-encodes; the mark is blended by
  pngmark.composite, so every format gets exactly the same mark.

The marker is embedded and verified with the standard library only, so
tools/check.py never needs Pillow:
- JPEG: a COM segment straight after SOI
- WebP: an "XMP " chunk (simple files are converted to the extended layout)
Its sha256 covers the whole file with the hash field zeroed, so any change to
the file after the build (or a raw image copied into dist/) fails the check.
"""
import hashlib
import io
import re
import struct
import zlib

import pngmark

FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}
MAX_WIDTH = 1600          # JPEG/WebP wider than this are scaled down
JPEG_QUALITY = 82
WEBP_QUALITY = 80
ZERO = b"0" * 64
MARKER_RE = re.compile(rb"IT7Q-Watermark (v\d+) sha256=([0-9a-f]{64}) corner=(br|bl|tr|tl)")
XMP_NS = "https://it7q.com.au/ns/watermark/1.0/"


class MarkError(ValueError):
    pass


# ---------------------------------------------------------------- Pillow (build only)

def _pil():
    try:
        from PIL import Image, ImageCms, ImageOps
    except ImportError:
        raise MarkError(
            "JPEG/WebP images need Pillow: pip install -r requirements.txt (PLAN.md §5.1, §7.1)"
        ) from None
    return Image, ImageCms, ImageOps


def has_pillow():
    try:
        _pil()
    except MarkError:
        return False
    return True


def _pillow_decode(data, max_width=None):
    """Decode with Pillow into an 8-bit RGB/RGBA pngmark.Image.

    Applies the camera's rotation, converts to sRGB and drops every bit of
    metadata (EXIF and its GPS location never reach dist/).
    """
    Image, ImageCms, ImageOps = _pil()
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:  # Pillow raises many types for bad files
        raise MarkError("unreadable image: %s" % e)
    icc = im.info.get("icc_profile")
    alpha = im.mode in ("RGBA", "LA", "PA", "RGBa") or "transparency" in im.info
    mode = "RGBA" if alpha else "RGB"
    im = ImageOps.exif_transpose(im)
    if icc:
        try:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            im = ImageCms.profileToProfile(im, src, ImageCms.createProfile("sRGB"), outputMode=mode)
        except Exception as e:
            print("warning: colour profile not converted (%s); colours may shift slightly" % e)
    if im.mode != mode:
        im = im.convert(mode)
    if max_width and im.width > max_width:
        height = max(1, round(im.height * max_width / im.width))
        im = im.resize((max_width, height), Image.Resampling.LANCZOS)
    return pngmark.Image(im.width, im.height, len(mode), bytearray(im.tobytes()))


def _pillow_encode(img, fmt):
    Image = _pil()[0]
    im = Image.frombytes("RGBA" if img.channels == 4 else "RGB", (img.width, img.height), bytes(img.pixels))
    buf = io.BytesIO()
    if fmt == "jpeg":
        im.convert("RGB").save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    else:
        im.save(buf, "WEBP", quality=WEBP_QUALITY, method=6)
    return buf.getvalue()


# ---------------------------------------------------------------- containers (stdlib)

def _jpeg_segments(data):
    """Yield (marker, payload) for each header segment up to the start of scan."""
    if not data.startswith(b"\xff\xd8"):
        raise MarkError("not a JPEG file")
    pos = 2
    while pos < len(data):
        if data[pos] != 0xFF:
            raise MarkError("corrupt JPEG segment at byte %d" % pos)
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker == 0xDA or marker == 0xD9:  # start of scan / end of image
            return
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            continue
        if pos + 2 > len(data):
            raise MarkError("truncated JPEG segment")
        length = struct.unpack(">H", data[pos:pos + 2])[0]
        if length < 2 or pos + length > len(data):
            raise MarkError("truncated JPEG segment")
        yield marker, data[pos + 2:pos + length]
        pos += length
    raise MarkError("JPEG has no image data")


def _riff_chunks(data):
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise MarkError("not a WebP file")
    if struct.unpack("<I", data[4:8])[0] + 8 != len(data):
        raise MarkError("WebP size field does not match the file")
    pos, chunks = 12, []
    while pos < len(data):
        if pos + 8 > len(data):
            raise MarkError("truncated WebP chunk")
        fourcc, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
        payload = data[pos + 8:pos + 8 + size]
        if len(payload) != size:
            raise MarkError("truncated WebP chunk")
        chunks.append((fourcc, payload))
        pos += 8 + size + (size & 1)
    if not chunks:
        raise MarkError("WebP has no chunks")
    return chunks


def _riff_build(chunks):
    body = b"".join(
        fourcc + struct.pack("<I", len(p)) + p + (b"\x00" if len(p) & 1 else b"") for fourcc, p in chunks
    )
    return b"RIFF" + struct.pack("<I", len(body) + 4) + b"WEBP" + body


def _jpeg_add_comment(data, text):
    if not data.startswith(b"\xff\xd8"):
        raise MarkError("not a JPEG file")
    return data[:2] + b"\xff\xfe" + struct.pack(">H", len(text) + 2) + text + data[2:]


def _webp_add_xmp(data, xmp, width, height, alpha):
    chunks = _riff_chunks(data)
    if chunks[0][0] == b"VP8X":
        head = chunks[0][1]
        chunks = [(b"VP8X", bytes([head[0] | 0x04]) + head[1:])] + chunks[1:]
    else:  # simple VP8/VP8L file: extended layout needed to carry metadata
        flags = 0x04 | (0x10 if alpha else 0)
        vp8x = bytes([flags, 0, 0, 0]) + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
        chunks = [(b"VP8X", vp8x)] + chunks
    chunks = [c for c in chunks if c[0] != b"XMP "] + [(b"XMP ", xmp)]
    return _riff_build(chunks)


def _marker(corner):
    return b"IT7Q-Watermark %s sha256=%s corner=%s" % (pngmark.MARK_VERSION.encode(), ZERO, corner.encode())


def _seal(data):
    """Replace the zeroed hash in the (single) marker with the file's hash."""
    matches = list(MARKER_RE.finditer(data))
    if len(matches) != 1 or matches[0].group(2) != ZERO:
        raise MarkError("expected exactly one unsealed marker")
    start, end = matches[0].span(2)
    digest = hashlib.sha256(data).hexdigest().encode()
    return data[:start] + digest + data[end:]


def embed(data, fmt, corner, width=None, height=None, alpha=False):
    """Add a sealed IT7Q marker to an encoded JPEG or WebP file."""
    if fmt == "jpeg":
        out = _jpeg_add_comment(data, _marker(corner))
    elif fmt == "webp":
        xmp = (
            '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description xmlns:it7q="%s" it7q:watermark="%s"/></rdf:RDF></x:xmpmeta>'
            % (XMP_NS, _marker(corner).decode("ascii"))
        ).encode("ascii")
        out = _webp_add_xmp(data, xmp, width, height, alpha)
    else:
        raise MarkError("embed() handles JPEG and WebP only")
    return _seal(out)


# ---------------------------------------------------------------- public API

def watermark(data, ext, paths, view_size, corner="br"):
    """Return the watermarked bytes for a source image with extension ext."""
    fmt = FORMATS.get(ext.lower())
    if fmt is None:
        raise MarkError("unsupported image format %s: use PNG, JPEG or WebP (§5.1)" % ext)
    try:
        if fmt == "png":
            try:
                img = pngmark.decode(data)
            except (pngmark.PNGError, zlib.error) as e:
                if not has_pillow():
                    raise MarkError(str(e))
                img = _pillow_decode(data)
            pngmark.composite(img, paths, view_size, corner)
            marker = "%s sha256=%s corner=%s" % (pngmark.MARK_VERSION, img.digest(), corner)
            return pngmark.encode(img, marker)
        img = _pillow_decode(data, MAX_WIDTH)
        pngmark.composite(img, paths, view_size, corner)
        encoded = _pillow_encode(img, fmt)
        return embed(encoded, fmt, corner, img.width, img.height, img.channels == 4)
    except pngmark.PNGError as e:
        raise MarkError(str(e))


def verify(data, ext):
    """(ok, reason). Stdlib only: works without Pillow."""
    fmt = FORMATS.get(ext.lower())
    if fmt is None:
        return False, "format not allowed: use PNG, JPEG or WebP (§5.1)"
    if fmt == "png":
        return pngmark.verify(data)
    try:
        if fmt == "jpeg":
            holders = [p for m, p in _jpeg_segments(data) if m == 0xFE]
        else:
            holders = [p for fourcc, p in _riff_chunks(data) if fourcc == b"XMP "]
    except MarkError as e:
        return False, "unreadable %s: %s" % (fmt.upper(), e)
    matches = list(MARKER_RE.finditer(data))
    if not matches or not any(MARKER_RE.search(h) for h in holders):
        return False, "no IT7Q watermark marker"
    if len(matches) != 1:
        return False, "more than one watermark marker"
    m = matches[0]
    if m.group(1).decode() != pngmark.MARK_VERSION:
        return False, "malformed watermark marker"
    zeroed = data[:m.start(2)] + ZERO + data[m.end(2):]
    if hashlib.sha256(zeroed).hexdigest().encode() != m.group(2):
        return False, "marker does not match the file (image changed after watermarking)"
    return True, "ok"
