"""Extract positioned glyphs from a text-layer PDF.

Guitar Pro exports its PDFs through Qt, which writes one Tj per glyph with an
explicit Td before it. That makes every fret number, chord name and lyric
recoverable as (x, y, char) with no OCR.
"""

import re
import zlib

TOKEN = re.compile(rb"<([0-9A-Fa-f]*)>|\[(.*?)\]|(-?[\d.]+)|/(\w+)|(\b[A-Za-z'\"*]+\b)", re.S)


class Glyph:
    def __init__(self, char, x, y, font, size):
        self.char = char
        self.x = x
        self.y = y
        self.font = font
        self.size = size

    def __repr__(self):
        return f"{self.char!r}@({self.x:.0f},{self.y:.0f})"


class Segment:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    @property
    def horizontal(self):
        return abs(self.y1 - self.y0) < 0.5

    @property
    def vertical(self):
        return abs(self.x1 - self.x0) < 0.5

    @property
    def length(self):
        return max(abs(self.x1 - self.x0), abs(self.y1 - self.y0))

    def __repr__(self):
        return f"({self.x0:.0f},{self.y0:.0f})-({self.x1:.0f},{self.y1:.0f})"


def apply(ctm, x, y):
    return ctm[0] * x + ctm[2] * y + ctm[4], ctm[1] * x + ctm[3] * y + ctm[5]


BEZIER_STEPS = 4


def flatten(p0, p1, p2, p3, steps=BEZIER_STEPS):
    """Cubic Bezier as a short polyline. Glyph outlines are mostly curves, so
    dropping them leaves fragments that never hash to a stable shape."""
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        x = u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0]
        y = u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]
        pts.append((x, y))
    return pts


def objects(data):
    out = {}
    for m in re.finditer(rb"(\d+)\s+0\s+obj\b(.*?)\bendobj", data, re.S):
        out[int(m.group(1))] = m.group(2)
    return out


def stream(objs, num):
    body = objs.get(num)
    if body is None:
        return None
    m = re.search(rb"stream\r?\n?", body)
    end = body.rfind(b"endstream")
    if not m or end < 0:
        return None
    raw = body[m.end():end].rstrip(b"\r\n")
    if b"/FlateDecode" in body:
        try:
            return zlib.decompress(raw)
        except Exception:
            return None
    return raw


