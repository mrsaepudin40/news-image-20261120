#!/usr/bin/env python3
"""The World in One Day -- Friday 20 November 2026.

A pure-stdlib program (no Pillow, no network) that draws one 1024x1024
newspaper front page summing up the world news of Friday 20 November
2026: 33 stories (3 illustrated leads, 8 pictured medium stories, 22
more in brief), a world map with 12 numbered pins, a numbers strip, a
DATE CHECK box and a source footer. Output is deterministic: two runs
write identical bytes.

Every headline was checked against reports dated 20 November 2026
before it was drawn. Four items the day's top entries carry turned out
to be 19 November news on re-check (U17 Australia 2-0 Argentina,
Lula-Raoni land recognition, South Africa's Test win, Senegal's budget
decree) and were left out; they are named in the DATE CHECK box.
Market figures are Friday closes, labelled as closes; the US close,
the COP31 final text and Medvedev v Tiafoe all fell after the 17:30
UTC press time and are flagged as such. Contested claims are
attributed in the text, never stated as fact.

Layout follows the front-page skeleton the day's best entries share:
a big serif masthead with the date and a story/region count strip, a
numbers strip, three big illustrated leads, a pictured medium grid,
a map with numbered pins, and a numbered also-list at the bottom.
All pictures are flat vector drawings made in code; the only files
the program reads are the three Liberation Serif fonts beside it.
"""