def parse_cmap(data):
    """ToUnicode CMap. Handles both bfchar and the two bfrange forms."""
    text = data.decode("latin1")
    out = {}
    for block in re.findall(r"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            out[int(src, 16)] = _utf16(dst)
    for block in re.findall(r"beginbfrange(.*?)endbfrange", text, re.S):
        # array form: <lo> <hi> [<d0> <d1> ...]
        for lo, hi, arr in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", block, re.S):
            dsts = re.findall(r"<([0-9A-Fa-f]+)>", arr)
            for i, dst in enumerate(dsts):
                out[int(lo, 16) + i] = _utf16(dst)
        # contiguous form: <lo> <hi> <start>
        for lo, hi, start in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>(?!\s*\[)", block):
            base = int(start, 16)
            for k in range(int(lo, 16), int(hi, 16) + 1):
                out[k] = chr(base + k - int(lo, 16))
    return out


def _utf16(hexstr):
    return "".join(chr(int(hexstr[i:i + 4], 16)) for i in range(0, len(hexstr), 4))


def page_fonts(objs, page_body):
    """Map the page's /F<n> resource names to decoded CMaps."""
    res = re.search(rb"/Resources\s+(\d+)\s+0\s+R", page_body)
    scope = objs.get(int(res.group(1)), b"") if res else page_body
    m = re.search(rb"/Font\s*<<(.*?)>>", scope, re.S)
    if not m:
        return {}
    fonts = {}
    for name, num in re.findall(rb"/(\w+)\s+(\d+)\s+0\s+R", m.group(1)):
        body = objs.get(int(num), b"")
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+0\s+R", body)
        base = re.search(rb"/BaseFont\s*/([\w+]+)", body)
        cmap = parse_cmap(stream(objs, int(tu.group(1)))) if tu else {}
        fonts[name.decode()] = (base.group(1).decode() if base else "?", cmap)
    return fonts


def mul(a, b):
    """3x2 affine matrix product: a then b."""
    return (
        a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5],
    )


def run(content, fonts):
    """Minimal content-stream interpreter: enough for Qt's one-glyph-per-Tj output."""
    ctm = (1, 0, 0, 1, 0, 0)
    stack = []
    tm = tlm = (1, 0, 0, 1, 0, 0)
    font, size = None, 0
    glyphs = []
    segments = []
    path, cur = [], None
    ops = []
    for m in TOKEN.finditer(content):
        hexstr, arr, num, name, op = m.groups()
        if hexstr is not None:
            ops.append(("hex", hexstr.decode()))
        elif arr is not None:
            ops.append(("arr", arr))
        elif num is not None:
            try:
                ops.append(("num", float(num)))
            except ValueError:
                pass                      # a bare "." is not a number

        elif name is not None:
            ops.append(("name", name.decode()))
        else:
            o = op.decode()
            args = ops
            ops = []
            if o == "q":
                stack.append(ctm)
            elif o == "Q":
                ctm = stack.pop() if stack else ctm
            elif o == "cm" and len(args) >= 6:
                ctm = mul(tuple(a[1] for a in args[-6:]), ctm)
            elif o == "m" and len(args) >= 2:
                cur = apply(ctm, args[-2][1], args[-1][1])
            elif o == "l" and len(args) >= 2 and cur:
                nxt = apply(ctm, args[-2][1], args[-1][1])
                path.append(Segment(cur[0], cur[1], nxt[0], nxt[1]))
                cur = nxt
            elif o == "c" and len(args) >= 6 and cur:
                c1 = apply(ctm, args[-6][1], args[-5][1])
                c2 = apply(ctm, args[-4][1], args[-3][1])
                end = apply(ctm, args[-2][1], args[-1][1])
                prev = cur
                for pt in flatten(cur, c1, c2, end):
                    path.append(Segment(prev[0], prev[1], pt[0], pt[1]))
                    prev = pt
                cur = end
            elif o in ("v", "y") and len(args) >= 4 and cur:
                a = apply(ctm, args[-4][1], args[-3][1])
                end = apply(ctm, args[-2][1], args[-1][1])
                c1, c2 = (cur, a) if o == "v" else (a, end)
                prev = cur
                for pt in flatten(cur, c1, c2, end):
                    path.append(Segment(prev[0], prev[1], pt[0], pt[1]))
                    prev = pt
                cur = end
            elif o == "h" and path and cur:
                start = (path[0].x0, path[0].y0)
                path.append(Segment(cur[0], cur[1], start[0], start[1]))
                cur = start
            elif o == "re" and len(args) >= 4:
                x, y, w, h = (a[1] for a in args[-4:])
                pts = [apply(ctm, x, y), apply(ctm, x + w, y), apply(ctm, x + w, y + h), apply(ctm, x, y + h)]
                for i in range(4):
                    a, b = pts[i], pts[(i + 1) % 4]
                    path.append(Segment(a[0], a[1], b[0], b[1]))
            elif o in ("S", "s", "f", "F", "B", "b", "n", "f*", "B*", "b*"):
                segments.extend(path)
                path, cur = [], None
            elif o == "BT":
                tm = tlm = (1, 0, 0, 1, 0, 0)
            elif o == "Tf" and len(args) >= 2:
                font, size = args[-2][1], args[-1][1]
            elif o == "Tm" and len(args) >= 6:
                tm = tlm = tuple(a[1] for a in args[-6:])
            elif o in ("Td", "TD") and len(args) >= 2:
                tlm = mul((1, 0, 0, 1, args[-2][1], args[-1][1]), tlm)
                tm = tlm
            elif o in ("Tj", "TJ"):
                cmap = fonts.get(font, ("?", {}))[1]
                codes = []
                for kind, val in args:
                    if kind == "hex":
                        codes += [int(val[i:i + 4], 16) for i in range(0, len(val), 4)]
                    elif kind == "arr":
                        for h in re.findall(rb"<([0-9A-Fa-f]+)>", val):
                            s = h.decode()
                            codes += [int(s[i:i + 4], 16) for i in range(0, len(s), 4)]
                dev = mul(tm, ctm)
                for c in codes:
                    ch = cmap.get(c, "")
                    if ch and ch != "\x00":
                        glyphs.append(Glyph(ch, dev[4], dev[5], fonts.get(font, ("?", {}))[0], size))
    return glyphs, segments


def extract(path, page_index=0):
    data = open(path, "rb").read()
    objs = objects(data)
    pages = [(n, b) for n, b in objs.items() if b"/Type" in b and b"/Page" in b and b"/Contents" in b]
    pages.sort()
    if page_index >= len(pages):
        return [], [], None
    _, body = pages[page_index]
    fonts = page_fonts(objs, body)
    refs = re.search(rb"/Contents\s+(?:(\d+)\s+0\s+R|\[(.*?)\])", body, re.S)
    if refs is None:
        return [], [], None
    nums = []
    if refs.group(1):
        nums = [int(refs.group(1))]
    else:
        nums = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", refs.group(2))]
    content = b"".join(stream(objs, n) or b"" for n in nums)
    media = re.search(rb"/MediaBox\s*\[([^\]]*)\]", body)
    box = [float(v) for v in media.group(1).split()] if media else None
    glyphs, segments = run(content, fonts)
    return glyphs, segments, box