import math
import os
import struct
import sys
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- palette
CREAM = (246, 239, 220)
PAPER = (251, 247, 234)
INK = (26, 26, 26)
NAVY = (16, 41, 78)
NAVY2 = (12, 33, 63)
NAVY3 = (24, 58, 104)
GOLD = (201, 162, 39)
RED = (178, 34, 34)
DARKRED = (140, 22, 22)
TEAL = (18, 105, 120)
SKY = (205, 222, 232)
SAND = (226, 208, 168)
LAND = (222, 205, 165)
GREY = (90, 90, 90)
LIGHT = (238, 231, 210)
MIDGREY = (160, 155, 140)

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _idx(self, x, y):
        return (y * self.w + x) * 3

    def set_px(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = self._idx(x, y)
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def blend_px(self, x, y, c, a):
        """Blend colour c with coverage a (0-255) over the pixel."""
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a >= 255:
            self.set_px(x, y, c)
            return
        i = self._idx(x, y)
        ia = 255 - a
        self.px[i] = (c[0] * a + self.px[i] * ia) // 255
        self.px[i + 1] = (c[1] * a + self.px[i + 1] * ia) // 255
        self.px[i + 2] = (c[2] * a + self.px[i + 2] * ia) // 255

    def fill_rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = self._idx(x0, yy)
            self.px[i:i + len(row)] = row

    def rect_outline(self, x, y, w, h, c, t=1):
        self.fill_rect(x, y, w, t, c)
        self.fill_rect(x, y + h - t, w, t, c)
        self.fill_rect(x, y, t, h, c)
        self.fill_rect(x + w - t, y, t, h, c)

    def hline(self, x0, x1, y, c, t=1):
        if x0 > x1:
            x0, x1 = x1, x0
        self.fill_rect(x0, y, x1 - x0 + 1, t, c)

    def vline(self, x, y0, y1, c, t=1):
        if y0 > y1:
            y0, y1 = y1, y0
        self.fill_rect(x, y0, t, y1 - y0 + 1, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            if t <= 1:
                self.set_px(x, y, c)
            else:
                r = t // 2
                self.fill_rect(x - r, y - r, t, t, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x += sx
            if e2 <= dx:
                err += dx
                y += sy

    def fill_circle(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.fill_rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def circle_outline(self, cx, cy, r, c, t=1):
        steps = max(24, r * 6)
        pts = []
        for i in range(steps + 1):
            a = 2 * math.pi * i / steps
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.polyline(pts, c, t)

    def polyline(self, pts, c, t=1):
        for i in range(len(pts) - 1):
            self.line(int(round(pts[i][0])), int(round(pts[i][1])),
                      int(round(pts[i + 1][0])), int(round(pts[i + 1][1])), c, t)

    def fill_poly(self, pts, c):
        """Even-odd scanline fill of a polygon (float coords allowed)."""
        if len(pts) < 3:
            return
        edges = []
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if y0 == y1:
                continue
            edges.append((x0, y0, x1, y1))
        if not edges:
            return
        ymin = max(0, int(math.floor(min(p[1] for p in pts))))
        ymax = min(self.h - 1, int(math.ceil(max(p[1] for p in pts))))
        for y in range(ymin, ymax + 1):
            yc = y + 0.5
            xs = []
            for (x0, y0, x1, y1) in edges:
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    xs.append(x0 + (yc - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                x0 = int(math.ceil(xs[i]))
                x1 = int(math.floor(xs[i + 1]))
                if x1 >= x0:
                    self.fill_rect(x0, y, x1 - x0 + 1, 1, c)

    def blit_mask(self, mask, mw, mh, dx, dy, c):
        """Blit a coverage mask (bytes, mw*mh) in colour c."""
        for yy in range(mh):
            ty = dy + yy
            if ty < 0 or ty >= self.h:
                continue
            row = mask[yy * mw:(yy + 1) * mw]
            base = ty * self.w * 3
            for xx in range(mw):
                a = row[xx]
                if a == 0:
                    continue
                tx = dx + xx
                if tx < 0 or tx >= self.w:
                    continue
                i = base + tx * 3
                if a == 255:
                    self.px[i] = c[0]
                    self.px[i + 1] = c[1]
                    self.px[i + 2] = c[2]
                else:
                    ia = 255 - a
                    self.px[i] = (c[0] * a + self.px[i] * ia) // 255
                    self.px[i + 1] = (c[1] * a + self.px[i + 1] * ia) // 255
                    self.px[i + 2] = (c[2] * a + self.px[i + 2] * ia) // 255

# ---------------------------------------------------------------- PNG out
def encode_png(rgb, w, h):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))

# ---------------------------------------------------------------- fonts
# Minimal TrueType reader + rasteriser, written for this entry. Only
# what a newspaper page needs: cmap (formats 4 and 12), hmtx advances,
# simple and composite glyf outlines, quadratic flattening, non-zero
# scanline fill with 3x supersampling for smooth edges.

def _u16(b, o):
    return struct.unpack_from(">H", b, o)[0]


def _i16(b, o):
    return struct.unpack_from(">h", b, o)[0]


def _u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


class Font:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        d = self.data
        ntab = _u16(d, 4)
        self.tables = {}
        for i in range(ntab):
            o = 12 + 16 * i
            tag = d[o:o + 4].decode("latin-1")
            self.tables[tag] = (_u32(d, o + 8), _u32(d, o + 12))
        head = self.tables["head"][0]
        self.upem = _u16(d, head + 18)
        self.loc_fmt = _i16(d, head + 50)
        maxp = self.tables["maxp"][0]
        self.nglyphs = _u16(d, maxp + 4)
        hhea = self.tables["hhea"][0]
        self.ascent = _i16(d, hhea + 4)
        self.descent = _i16(d, hhea + 6)
        self.nhmtx = _u16(d, hhea + 34)
        self.hmtx = self.tables["hmtx"][0]
        self.cmap = self.tables["cmap"][0]
        self.loca = self.tables["loca"][0]
        self.glyf = self.tables["glyf"][0]
        self._cmap4 = None
        self._cmap12 = None
        self._parse_cmap()
        self._cache = {}

    def _parse_cmap(self):
        d = self.data
        n = _u16(d, self.cmap + 2)
        best4 = None
        best12 = None
        for i in range(n):
            o = self.cmap + 4 + 8 * i
            plat = _u16(d, o)
            enc = _u16(d, o + 2)
            off = _u32(d, o + 4)
            fmt = _u16(d, self.cmap + off)
            if fmt == 4 and best4 is None:
                best4 = self.cmap + off
                if plat == 3 and enc == 1:
                    best4 = self.cmap + off
                    break
            elif fmt == 12 and best12 is None:
                best12 = self.cmap + off
        if best4 is not None:
            self._cmap4 = self._read_fmt4(best4)
        if best12 is not None:
            self._cmap12 = self._read_fmt12(best12)

    def _read_fmt4(self, o):
        d = self.data
        seg = _u16(d, o + 6) // 2
        p = o + 14
        end = [_u16(d, p + 2 * i) for i in range(seg)]
        p += 2 * seg + 2
        start = [_u16(d, p + 2 * i) for i in range(seg)]
        p += 2 * seg
        delta = [_i16(d, p + 2 * i) for i in range(seg)]
        p += 2 * seg
        ro_off = p
        ro = [_u16(d, p + 2 * i) for i in range(seg)]
        glyphs = p + 2 * seg
        return (start, end, delta, ro, ro_off, glyphs)

    def _read_fmt12(self, o):
        d = self.data
        n = _u32(d, o + 12)
        groups = []
        p = o + 16
        for _ in range(n):
            groups.append((_u32(d, p), _u32(d, p + 4), _u32(d, p + 8)))
            p += 12
        return groups

    def glyph_id(self, ch):
        c = ord(ch)
        if self._cmap4 is not None:
            start, end, delta, ro, ro_off, glyphs = self._cmap4
            for i in range(len(start)):
                if start[i] <= c <= end[i]:
                    if ro[i] == 0:
                        return (c + delta[i]) & 0xFFFF
                    pos = ro_off + 2 * i + ro[i] + 2 * (c - start[i])
                    g = _u16(self.data, pos)
                    if g == 0:
                        return 0
                    return (g + delta[i]) & 0xFFFF
                if c < start[i]:
                    break
        if self._cmap12 is not None:
            for (s, e, g) in self._cmap12:
                if s <= c <= e:
                    return g + (c - s)
        return 0

    def advance(self, gid):
        if gid < self.nhmtx:
            return _u16(self.data, self.hmtx + 4 * gid)
        return _u16(self.data, self.hmtx + 4 * (self.nhmtx - 1))

    def _loc(self, gid):
        d = self.data
        if self.loc_fmt == 0:
            return _u16(d, self.loca + 2 * gid) * 2, _u16(d, self.loca + 2 * (gid + 1)) * 2
        return _u32(d, self.loca + 4 * gid), _u32(d, self.loca + 4 * (gid + 1))

    def _outline(self, gid, depth=0):
        """Return list of contours; each is a list of (x, y, oncurve)."""
        if depth > 4:
            return []
        off, nxt = self._loc(gid)
        if nxt <= off:
            return []
        d = self.data
        base = self.glyf + off
        ncon = _i16(d, base)
        if ncon >= 0:
            return self._simple_outline(base, ncon)
        # composite glyph: gather transformed component outlines
        p = base + 10
        out = []
        while True:
            flags = _u16(d, p)
            comp = _u16(d, p + 2)
            p += 4
            if flags & 0x0001:
                dx = _i16(d, p)
                dy = _i16(d, p + 2)
                p += 4
            else:
                dx = struct.unpack_from(">b", d, p)[0]
                dy = struct.unpack_from(">b", d, p + 1)[0]
                p += 2
            if flags & 0x0002:
                pass  # args are xy offsets, already read as dx/dy
            else:
                dx, dy = 0, 0  # point matching: ignore, rare in our text
            # transform matrix, F2DOT14
            if flags & 0x0008:
                s = _i16(d, p) / 16384.0
                p += 2
                m = (s, 0.0, 0.0, s)
            elif flags & 0x0040:
                sx = _i16(d, p) / 16384.0
                sy = _i16(d, p + 2) / 16384.0
                p += 4
                m = (sx, 0.0, 0.0, sy)
            elif flags & 0x0080:
                m = tuple(_i16(d, p + 2 * k) / 16384.0 for k in range(4))
                p += 8
            else:
                m = (1.0, 0.0, 0.0, 1.0)
            for contour in self._outline(comp, depth + 1):
                out.append([(m[0] * x + m[1] * y + dx,
                             m[2] * x + m[3] * y + dy, on)
                            for (x, y, on) in contour])
            if not (flags & 0x0020):
                break
        return out

    def _simple_outline(self, base, ncon):
        d = self.data
        ends = [_u16(d, base + 10 + 2 * i) for i in range(ncon)]
        npts = ends[-1] + 1 if ends else 0
        p = base + 10 + 2 * ncon
        ilen = _u16(d, p)
        p += 2 + ilen
        flags = []
        while len(flags) < npts:
            fl = d[p]
            p += 1
            flags.append(fl)
            if fl & 0x08:
                rep = d[p]
                p += 1
                flags.extend([fl] * rep)
        xs = []
        x = 0
        for fl in flags:
            if fl & 0x02:
                v = d[p]
                p += 1
                x += v if (fl & 0x10) else -v
            elif fl & 0x10:
                pass
            else:
                x += _i16(d, p)
                p += 2
            xs.append(x)
        ys = []
        y = 0
        for fl in flags:
            if fl & 0x04:
                v = d[p]
                p += 1
                y += v if (fl & 0x20) else -v
            elif fl & 0x20:
                pass
            else:
                y += _i16(d, p)
                p += 2
            ys.append(y)
        pts = [(xs[i], ys[i], bool(flags[i] & 0x01)) for i in range(npts)]
        contours = []
        start = 0
        for e in ends:
            contours.append(pts[start:e + 1])
            start = e + 1
        return contours

    def _flatten(self, contours, scale):
        """Contours in font units -> polygons in pixel coords (y down)."""
        polys = []
        for pts in contours:
            if len(pts) < 2:
                continue
            # build walk list starting at an on-curve point
            if pts[0][2]:
                start = pts[0][:2]
                rest = pts[1:]
            elif pts[-1][2]:
                start = pts[-1][:2]
                rest = pts[:-1]
            else:
                start = ((pts[-1][0] + pts[0][0]) / 2.0,
                         (pts[-1][1] + pts[0][1]) / 2.0)
                rest = pts
            poly = [start]
            cur = start
            i = 0
            seq = rest + [start + (True,)] if False else rest
            # walk rest points, wrapping to start at the end
            order = list(rest)
            n = len(order)
            j = 0
            while j < n:
                pt = order[j]
                if pt[2]:
                    poly.append(pt[:2])
                    cur = pt[:2]
                    j += 1
                else:
                    if j + 1 < n:
                        nxt = order[j + 1]
                    else:
                        nxt = (start[0], start[1], True)
                    if nxt[2]:
                        end = nxt[:2]
                        j += 2
                    else:
                        end = ((pt[0] + nxt[0]) / 2.0, (pt[1] + nxt[1]) / 2.0)
                        j += 1
                    # quadratic bezier cur -> end with control pt
                    cx, cy = pt[0], pt[1]
                    x0, y0 = cur
                    x1, y1 = end
                    chord = math.hypot(x1 - x0, y1 - y0) * scale
                    steps = max(2, min(28, int(chord / 1.5) + 1))
                    for s in range(1, steps):
                        t = s / steps
                        mt = 1 - t
                        poly.append((mt * mt * x0 + 2 * mt * t * cx + t * t * x1,
                                     mt * mt * y0 + 2 * mt * t * cy + t * t * y1))
                    poly.append(end)
                    cur = end
            if poly and poly[-1] != start:
                pass
            polys.append([(x * scale, -y * scale) for (x, y) in poly])
        return polys

    def _fill_binary(self, mask, mw, polys):
        """Non-zero winding fill of polygons into a binary mask bytearray."""
        mh = len(mask) // mw
        edges = []
        for poly in polys:
            n = len(poly)
            for i in range(n):
                x0, y0 = poly[i]
                x1, y1 = poly[(i + 1) % n]
                if y0 != y1:
                    edges.append((x0, y0, x1, y1))
        for y in range(mh):
            yc = y + 0.5
            cross = []
            for (x0, y0, x1, y1) in edges:
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    cross.append((x0 + (yc - y0) * (x1 - x0) / (y1 - y0),
                                  1 if y1 > y0 else -1))
            cross.sort()
            wind = 0
            for i in range(len(cross) - 1):
                wind += cross[i][1]
                if wind != 0:
                    x0 = int(math.ceil(cross[i][0]))
                    x1 = int(math.floor(cross[i + 1][0]))
                    if x1 >= x0:
                        base = y * mw
                        for xx in range(max(0, x0), min(mw, x1 + 1)):
                            mask[base + xx] = 255

    def glyph(self, ch, size):
        """Return (mask, w, h, left, top, advance) for ch at pixel size."""
        key = (ch, size)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        gid = self.glyph_id(ch)
        adv = self.advance(gid) * size / self.upem
        if gid == 0:
            res = (b"", 0, 0, 0, 0, adv)
            self._cache[key] = res
            return res
        contours = self._outline(gid)
        if not contours:
            res = (b"", 0, 0, 0, 0, adv)
            self._cache[key] = res
            return res
        ss = 3
        scale = size / self.upem * ss
        polys = self._flatten(contours, scale)
        xs = [p[0] for poly in polys for p in poly]
        ys = [p[1] for poly in polys for p in poly]
        left = int(math.floor(min(xs)))
        right = int(math.ceil(max(xs)))
        top = int(math.floor(min(ys)))
        bottom = int(math.ceil(max(ys)))
        mw = max(1, right - left)
        mh = max(1, bottom - top)
        shifted = [[(x - left, y - top) for (x, y) in poly] for poly in polys]
        big = bytearray(mw * mh)
        self._fill_binary(big, mw, shifted)
        w = (mw + ss - 1) // ss
        h = (mh + ss - 1) // ss
        mask = bytearray(w * h)
        for yy in range(h):
            for xx in range(w):
                total = 0
                for dy in range(ss):
                    for dx in range(ss):
                        sx = xx * ss + dx
                        sy = yy * ss + dy
                        if sx < mw and sy < mh and big[sy * mw + sx]:
                            total += 1
                mask[yy * w + xx] = total * 255 // (ss * ss)
        res = (bytes(mask), w, h, left // ss, top // ss, adv)
        self._cache[key] = res
        return res

    def text_width(self, s, size):
        w = 0.0
        for ch in s:
            w += self.glyph(ch, size)[5]
        return w

    def draw(self, cv, x, y_baseline, s, size, color):
        cx = x
        for ch in s:
            mask, w, h, left, top, adv = self.glyph(ch, size)
            if w and h:
                cv.blit_mask(mask, w, h, int(round(cx)) + left,
                             int(round(y_baseline)) + top, color)
            cx += adv
        return cx

# ---------------------------------------------------------------- text tools
def wrap_text(font, s, size, maxw):
    lines = []
    for para in s.split("\n"):
        words = para.split(" ")
        cur = ""
        for wd in words:
            trial = wd if not cur else cur + " " + wd
            if font.text_width(trial, size) <= maxw or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        if cur or not lines:
            lines.append(cur)
    return lines


def draw_wrapped(cv, font, x, y, s, size, color, maxw, leading=None):
    if leading is None:
        leading = int(size * 1.28)
    lines = wrap_text(font, s, size, maxw)
    for i, ln in enumerate(lines):
        font.draw(cv, x, y + i * leading + size, ln, size, color)
    return y + len(lines) * leading


def draw_centered(cv, font, cx, y_baseline, s, size, color):
    w = font.text_width(s, size)
    font.draw(cv, cx - w / 2.0, y_baseline, s, size, color)
    return w


def draw_spaced(cv, font, cx, y_baseline, s, size, color, tracking=3):
    """Centred caps with extra tracking between letters."""
    widths = [font.text_width(ch, size) for ch in s]
    total = sum(widths) + tracking * (len(s) - 1)
    x = cx - total / 2.0
    for ch, wd in zip(s, widths):
        font.draw(cv, x, y_baseline, ch, size, color)
        x += wd + tracking
    return total

# ---------------------------------------------------------------- shapes
def star_points(cx, cy, r_out, r_in, n=5, rot=-90.0):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180.0 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def arc_points(cx, cy, rx, ry, a0, a1, steps=24):
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


# ---------------------------------------------------------------- world map
# Simplified continent outlines as (lon, lat) points, equirectangular.
N_AMERICA = [(-168, 66), (-158, 58), (-152, 60), (-140, 60), (-135, 57),
             (-130, 54), (-125, 49), (-124, 42), (-120, 34), (-114, 29),
             (-110, 24), (-105, 20), (-97, 16), (-92, 15), (-86, 12),
             (-83, 9), (-79, 9), (-81, 13), (-83, 16), (-87, 21), (-90, 21),
             (-91, 19), (-97, 26), (-93, 30), (-89, 30), (-84, 30),
             (-81, 26), (-80, 32), (-76, 35), (-74, 40), (-70, 42),
             (-68, 45), (-65, 44), (-60, 47), (-55, 52), (-60, 55),
             (-65, 60), (-68, 58), (-78, 62), (-85, 66), (-92, 66),
             (-95, 69), (-110, 68), (-125, 70), (-140, 70), (-155, 71),
             (-165, 68), (-168, 66)]
GREENLAND = [(-58, 64), (-52, 60), (-43, 60), (-40, 64), (-32, 68),
             (-22, 70), (-20, 74), (-25, 77), (-35, 78), (-50, 76),
             (-58, 74), (-62, 70), (-58, 64)]
S_AMERICA = [(-79, 9), (-77, 4), (-80, -3), (-81, -6), (-77, -12),
             (-72, -18), (-70, -23), (-70, -30), (-72, -37), (-73, -44),
             (-74, -50), (-70, -54), (-66, -55), (-65, -45), (-62, -41),
             (-58, -35), (-52, -32), (-48, -28), (-41, -23), (-39, -17),
             (-35, -9), (-35, -6), (-40, -3), (-44, -2), (-50, 0),
             (-53, 4), (-58, 6), (-62, 9), (-68, 11), (-72, 12),
             (-77, 8), (-79, 9)]
AFRICA = [(-17, 15), (-17, 21), (-15, 27), (-10, 31), (-5, 35), (0, 36),
          (10, 37), (11, 34), (20, 32), (30, 31), (32, 31), (34, 28),
          (37, 22), (39, 18), (43, 12), (48, 11), (51, 11), (46, 5),
          (41, -2), (40, -10), (36, -18), (33, -26), (28, -33), (20, -35),
          (17, -32), (15, -27), (13, -18), (12, -6), (9, 4), (4, 6),
          (-8, 5), (-13, 8), (-17, 12), (-17, 15)]
EURASIA = [(-10, 36), (-9, 38), (-9, 43), (-2, 44), (-1, 46), (-4, 48),
           (-2, 50), (0, 51), (3, 53), (8, 55), (8, 57), (10, 59), (5, 60),
           (5, 62), (10, 64), (12, 66), (18, 69), (25, 71), (30, 70),
           (35, 68), (40, 68), (45, 68), (50, 69), (55, 68), (60, 69),
           (68, 73), (75, 73), (80, 73), (90, 75), (100, 77), (110, 74),
           (120, 73), (130, 72), (140, 72), (150, 70), (158, 69),
           (162, 66), (170, 66), (178, 65), (178, 62), (170, 60),
           (162, 60), (158, 56), (156, 52), (150, 59), (142, 55),
           (141, 50), (140, 45), (135, 43), (130, 42), (127, 40),
           (122, 39), (120, 35), (122, 31), (120, 28), (115, 23),
           (110, 20), (108, 18), (105, 10), (103, 8), (100, 8), (98, 10),
           (97, 15), (94, 17), (92, 21), (89, 22), (86, 20), (84, 19),
           (80, 15), (80, 13), (77, 8), (76, 10), (73, 16), (72, 20),
           (68, 23), (66, 25), (62, 25), (58, 26), (56, 27), (52, 28),
           (50, 29), (48, 30), (48, 29), (50, 26), (54, 24), (57, 22),
           (59, 22), (58, 20), (55, 17), (52, 16), (48, 14), (44, 13),
           (43, 12), (40, 15), (38, 18), (35, 28), (34, 28), (33, 31),
           (30, 36), (27, 37), (23, 36), (22, 37), (19, 40), (16, 38),
           (14, 42), (12, 44), (10, 44), (8, 44), (3, 43), (0, 40),
           (-2, 37), (-6, 36), (-9, 37), (-10, 36)]
UK = [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (1, 51),
      (-3, 50)]
JAPAN = [(130, 31), (132, 33), (134, 34), (136, 35), (138, 35), (140, 37),
         (141, 39), (141, 41), (142, 43), (144, 44), (142, 42), (140, 39),
         (139, 37), (137, 35), (134, 33), (131, 32)]
AUSTRALIA = [(113, -22), (114, -30), (115, -35), (120, -34), (124, -33),
             (129, -32), (132, -32), (135, -35), (138, -35), (140, -38),
             (145, -38), (150, -37), (153, -32), (153, -27), (150, -22),
             (146, -19), (142, -11), (142, -15), (137, -12), (135, -12),
             (132, -11), (130, -13), (126, -14), (122, -17), (118, -20),
             (113, -22)]
NEW_ZEALAND = [(167, -45), (170, -43), (173, -41), (175, -38), (177, -38),
               (174, -41), (172, -43), (168, -46)]
MADAGASCAR = [(44, -16), (47, -15), (50, -16), (49, -20), (47, -24),
              (44, -25), (43, -21), (44, -16)]
SUMATRA = [(95, 5), (98, 3), (100, 0), (103, -3), (105, -5), (104, -6),
           (101, -2), (98, 2), (95, 5)]
BORNEO = [(109, 1), (111, 2), (114, 3), (117, 0), (117, -3), (113, -4),
          (110, -2), (109, 1)]
JAVA = [(105, -6), (108, -7), (112, -7), (114, -8), (111, -8), (107, -7),
        (105, -6)]
NEW_GUINEA = [(131, -1), (136, -2), (140, -3), (141, -8), (137, -8),
              (132, -4), (131, -1)]
LANDS = [N_AMERICA, GREENLAND, S_AMERICA, AFRICA, EURASIA, UK, JAPAN,
         AUSTRALIA, NEW_ZEALAND, MADAGASCAR, SUMATRA, BORNEO, JAVA,
         NEW_GUINEA]


def draw_map(cv, x, y, w, h, pins, serif_b):
    cv.fill_rect(x, y, w, h, NAVY2)
    # faint graticule
    grid = (28, 58, 98)
    for lon in range(-150, 181, 30):
        px = x + (lon + 168) / 360.0 * w
        cv.vline(int(px), y, y + h - 1, grid)
    for lat in range(-60, 79, 30):
        py = y + (78 - lat) / 134.0 * h
        cv.hline(x, x + w - 1, int(py), grid)
    for land in LANDS:
        pts = [(x + (lon + 168) / 360.0 * w, y + (78 - lat) / 134.0 * h)
               for (lon, lat) in land]
        cv.fill_poly(pts, LAND)
        cv.polyline(pts, (170, 150, 110), 1)
    for (num, lon, lat, dx, dy) in pins:
        px = x + (lon + 168) / 360.0 * w
        py = y + (78 - lat) / 134.0 * h
        cx = int(px + dx)
        cy = int(py + dy)
        if dx or dy:
            cv.line(int(px), int(py), cx, cy, RED)
            cv.fill_circle(int(px), int(py), 2, RED)
        cv.fill_circle(cx, cy, 7, RED)
        cv.circle_outline(cx, cy, 7, (251, 247, 234), 1)
        label = str(num)
        tw = serif_b.text_width(label, 9)
        serif_b.draw(cv, cx - tw / 2.0, cy + 3, label, 9,
                     (251, 247, 234))

# ---------------------------------------------------------------- icons
def icon_globe(cv, x, y):
    cv.fill_circle(x + 32, y + 32, 26, NAVY3)
    cv.fill_poly([(x + 18, y + 22), (x + 28, y + 16), (x + 34, y + 24),
                  (x + 26, y + 30), (x + 18, y + 28)], (46, 139, 87))
    cv.fill_poly([(x + 36, y + 38), (x + 46, y + 34), (x + 50, y + 42),
                  (x + 42, y + 48), (x + 36, y + 44)], (46, 139, 87))
    cv.hline(x + 9, x + 55, y + 32, (251, 247, 234))
    cv.hline(x + 14, x + 50, y + 20, (200, 210, 220))
    cv.hline(x + 14, x + 50, y + 44, (200, 210, 220))
    cv.circle_outline(x + 32, y + 32, 26, NAVY, 2)


def icon_flags(cv, x, y):
    # UK flag, left
    cv.fill_rect(x + 2, y + 20, 28, 20, NAVY)
    cv.line(x + 2, y + 20, x + 30, y + 40, (251, 247, 234), 2)
    cv.line(x + 30, y + 20, x + 2, y + 40, (251, 247, 234), 2)
    cv.line(x + 2, y + 20, x + 30, y + 40, RED, 1)
    cv.line(x + 30, y + 20, x + 2, y + 40, RED, 1)
    cv.fill_rect(x + 14, y + 20, 4, 20, (251, 247, 234))
    cv.fill_rect(x + 2, y + 28, 28, 4, (251, 247, 234))
    cv.fill_rect(x + 15, y + 20, 2, 20, RED)
    cv.fill_rect(x + 2, y + 29, 28, 2, RED)
    # EU flag, right
    cv.fill_rect(x + 34, y + 20, 28, 20, (0, 51, 153))
    for k in range(8):
        a = math.radians(k * 45)
        cv.fill_circle(x + 48 + int(7 * math.cos(a)),
                       y + 30 + int(7 * math.sin(a)), 1, GOLD)
    cv.rect_outline(x + 2, y + 20, 28, 20, NAVY, 1)
    cv.rect_outline(x + 34, y + 20, 28, 20, NAVY, 1)


def icon_yen(cv, x, y, serif_b):
    cv.fill_circle(x + 32, y + 32, 25, GOLD)
    cv.circle_outline(x + 32, y + 32, 25, (146, 110, 16), 2)
    cv.circle_outline(x + 32, y + 32, 20, (146, 110, 16), 1)
    label = "Y"
    tw = serif_b.text_width(label, 30)
    serif_b.draw(cv, x + 32 - tw / 2.0, y + 44, label, 30, NAVY)
    cv.hline(x + 22, x + 42, y + 40, NAVY, 2)
    cv.hline(x + 22, x + 42, y + 45, NAVY, 2)


def icon_derrick(cv, x, y):
    cv.fill_poly([(x + 10, y + 56), (x + 54, y + 56), (x + 38, y + 12),
                  (x + 26, y + 12)], INK)
    cv.fill_rect(x + 22, y + 48, 20, 8, CREAM)
    cv.line(x + 16, y + 44, x + 48, y + 44, CREAM, 1)
    cv.line(x + 20, y + 32, x + 44, y + 32, CREAM, 1)
    cv.fill_poly([(x + 32, y + 2), (x + 28, y + 10), (x + 36, y + 10)],
                 (255, 140, 0))
    cv.fill_rect(x + 6, y + 56, 52, 4, INK)


def icon_shield(cv, x, y):
    cv.fill_poly([(x + 12, y + 8), (x + 52, y + 8), (x + 52, y + 32),
                  (x + 32, y + 56), (x + 12, y + 32)], NAVY)
    cv.polyline([(x + 12, y + 8), (x + 52, y + 8), (x + 52, y + 32),
                 (x + 32, y + 56), (x + 12, y + 32), (x + 12, y + 8)],
                GOLD, 2)
    cv.fill_poly(star_points(x + 32, y + 28, 11, 5), GOLD)


def icon_pump(cv, x, y):
    cv.fill_rect(x + 12, y + 10, 30, 40, RED)
    cv.rect_outline(x + 12, y + 10, 30, 40, DARKRED, 2)
    cv.fill_rect(x + 17, y + 16, 20, 12, CREAM)
    cv.fill_rect(x + 20, y + 19, 14, 3, INK)
    cv.fill_rect(x + 20, y + 24, 8, 2, INK)
    cv.fill_rect(x + 17, y + 33, 20, 8, (251, 247, 234))
    cv.polyline([(x + 42, y + 14), (x + 52, y + 22), (x + 52, y + 44),
                 (x + 46, y + 50)], INK, 3)
    cv.fill_rect(x + 44, y + 48, 6, 8, INK)
    cv.fill_rect(x + 8, y + 50, 38, 4, INK)


def icon_megaphone(cv, x, y):
    cv.fill_poly([(x + 8, y + 26), (x + 42, y + 12), (x + 42, y + 50),
                  (x + 8, y + 36)], RED)
    cv.fill_rect(x + 42, y + 12, 5, 38, DARKRED)
    cv.fill_rect(x + 14, y + 36, 8, 14, INK)
    cv.line(x + 52, y + 20, x + 58, y + 14, NAVY, 2)
    cv.line(x + 52, y + 31, x + 60, y + 31, NAVY, 2)
    cv.line(x + 52, y + 42, x + 58, y + 48, NAVY, 2)


def icon_scales(cv, x, y):
    cv.vline(x + 32, y + 8, y + 52, NAVY, 3)
    cv.hline(x + 12, x + 52, y + 12, NAVY, 3)
    cv.fill_poly([(x + 26, y + 52), (x + 38, y + 52), (x + 32, y + 44)],
                 NAVY)
    cv.hline(x + 10, x + 54, y + 54, NAVY, 3)
    for cx in (x + 14, x + 50):
        cv.line(cx, y + 12, cx - 7, y + 30, NAVY, 2)
        cv.line(cx, y + 12, cx + 7, y + 30, NAVY, 2)
        cv.fill_poly(arc_points(cx, y + 30, 9, 6, 0, 180, 12)
                     + [(cx + 9, y + 30), (cx - 9, y + 30)], GOLD)
        cv.hline(cx - 9, cx + 9, y + 30, NAVY, 1)


ICONS = {"globe": icon_globe, "flags": icon_flags, "yen": icon_yen,
         "derrick": icon_derrick, "shield": icon_shield, "pump": icon_pump,
         "megaphone": icon_megaphone, "scales": icon_scales}

# ---------------------------------------------------------------- lead art
def _stars(cv, x, y, w, h, n, color):
    for i in range(n):
        sx = x + (i * 97 + 13) % w
        sy = y + (i * 61 + 7) % h
        cv.set_px(sx, sy, color)
        if i % 3 == 0:
            cv.set_px(sx + 1, sy, color)


def _burst(cv, cx, cy, r):
    cv.fill_poly(star_points(cx, cy, r, r * 0.45, 8), (255, 140, 0))
    cv.fill_poly(star_points(cx, cy, r * 0.62, r * 0.3, 8), (255, 210, 60))
    cv.fill_circle(cx, cy, max(2, r // 4), (255, 240, 180))


def art_kyiv(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, NAVY2)
    cv.fill_rect(x, y, w, 58, (10, 24, 48))
    _stars(cv, x, y, w, 58, 26, (220, 225, 235))
    # skyline silhouettes
    heights = [26, 40, 18, 48, 30, 22, 44, 16, 34, 28]
    bx = x + 4
    for i, hh in enumerate(heights):
        bw = (w - 8) // len(heights)
        cv.fill_rect(bx, y + 96 - hh, bw - 3, hh, (8, 14, 28))
        if i in (1, 4, 6):
            cv.fill_rect(bx + 2, y + 96 - hh - 8, 3, 8, (8, 14, 28))
        bx += bw
    # river
    cv.fill_rect(x, y + 96, w, h - 96, (28, 68, 120))
    cv.hline(x + 10, x + 120, y + 108, (90, 140, 190))
    cv.hline(x + 180, x + 300, y + 118, (90, 140, 190))
    # bridge: deck + three arches, middle arch broken
    cv.fill_rect(x + 8, y + 92, w - 16, 4, (232, 222, 196))
    for ax in (x + 30, x + 130, x + 230):
        cv.polyline(arc_points(ax + 32, y + 96, 32, 16, 180, 360, 16),
                    (232, 222, 196), 2)
    # break in the middle arch
    cv.fill_rect(x + 148, y + 82, 14, 14, NAVY2)
    cv.line(x + 148, y + 96, x + 162, y + 84, (232, 222, 196), 2)
    cv.line(x + 162, y + 96, x + 156, y + 82, (232, 222, 196), 2)
    # missile trails
    for (sx, sy, ex, ey) in [(x + 300, y + 6, x + 250, y + 40),
                             (x + 270, y + 2, x + 210, y + 46),
                             (x + 180, y + 4, x + 150, y + 34)]:
        cv.line(sx, sy, ex, ey, (255, 240, 200), 2)
        cv.fill_circle(ex, ey, 3, (255, 140, 0))
    _burst(cv, x + 66, y + 62, 15)
    _burst(cv, x + 258, y + 52, 12)
    cv.fill_circle(x + 78, y + 48, 7, (120, 120, 120))
    cv.fill_circle(x + 88, y + 42, 5, (140, 140, 140))


def art_akvan(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, SKY)
    cv.fill_rect(x, y + 56, w, h - 56, TEAL)
    cv.fill_rect(x, y + 56, w, 3, (140, 190, 200))
    # clouds
    for (cx, cy, r) in [(x + 40, y + 18, 12), (x + 58, y + 14, 15),
                        (x + 76, y + 20, 11), (x + 250, y + 12, 13),
                        (x + 270, y + 18, 10)]:
        cv.fill_circle(cx, cy, r, (251, 247, 234))
    # rain slashes
    for i in range(14):
        rx = x + 8 + (i * 23) % 200
        ry = y + 26 + (i * 7) % 26
        cv.line(rx, ry, rx - 5, ry + 9, (160, 190, 205), 1)
    # Odisha coast, right side
    cv.fill_poly([(x + 238, y + 56), (x + 268, y + 62), (x + 292, y + 78),
                  (x + 320, y + 96), (x + 320, y + h), (x + 252, y + h),
                  (x + 240, y + 96), (x + 232, y + 72)], SAND)
    cv.fill_circle(x + 282, y + 84, 7, (46, 139, 87))
    cv.fill_circle(x + 296, y + 104, 6, (46, 139, 87))
    cv.fill_circle(x + 268, y + 108, 6, (46, 139, 87))
    # cyclone spiral over the bay
    cx, cy = x + 138, y + 96
    arm = []
    for k in range(120):
        t = k / 119.0 * 4.6 * math.pi
        r = 5 + t * 3.1
        arm.append((cx + r * math.cos(t), cy + r * math.sin(t) * 0.85))
    cv.polyline(arm, (251, 247, 234), 3)
    arm2 = []
    for k in range(90):
        t = k / 89.0 * 3.6 * math.pi + 2.2
        r = 5 + t * 3.1
        arm2.append((cx + r * math.cos(t), cy + r * math.sin(t) * 0.85))
    cv.polyline(arm2, (200, 225, 235), 2)
    cv.fill_circle(cx, cy, 8, (251, 247, 234))
    cv.fill_circle(cx, cy, 4, TEAL)
    # wave marks
    for wy in (y + 118, y + 126):
        for wx in range(x + 12, x + 200, 34):
            cv.polyline(arc_points(wx + 8, wy, 8, 3, 180, 360, 8),
                        (180, 220, 230), 1)


def art_markets(cv, x, y, w, h, serif_b):
    cv.fill_rect(x, y, w, h, (24, 24, 32))
    for gy in range(y + 16, y + h - 16, 16):
        cv.hline(x + 6, x + w - 6, gy, (44, 44, 56))
    tops = [18, 30, 26, 44, 40, 56, 52, 68, 64]
    bottoms = [44, 52, 58, 66, 70, 80, 84, 94, 96]
    for i, (t, b) in enumerate(zip(tops, bottoms)):
        bx = x + 16 + i * 32
        cv.vline(bx + 7, y + t - 6, y + b + 6, (200, 60, 60), 1)
        cv.fill_rect(bx, y + t, 14, b - t, (178, 34, 34))
    cv.polyline([(x + 23 + i * 32, y + t) for i, t in enumerate(tops)],
                (255, 90, 90), 2)
    # big down arrow, right side
    cv.fill_poly([(x + 286, y + 22), (x + 306, y + 22), (x + 306, y + 58),
                  (x + 314, y + 58), (x + 296, y + 82), (x + 278, y + 58),
                  (x + 286, y + 58)], RED)
    cv.rect_outline(x, y, w, h, NAVY, 1)
    label = "NIKKEI -4.77%    KOSPI -5.21%    TAIEX -6.63%"
    tw = serif_b.text_width(label, 11)
    serif_b.draw(cv, x + (w - tw) / 2.0, y + h - 8, label, 11,
                 (251, 247, 234))

# ---------------------------------------------------------------- stories
# (region, tag, headline, deck, art/icon) -- every item dated 20 Nov 2026.
LEADS = [
    ("EUROPE", "UKRAINE - OVERNIGHT BARRAGE",
     "Russia fires 110+ missiles and 400+ drones; three Kyiv bridges hit",
     "27 of the missiles were ballistic, in waves 20-30 minutes apart. "
     "At least eight were killed - six in Kyiv, two in Lviv - and power, "
     "water and heating were cut in five Kyiv districts. A Kh-101 also "
     "came down in Poland.",
     "kyiv"),
    ("ASIA-PACIFIC", "INDIA - CYCLONE AKVAN",
     "Cyclone Akvan makes landfall near Gopalpur; 300,000+ evacuated",
     "The storm crossed the Odisha coast with winds of 70-80 km/h, "
     "gusting to 90, after weakening from a severe cyclonic storm. "
     "209 mm of rain fell at Patrapur. No deaths were reported.",
     "akvan"),
    ("ASIA-PACIFIC", "MARKETS - AI SELL-OFF",
     "AI sell-off sinks Asia: Nikkei -4.77%, KOSPI -5.21%, Taiex -6.63%",
     "Friday closes: Nikkei 56,606; KOSPI 4,869.96, below 5,000; Taiex "
     "35,877.63, capping its worst week since 1991. SoftBank fell "
     "14.6%, Samsung 7.0%. MSCI Asia-Pacific had its worst week since "
     "March 2020.",
     "markets"),
]

MEDIUMS = [
    ("WORLD", "COP31 - CLIMATE",
     "COP31 ends its final day with no deal",
     "The latest draft drops every fossil-fuel mention and the $120bn "
     "goal. '35 by 35' survives; talks run on.",
     "globe"),
    ("EUROPE", "UK-EU - RESET DEAL",
     "UK and EU seal reset deal",
     "100,000 youth visas a year each way; food checks end; carbon "
     "markets linked. Worth up to 17bn pounds a year.",
     "flags"),
    ("ASIA-PACIFIC", "JAPAN - INFLATION",
     "Japan inflation 2.3%; rate rise eyed",
     "October CPI: 2.3% headline, 2.2% core. Most economists expect "
     "the Bank of Japan to lift rates to 1.50% in December.",
     "yen"),
    ("AFRICA", "KENYA - FIRST OIL",
     "Kenya drills its first oil well",
     "Spudding starts at Amosing 1 in Turkana. First oil due 1 Dec: "
     "20,000 barrels a day, rising to 50,000 by 2032.",
     "derrick"),
    ("MIDDLE EAST", "IRAQ - MILITIA BASE",
     "Iraqi troops enter militia stronghold",
     "Forces deploy in Jurf al-Sakhar, a Kataib Hezbollah base "
     "south-west of Baghdad, after a probe into oil smuggling.",
     "shield"),
    ("AFRICA", "MALAWI - FUEL CRISIS",
     "Malawi rations fuel to 20 litres a day",
     "Motorists queue for hours, sometimes overnight, in Blantyre. "
     "Black-market petrol sells at about $17 for two litres.",
     "pump"),
    ("EUROPE", "ITALY - STRIKE",
     "Italy hit by 24-hour general strike",
     "Tens of thousands march in 100+ cities against the 2027 budget. "
     "Rail freight halts from Friday night to Saturday.",
     "megaphone"),
    ("ASIA-PACIFIC", "SOUTH KOREA - COURTS",
     "Seoul moves to impeach top judge",
     "The ruling party acts against Chief Justice Cho Hee-dae after the "
     "Supreme Court softened ex-PM Han's martial-law case.",
     "scales"),
]

# (region, one-line brief) -- numbered 12 to 33 in the page.
ALSO = [
    ("EUROPE", "POLAND: Kh-101 missile and a drone come down near the border; no injuries; Warsaw calls it a provocation."),
    ("EUROPE", "LVIV: Strike on Sknyliv station kills two and wrecks the ticket hall; 10 in hospital."),
    ("MIDDLE EAST", "OMAN: Tanker hit by an unknown projectile off Khasab; fire on board, no casualties. Brent about $92.50."),
    ("AMERICAS", "EL SALVADOR: Bukele files for a third term at Thursday night's deadline; vote 28 Feb 2027."),
    ("ASIA-PACIFIC", "CHINA-AUSTRALIA: Xi hails a 'comprehensive turnaround' as he meets Albanese in Shenzhen."),
    ("ASIA-PACIFIC", "CHINA: Lending rates held for an 18th month - 1-year 3.00%, 5-year 3.50%."),
    ("ASIA-PACIFIC", "CRICKET: Phillips 118 and Nicholls 175 not out put New Zealand on 368 in Wellington."),
    ("AMERICAS", "LAS VEGAS GP: Russell fastest in a wet FP2, 1:47.272; FP1 washed out."),
    ("EUROPE", "ATP FINALS: Alcaraz beats Cobolli 6-4, 6-1 (3-0); Medvedev v Tiafoe tonight for the last semi."),
    ("ASIA-PACIFIC", "ROHINGYA: Bangladesh FM visits Cox's Bazar camps; Myanmar dismisses the ICJ ruling as 'unfair'."),
    ("ASIA-PACIFIC", "CHIPS: SoftBank -14.6%, Samsung -7.0%, SK Hynix -5.9%; Seoul triggers sidecar curbs twice."),
    ("WORLD", "GOLD: Slides to its lowest in more than a year as investors sell to cover losses."),
    ("AMERICAS", "FLORIDA: St Johns River holds above its all-time record, 18.7 ft at Cocoa; schools shut in four counties."),
    ("ASIA-PACIFIC", "TAIWAN: Short-selling curbs take effect as the Taiex caps its worst week since 1991."),
    ("EUROPE", "KHARKIV: Drone hits a hospital in the overnight barrage; at least four hurt."),
    ("AFRICA", "DAKAR: Four bodies found after Thursday's migrant boat capsizing off Senegal."),
    ("AMERICAS", "MEXICO: Nation marks the 116th anniversary of the Revolution."),
    ("AMERICAS", "SAO PAULO: Markets shut for Black Consciousness Day."),
    ("WORLD", "WORLD: UN marks World Children's Day across member states."),
    ("EUROPE", "BERLIN: School pupils strike against military service."),
    ("AMERICAS", "COP31: Panama asks the summit to cap world oil output."),
    ("AMERICAS", "WALL ST: Nasdaq falls about 2% intraday Friday as the AI rout rolls on; Thursday's close: Dow -2.19%."),
]

NUMBERS = [
    ("110+", "MISSILES FIRED AT UKRAINE"),
    ("400+", "DRONES IN THE BARRAGE"),
    ("300,000+", "EVACUATED IN ODISHA"),
    ("-6.63%", "TAIEX CLOSE, FRIDAY"),
    ("100,000", "YOUTH VISAS A YEAR, UK-EU"),
    ("2.3%", "JAPAN INFLATION, OCT"),
]

# (story number, lon, lat, dx, dy) -- pins on the map. Europe's pins
# fan out with leader lines: the true positions sit within a few pixels.
PINS = [
    (1, 30.5, 50.4, 8, 10),
    (12, 22.0, 50.6, -34, -4),
    (13, 24.0, 49.8, 20, -18),
    (5, -0.1, 51.5, -26, 0),
    (10, 12.5, 41.9, -4, 22),
    (31, 13.4, 52.5, -2, -18),
    (20, 7.7, 45.1, -16, 16),
    (4, 30.7, 36.9, 24, 10),
    (2, 84.9, 19.3, 0, 0),
    (11, 127.0, 37.5, 0, 0),
    (6, 139.7, 35.7, 0, 0),
    (7, 36.0, 3.5, 0, 0),
]

REGION_COLOR = {
    "EUROPE": NAVY3,
    "ASIA-PACIFIC": TEAL,
    "AMERICAS": DARKRED,
    "MIDDLE EAST": (128, 90, 0),
    "AFRICA": (34, 110, 60),
    "WORLD": GREY,
}

DATE_CHECK = (
    "DATE CHECK - LEFT OUT AS 19 NOVEMBER NEWS: Shenzhen summit; "
    "Anthropic IPO; ICJ Myanmar verdict; GTA VI launch; Fiona the hippo; "
    "U17 Australia 2-0 Argentina; Lula-Raoni land deal; South Africa Test "
    "win; Senegal budget decree. NOT YET: BepiColombo Mercury arrival "
    "(21 Nov). AFTER PRESS TIME: COP31 final text; US market close; "
    "Medvedev v Tiafoe."
)

FOOTER = [
    "Sources: Reuters, CNN, AP, AFP, BBC, IMD, The Hindu, Morningstar, Aju Press, Cricbuzz, Formula1.com, ATP, UKMTO, UN News, Carbon Brief.",
    "Original drawings. Contested claims are attributed; market figures are Friday closes unless labelled intraday. Press time 17:30 UTC.",
]

ART = {"kyiv": art_kyiv, "akvan": art_akvan, "markets": art_markets}

# ---------------------------------------------------------------- layout
def build():
    base = os.path.dirname(os.path.abspath(__file__))
    serif = Font(os.path.join(base, "LiberationSerif-Regular.ttf"))
    serif_b = Font(os.path.join(base, "LiberationSerif-Bold.ttf"))
    serif_i = Font(os.path.join(base, "LiberationSerif-Italic.ttf"))
    cv = Canvas(W, H, CREAM)
    cv.fill_rect(0, 0, W, 86, NAVY)

    # masthead, dark band: gold label, near-white date, gold rule
    draw_spaced(cv, serif_b, W // 2, 28, "THE WORLD IN ONE DAY", 15, GOLD, 4)
    draw_centered(cv, serif_b, W // 2, 72, "Friday 20 November 2026", 44,
                  (251, 247, 234))
    cv.hline(24, 1000, 80, GOLD, 2)

    # story / region count strip, computed from the data
    counts = {}
    total = 0
    for (region, *_rest) in LEADS + MEDIUMS + ALSO:
        counts[region] = counts.get(region, 0) + 1
        total += 1
    order = ["EUROPE", "ASIA-PACIFIC", "AMERICAS", "MIDDLE EAST", "AFRICA",
             "WORLD"]
    strip = "%d STORIES" % total
    for r in order:
        strip += "  |  %s %d" % (r, counts.get(r, 0))
    draw_centered(cv, serif_b, W // 2, 102, strip, 12, NAVY)

    # numbers strip
    for i, (num, label) in enumerate(NUMBERS):
        x = 24 + i * 163
        cv.fill_rect(x, 110, 160, 52, LIGHT)
        cv.rect_outline(x, 110, 160, 52, MIDGREY, 1)
        draw_centered(cv, serif_b, x + 80, 138, num, 23, NAVY)
        draw_centered(cv, serif_b, x + 80, 155, label, 10, INK)

    # three leads
    font = serif_b
    font.draw(cv, 24, 178, "THE DAY'S THREE BIG STORIES", 12, NAVY)
    cv.hline(24, 1000, 184, MIDGREY, 1)
    cols = [24, 352, 680]
    for (region, tag, head, deck, art), x in zip(LEADS, cols):
        if art == "markets":
            ART[art](cv, x, 190, 320, 124, serif_b)
        else:
            ART[art](cv, x, 190, 320, 124)
        cv.rect_outline(x, 190, 320, 124, NAVY, 1)
        serif_b.draw(cv, x, 332, tag, 11, RED)
        lines = wrap_text(serif_b, head, 19, 320)
        for j, ln in enumerate(lines):
            serif_b.draw(cv, x, 340 + j * 22 + 19, ln, 19, INK)
        dy = 340 + len(lines) * 22 + 6
        draw_wrapped(cv, serif, x, dy, deck, 12, INK, 320, 14)

    # medium grid
    cv.hline(24, 1000, 472, INK, 1)
    serif_b.draw(cv, 24, 490, "MORE OF THE DAY", 12, NAVY)
    for idx, (region, tag, head, deck, icon) in enumerate(MEDIUMS):
        col = idx % 4
        row = idx // 4
        x = 24 + col * 246
        y = 498 + row * 88
        cv.fill_rect(x, y, 64, 64, LIGHT)
        cv.rect_outline(x, y, 64, 64, MIDGREY, 1)
        if icon == "yen":
            ICONS[icon](cv, x, y, serif_b)
        else:
            ICONS[icon](cv, x, y)
        tx = x + 72
        serif_b.draw(cv, tx, y + 12, tag, 10, REGION_COLOR[region])
        draw_wrapped(cv, serif_b, tx, y + 17, head, 12, INK, 166, 15)
        draw_wrapped(cv, serif, tx, y + 50, deck, 10, INK, 166, 12)

    # world map
    cv.hline(24, 1000, 682, INK, 1)
    serif_b.draw(cv, 24, 700, "WHERE IT HAPPENED", 12, NAVY)
    serif.draw(cv, 1000 - serif.text_width("12 OF TODAY'S 33 STORIES PINNED", 11),
               700, "12 OF TODAY'S 33 STORIES PINNED", 11, GREY)
    draw_map(cv, 24, 706, 976, 124, PINS, serif_b)

    # also list
    cv.hline(24, 1000, 838, INK, 1)
    serif_b.draw(cv, 24, 856, "ALSO ON FRIDAY 20 NOVEMBER", 12, NAVY)
    for i, (region, text) in enumerate(ALSO):
        col = i // 11
        row = i % 11
        x = 24 + col * 498
        y = 862 + row * 10
        item = "%d. %s" % (12 + i, text)
        w = serif.text_width(item, 9)
        if w > 474:
            print("also item %d too wide: %.0f" % (12 + i, w),
                  file=sys.stderr)
        serif.draw(cv, x, y + 9, item, 9, INK)

    # date check box
    cv.fill_rect(24, 974, 976, 28, LIGHT)
    cv.rect_outline(24, 974, 976, 28, NAVY, 1)
    draw_wrapped(cv, serif, 32, 976, DATE_CHECK, 10, INK, 960, 12)

    # footer, one line
    draw_centered(cv, serif, W // 2, 1016, " ".join(FOOTER), 8, GREY)
    return cv


def main():
    cv = build()
    data = encode_png(bytes(cv.px), W, H)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR")
    if not outdir:
        outdir = "/output" if os.path.isdir("/output") else "out"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes, %dx%d)" % (path, len(data), W, H))


if __name__ == "__main__":
    main()
