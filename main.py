#!/usr/bin/env python3
"""The World in One Day -- Friday 20 November 2026 (v3).

A pure-stdlib program (no Pillow, no network) that draws one 1024x1024
newspaper front page summing up the world news of Friday 20 November
2026: 33 stories (3 illustrated leads, 10 pictured medium stories, 20
more in brief), a world map with 14 numbered pins, a numbers strip, a
DATE CHECK box and a source footer. Output is deterministic: two runs
write identical bytes.

v2 restyles every picture as a futuristic HUD panel (dark navy, neon
and gold, corner brackets, dot-matrix map) after the v1 entry scored
0.972784 (rank #2,231): the day's top 10 all draw 13 stories with
full illustrated scenes, cover 7 regions and carry banner labels
inside their lead art, while v1 had 11 drawn stories, 6 regions and
small pictogram icons. Two briefs are promoted to pictured mediums
(Wellington cricket, Las Vegas GP), which also adds Oceania as the
seventh region; the story total stays 33 -- no new unverified story
was added. Every headline was checked against reports dated
20 November 2026 before it was drawn. Market figures are Friday
closes, labelled as closes. v3 (press time 21:00 UTC) adds the
late-evening results v2 flagged as after press time: the US market
close (S&P -3.70%, Nasdaq -5.28%), Medvedev beating Tiafoe 6-3, 6-4
for the last ATP semi-final spot, and COP31 running into overtime
with no deal on Friday. Contested claims are attributed in the text,
never stated as fact.

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
BLUE = (42, 109, 176)
TEAL = (18, 105, 120)
SKY = (205, 222, 232)
SAND = (226, 208, 168)
LAND = (222, 205, 165)
GREY = (90, 90, 90)
LIGHT = (238, 231, 210)
MIDGREY = (160, 155, 140)
# v2 HUD accents
NIGHT = (8, 18, 40)
CYAN = (120, 200, 220)
NEON = (255, 190, 60)
ORANGE = (255, 140, 0)
PURPLE = (96, 64, 144)
GOLDDOT = (201, 162, 39)
PANEL = (10, 26, 54)

# One colour per story number, shared by the map pins and the also-list
# numbers: a number always wears the same colour as its pin on the map.
NUM_COLOURS = [RED, BLUE, TEAL, PURPLE]


def num_colour(n):
    return NUM_COLOURS[n % 4]

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


def draw_wrapped_mixed(cv, x, y, segments, size, maxw, leading=None):
    """Like draw_wrapped, but segments is [(text, font, colour), ...];
    wraps word by word, keeping each word's own font and colour."""
    if leading is None:
        leading = int(size * 1.28)
    words = []
    for (text, font, colour) in segments:
        for wd in text.split(" "):
            if wd:
                words.append((wd, font, colour))
    lines = []
    cur = []
    cur_w = 0
    for (wd, font, colour) in words:
        ww = font.text_width(wd, size)
        sp = font.text_width(" ", size) if cur else 0
        if cur and cur_w + sp + ww > maxw:
            lines.append(cur)
            cur = [(wd, font, colour)]
            cur_w = ww
        else:
            cur.append((wd, font, colour))
            cur_w += sp + ww
    if cur:
        lines.append(cur)
    for i, line in enumerate(lines):
        cx = x
        for j, (wd, font, colour) in enumerate(line):
            font.draw(cv, cx, y + i * leading + size, wd, size, colour)
            cx += font.text_width(wd, size)
            if j + 1 < len(line):
                cx += font.text_width(" ", size)
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


# ---------------------------------------------------------------- HUD tools
def _inside(px, py, poly):
    """Ray-cast point-in-polygon; poly is a list of (x, y)."""
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py):
            xin = (xj - xi) * (py - yi) / (yj - yi) + xi
            if px < xin:
                inside = not inside
        j = i
    return inside


def hud_corners(cv, x, y, w, h, c, arm=9, t=2):
    """Gold L-shaped corner brackets, HUD style."""
    cv.fill_rect(x, y, arm, t, c)
    cv.fill_rect(x, y, t, arm, c)
    cv.fill_rect(x + w - arm, y, arm, t, c)
    cv.fill_rect(x + w - t, y, t, arm, c)
    cv.fill_rect(x, y + h - t, arm, t, c)
    cv.fill_rect(x, y + h - arm, t, arm, c)
    cv.fill_rect(x + w - arm, y + h - t, arm, t, c)
    cv.fill_rect(x + w - t, y + h - arm, t, arm, c)


def neon_line(cv, x0, y0, x1, y1, dim, bright):
    """A glowing line: thick dim pass, thin bright pass."""
    cv.line(x0, y0, x1, y1, dim, 3)
    cv.line(x0, y0, x1, y1, bright, 1)


def lead_banner(cv, serif_b, x, y, big, small):
    """Red banner with white bold big text, white strip with small text."""
    bw = int(max(serif_b.text_width(big, 17),
                 serif_b.text_width(small, 10)) + 16)
    cv.fill_rect(x, y, bw, 24, RED)
    serif_b.draw(cv, x + 8, y + 18, big, 17, (251, 247, 234))
    cv.fill_rect(x, y + 24, bw, 15, (251, 247, 234))
    serif_b.draw(cv, x + 8, y + 36, small, 10, NAVY)
    return bw


def scene_banner(cv, serif_b, x, y, w, text, bg=RED):
    """Short white-on-colour label strip across the bottom of a scene."""
    cv.fill_rect(x, y, w, 13, bg)
    serif_b.draw(cv, x + 6, y + 10, text, 9, (251, 247, 234))


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
    # continents as a gold dot-matrix (HUD style), not solid blobs
    polys = []
    for land in LANDS:
        pts = [(x + (lon + 168) / 360.0 * w, y + (78 - lat) / 134.0 * h)
               for (lon, lat) in land]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        polys.append((pts, min(xs), max(xs), min(ys), max(ys)))
    step = 7
    for gy in range(y + 3, y + h - 2, step):
        for gx in range(x + 3, x + w - 2, step):
            for (pts, x0, x1, y0, y1) in polys:
                if x0 <= gx <= x1 and y0 <= gy <= y1 \
                        and _inside(gx, gy, pts):
                    cv.fill_circle(gx, gy, 1, GOLDDOT)
                    break
    for (num, lon, lat, dx, dy) in pins:
        px = x + (lon + 168) / 360.0 * w
        py = y + (78 - lat) / 134.0 * h
        cx = int(px + dx)
        cy = int(py + dy)
        # hard clamp: the whole pin disc (glow r=10) must stay inside
        # the panel, so no fan offset can ever push a pin over the edge
        cx = max(x + 11, min(x + w - 12, cx))
        cy = max(y + 11, min(y + h - 12, cy))
        if dx or dy:
            cv.line(int(px), int(py), cx, cy, GOLD, 1)
            cv.fill_circle(int(px), int(py), 2, GOLD)
        col = num_colour(num)
        glow = tuple(c // 4 for c in col)
        cv.fill_circle(cx, cy, 10, glow)  # glow ring, dark tint of the pin
        cv.fill_circle(cx, cy, 7, col)
        cv.circle_outline(cx, cy, 7, (251, 247, 234), 1)
        label = str(num)
        tw = serif_b.text_width(label, 9)
        serif_b.draw(cv, cx - tw / 2.0, cy + 3, label, 9,
                     (251, 247, 234))
    hud_corners(cv, x, y, w, h, GOLD, 12, 2)

# ---------------------------------------------------------------- scenes
# v2: every medium story gets a full illustrated HUD scene (188x58),
# not a pictogram icon. The banner strip is drawn by build(); each
# scene paints the 45 px below it on a dark panel.
def scene_cop31(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # globe, left
    cv.fill_circle(x + 30, y + 36, 14, NAVY3)
    cv.fill_poly([(x + 20, y + 30), (x + 28, y + 26), (x + 32, y + 32),
                  (x + 26, y + 36), (x + 20, y + 34)], (46, 139, 87))
    cv.fill_poly([(x + 34, y + 40), (x + 42, y + 38), (x + 44, y + 44),
                  (x + 38, y + 48), (x + 34, y + 44)], (46, 139, 87))
    cv.circle_outline(x + 30, y + 36, 14, CYAN, 1)
    # thermometer, right: red column, no fossil fuel in it
    cv.fill_rect(x + 96, y + 20, 8, 26, (251, 247, 234))
    cv.fill_rect(x + 98, y + 22, 4, 24, RED)
    cv.fill_circle(x + 100, y + 48, 7, RED)
    cv.circle_outline(x + 100, y + 48, 7, (251, 247, 234), 1)
    # a crossed-out flame: the deal that did not happen
    cv.line(x + 140, y + 22, x + 158, y + 44, GOLD, 2)
    cv.line(x + 158, y + 22, x + 140, y + 44, GOLD, 2)
    cv.fill_circle(x + 149, y + 33, 11, (60, 12, 12))
    cv.line(x + 142, y + 26, x + 156, y + 40, RED, 2)
    cv.line(x + 156, y + 26, x + 142, y + 40, RED, 2)


def scene_ukeu(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # UK flag, left
    cv.fill_rect(x + 16, y + 22, 44, 26, NAVY)
    cv.line(x + 16, y + 22, x + 60, y + 48, (251, 247, 234), 2)
    cv.line(x + 60, y + 22, x + 16, y + 48, (251, 247, 234), 2)
    cv.fill_rect(x + 35, y + 22, 6, 26, (251, 247, 234))
    cv.fill_rect(x + 16, y + 32, 44, 6, (251, 247, 234))
    # EU flag, right
    cv.fill_rect(x + 128, y + 22, 44, 26, (0, 51, 153))
    for k in range(8):
        a = math.radians(k * 45)
        cv.fill_circle(x + 150 + int(8 * math.cos(a)),
                       y + 35 + int(8 * math.sin(a)), 1, GOLD)
    # gold link between them
    neon_line(cv, x + 62, y + 35, x + 126, y + 35, (120, 90, 20), GOLD)
    cv.fill_circle(x + 94, y + 35, 4, GOLD)
    cv.fill_circle(x + 94, y + 35, 2, PANEL)


def scene_japan(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # rising bars, last one red-hot
    for i, bh in enumerate((12, 18, 26, 34)):
        bx = x + 18 + i * 26
        col = RED if i == 3 else GOLD
        cv.fill_rect(bx, y + 52 - bh, 16, bh, col)
    cv.hline(x + 12, x + 128, y + 52, (251, 247, 234))
    # rising sun disc
    cv.fill_circle(x + 162, y + 28, 10, RED)
    cv.circle_outline(x + 162, y + 28, 10, (251, 247, 234), 1)
    neon_line(cv, x + 138, y + 46, x + 176, y + 20, (120, 30, 30), RED)


def scene_kenya(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # desert sun
    cv.fill_circle(x + 158, y + 24, 9, ORANGE)
    # derrick silhouette in gold
    cv.line(x + 30, y + 52, x + 52, y + 18, GOLD, 2)
    cv.line(x + 74, y + 52, x + 52, y + 18, GOLD, 2)
    cv.line(x + 36, y + 42, x + 68, y + 42, GOLD, 1)
    cv.line(x + 42, y + 30, x + 62, y + 30, GOLD, 1)
    cv.fill_circle(x + 52, y + 16, 3, NEON)
    cv.hline(x + 12, x + 120, y + 52, SAND)
    # oil drop
    cv.fill_circle(x + 104, y + 44, 5, (20, 20, 20))
    cv.fill_poly([(x + 104, y + 34), (x + 109, y + 44), (x + 99, y + 44)],
                 (20, 20, 20))


def scene_iraq(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # sand ground + watchtower + fence
    cv.fill_rect(x, y + 46, w, 12, (120, 96, 60))
    cv.fill_rect(x + 26, y + 20, 16, 26, INK)
    cv.fill_rect(x + 22, y + 16, 24, 5, INK)
    cv.fill_rect(x + 30, y + 24, 3, 4, GOLD)
    cv.fill_rect(x + 37, y + 24, 3, 4, GOLD)
    for fx in range(70, 180, 12):
        cv.vline(fx, y + 28, y + 46, (200, 180, 130), 2)
    cv.hline(x + 66, x + 178, y + 28, (200, 180, 130), 2)
    cv.fill_poly(star_points(x + 150, y + 22, 7, 3), GOLD)


def scene_malawi(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # fuel pump
    cv.fill_rect(x + 16, y + 18, 26, 30, RED)
    cv.rect_outline(x + 16, y + 18, 26, 30, DARKRED, 1)
    cv.fill_rect(x + 21, y + 23, 16, 9, CREAM)
    cv.polyline([(x + 42, y + 22), (x + 52, y + 30), (x + 52, y + 44)],
                INK, 2)
    # queue of waiting motorists
    for i, qx in enumerate((72, 96, 120, 144)):
        cv.fill_circle(qx, y + 26, 4, (251, 247, 234))
        cv.fill_rect(qx - 3, y + 30, 6, 18, (251, 247, 234))
        if i < 3:
            cv.fill_circle(qx + 12, y + 40, 1, GOLD)
    cv.hline(x + 66, x + 168, y + 50, (120, 110, 90))


def scene_italy(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # marching crowd, one placard up
    for i, qx in enumerate((28, 52, 76, 100, 124, 148)):
        col = GOLD if i % 2 else (251, 247, 234)
        cv.fill_circle(qx, y + 24, 4, col)
        cv.fill_poly([(qx - 5, y + 48), (qx + 5, y + 48),
                      (qx + 3, y + 30), (qx - 3, y + 30)], col)
    cv.vline(x + 164, y + 16, y + 40, (251, 247, 234), 2)
    cv.fill_rect(x + 152, y + 14, 24, 12, (251, 247, 234))
    cv.fill_rect(x + 152, y + 14, 8, 12, (0, 140, 70))
    cv.fill_rect(x + 168, y + 14, 8, 12, RED)


def scene_seoul(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # courthouse pediment + columns (apex kept below the banner strip)
    cv.fill_poly([(x + 20, y + 24), (x + 94, y + 24), (x + 57, y + 16)],
                 GOLD)
    cv.fill_rect(x + 20, y + 24, 74, 3, GOLD)
    for cx in (28, 48, 68, 86):
        cv.fill_rect(cx, y + 27, 6, 22, (251, 247, 234))
    cv.fill_rect(x + 16, y + 49, 82, 3, (251, 247, 234))
    # gavel, right
    cv.fill_rect(x + 130, y + 22, 26, 7, GOLD)
    cv.line(x + 143, y + 29, x + 143, y + 46, GOLD, 3)
    cv.fill_rect(x + 132, y + 46, 22, 3, GOLD)


def scene_cricket(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # green pitch with crease lines
    cv.fill_rect(x, y + 30, w, 22, (34, 110, 60))
    cv.hline(x, x + w - 1, y + 30, (251, 247, 234))
    cv.hline(x, x + w - 1, y + 51, (251, 247, 234))
    cv.vline(x + 52, y + 30, y + 51, (251, 247, 234))
    cv.vline(x + 136, y + 30, y + 51, (251, 247, 234))
    # batsman, mid-stroke
    cv.fill_circle(x + 88, y + 24, 4, (251, 247, 234))
    cv.line(x + 88, y + 28, x + 84, y + 44, (251, 247, 234), 3)
    cv.line(x + 84, y + 44, x + 78, y + 52, (251, 247, 234), 2)
    cv.line(x + 84, y + 44, x + 90, y + 52, (251, 247, 234), 2)
    neon_line(cv, x + 88, y + 32, x + 104, y + 46, (120, 90, 20), GOLD)
    # stumps + ball
    for sx in (146, 151, 156):
        cv.vline(sx, y + 36, y + 50, GOLD, 2)
    cv.fill_circle(x + 120, y + 40, 3, RED)
    cv.fill_circle(x + 120, y + 40, 1, (251, 247, 234))


def scene_vegas(cv, x, y, w, h):
    cv.fill_rect(x, y, w, h, PANEL)
    # wet track + rain
    cv.fill_rect(x, y + 40, w, 12, (40, 44, 60))
    for i in range(10):
        rx = x + 10 + (i * 19) % 170
        ry = y + 16 + (i * 5) % 20
        cv.line(rx, ry, rx - 4, ry + 8, (160, 190, 205), 1)
    # race car silhouette, gold
    cv.fill_poly([(x + 52, y + 40), (x + 66, y + 28), (x + 110, y + 28),
                  (x + 128, y + 40)], GOLD)
    cv.fill_poly([(x + 66, y + 28), (x + 74, y + 22), (x + 100, y + 22),
                  (x + 110, y + 28)], (251, 247, 234))
    cv.fill_circle(x + 68, y + 42, 6, INK)
    cv.fill_circle(x + 68, y + 42, 2, GOLD)
    cv.fill_circle(x + 112, y + 42, 6, INK)
    cv.fill_circle(x + 112, y + 42, 2, GOLD)
    # checkered flag strip, right
    for r in range(2):
        for c in range(3):
            if (r + c) % 2 == 0:
                cv.fill_rect(x + 156 + c * 8, y + 16 + r * 8, 8, 8,
                             (251, 247, 234))
    cv.rect_outline(x + 156, y + 16, 24, 16, (251, 247, 234), 1)


SCENES = {"cop31": scene_cop31, "ukeu": scene_ukeu,
          "japan": scene_japan, "kenya": scene_kenya,
          "iraq": scene_iraq, "malawi": scene_malawi,
          "italy": scene_italy, "seoul": scene_seoul,
          "cricket": scene_cricket, "vegas": scene_vegas}

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


def art_kyiv(cv, x, y, w, h, serif_b):
    # HUD restyle: night panel, neon missile trails, gold bridge.
    cv.fill_rect(x, y, w, h, NIGHT)
    cv.fill_rect(x, y + h - 30, w, 30, (10, 26, 48))
    _stars(cv, x, y, w, 56, 26, (220, 225, 235))
    # skyline silhouettes, base at the river line
    base = y + h - 30
    heights = [26, 40, 18, 48, 30, 22, 44, 16, 34, 28]
    bx = x + 4
    for i, hh in enumerate(heights):
        bw = (w - 8) // len(heights)
        cv.fill_rect(bx, base - hh, bw - 3, hh, (16, 30, 58))
        if i in (1, 4, 6):
            cv.fill_rect(bx + 2, base - hh - 8, 3, 8, (16, 30, 58))
        bx += bw
    # river
    cv.fill_rect(x, base, w, h - (base - y), (28, 68, 120))
    cv.hline(x + 10, x + 120, base + 12, (90, 140, 190))
    cv.hline(x + 180, x + 300, base + 22, (90, 140, 190))
    # bridge: gold deck + three arches, middle arch broken
    cv.fill_rect(x + 8, base - 4, w - 16, 4, GOLD)
    for ax in (x + 30, x + 130, x + 230):
        cv.polyline(arc_points(ax + 32, base, 32, 14, 180, 360, 16),
                    GOLD, 2)
    cv.fill_rect(x + 148, base - 14, 14, 14, NIGHT)
    cv.line(x + 148, base, x + 162, base - 12, GOLD, 2)
    cv.line(x + 162, base, x + 156, base - 14, GOLD, 2)
    # neon missile trails
    for (sx, sy, ex, ey) in [(x + 300, y + 6, x + 250, y + 40),
                             (x + 270, y + 2, x + 210, y + 46),
                             (x + 180, y + 4, x + 150, y + 34)]:
        neon_line(cv, sx, sy, ex, ey, (120, 60, 20), (255, 200, 120))
        cv.fill_circle(ex, ey, 3, ORANGE)
    _burst(cv, x + 66, y + 58, 15)
    _burst(cv, x + 258, y + 48, 12)
    cv.fill_circle(x + 78, y + 44, 7, (120, 120, 120))
    cv.fill_circle(x + 88, y + 38, 5, (140, 140, 140))
    lead_banner(cv, serif_b, x + 6, y + 6, "KYIV", "3 bridges hit")
    hud_corners(cv, x, y, w, h, GOLD, 10, 2)


def art_akvan(cv, x, y, w, h, serif_b):
    # HUD restyle: radar rings + sweep over a dark sea, sand coast.
    cv.fill_rect(x, y, w, h, (12, 40, 66))
    cv.fill_rect(x, y, w, 3, CYAN)
    # rain slashes
    for i in range(14):
        rx = x + 8 + (i * 23) % 200
        ry = y + 46 + (i * 7) % 22
        cv.line(rx, ry, rx - 5, ry + 9, (120, 180, 200), 1)
    # Odisha coast, right side
    cv.fill_poly([(x + 238, y + 44), (x + 268, y + 52), (x + 292, y + 66),
                  (x + 320, y + 84), (x + 320, y + h), (x + 252, y + h),
                  (x + 240, y + 84), (x + 232, y + 60)], (200, 180, 130))
    cv.fill_circle(x + 282, y + 72, 7, (46, 139, 87))
    cv.fill_circle(x + 296, y + 92, 6, (46, 139, 87))
    cv.fill_circle(x + 268, y + 96, 6, (46, 139, 87))
    # cyclone eye + radar rings + sweep (kept inside the 118 px panel)
    cx, cy = x + 130, y + 76
    cv.circle_outline(cx, cy, 38, CYAN, 1)
    cv.circle_outline(cx, cy, 24, CYAN, 1)
    ang = math.radians(-35)
    cv.line(cx, cy, int(cx + 38 * math.cos(ang)),
            int(cy + 38 * math.sin(ang)), (180, 230, 240), 1)
    arm = []
    for k in range(120):
        t = k / 119.0 * 4.6 * math.pi
        r = 5 + t * 2.6
        arm.append((cx + r * math.cos(t), cy + r * math.sin(t) * 0.85))
    cv.polyline(arm, (251, 247, 234), 3)
    arm2 = []
    for k in range(90):
        t = k / 89.0 * 3.6 * math.pi + 2.2
        r = 5 + t * 2.6
        arm2.append((cx + r * math.cos(t), cy + r * math.sin(t) * 0.85))
    cv.polyline(arm2, (150, 210, 225), 2)
    cv.fill_circle(cx, cy, 8, (251, 247, 234))
    cv.fill_circle(cx, cy, 4, (12, 40, 66))
    # wave marks
    for wy in (y + 100, y + 108):
        for wx in range(x + 12, x + 190, 34):
            cv.polyline(arc_points(wx + 8, wy, 8, 3, 180, 360, 8),
                        (150, 200, 215), 1)
    lead_banner(cv, serif_b, x + 6, y + 6, "CYCLONE AKVAN",
                "Landfall - 8 am")
    hud_corners(cv, x, y, w, h, GOLD, 10, 2)


def art_markets(cv, x, y, w, h, serif_b):
    # HUD restyle: neon grid, red candles, close table on the right.
    cv.fill_rect(x, y, w, h, (16, 16, 24))
    for gy in range(y + 52, y + h - 8, 14):
        cv.hline(x + 6, x + w - 6, gy, (40, 40, 52))
    for gx in range(x + 24, x + w - 6, 26):
        cv.vline(gx, y + 52, y + h - 8, (32, 32, 44))
    tops = [58, 66, 62, 74, 70, 82, 78]
    bottoms = [74, 80, 84, 90, 94, 100, 102]
    for i, (t, b) in enumerate(zip(tops, bottoms)):
        bx = x + 14 + i * 26
        cv.vline(bx + 6, y + t - 5, y + b + 5, (200, 60, 60), 1)
        cv.fill_rect(bx, y + t, 12, b - t, (178, 34, 34))
    cv.polyline([(x + 20 + i * 26, y + t) for i, t in enumerate(tops)],
                (255, 90, 90), 2)
    # Friday closes table, right side (no arrow: the table is the data)
    # v3: Asia closes on top, US closes below the gold rule -- the
    # sell-off went global on Friday (S&P -3.70%, Nasdaq -5.28%).
    rows = [("TAIPEI", "-6.63%"), ("SEOUL", "-5.21%"),
            ("TOKYO", "-4.77%"), ("HONG KONG", "-1.89%"),
            ("NASDAQ", "-5.28%"), ("S&P 500", "-3.70%")]
    for i, (name, val) in enumerate(rows):
        ry = y + 56 + i * 10
        serif_b.draw(cv, x + 204, ry, name, 9, (251, 247, 234))
        vw = serif_b.text_width(val, 9)
        serif_b.draw(cv, x + 314 - vw, ry, val, 9, (255, 110, 110))
    cv.hline(x + 204, x + 314, y + 91, GOLD, 1)
    lead_banner(cv, serif_b, x + 6, y + 6, "AI SELL-OFF",
                "Asia to Wall St, Friday's close")
    hud_corners(cv, x, y, w, h, GOLD, 10, 2)

# ---------------------------------------------------------------- stories
# (num, region, place, field, headline, deck, art) -- every item dated
# 20 Nov 2026. Lead decks are trimmed to three lines at the v2 layout.
LEADS = [
    (1, "EUROPE", "KYIV, UKRAINE", "WAR",
     "Russia fires 110+ missiles and 400+ drones; three Kyiv bridges hit",
     "27 were ballistic, in waves 20-30 minutes apart. Eight killed - "
     "six in Kyiv, two in Lviv - and power, water and heating cut in "
     "five districts.",
     "kyiv"),
    (2, "ASIA-PACIFIC", "ODISHA, INDIA", "CYCLONE",
     "Cyclone Akvan makes landfall near Gopalpur; 300,000+ evacuated",
     "Crossed the Odisha coast with winds of 70-80 km/h, gusting to 90. "
     "209 mm of rain fell at Patrapur. No deaths were reported.",
     "akvan"),
    (3, "ASIA-PACIFIC", "ASIA TO WALL ST", "MARKETS",
     "AI sell-off goes global: Asia sinks, Wall St follows",
     "Friday closes: Nikkei -4.77%, KOSPI -5.21%, Taiex -6.63%; then "
     "S&P -3.70% to 6,910, Nasdaq -5.28% to 22,618, Dow -1.93%.",
     "markets"),
]

# (num, region, place, field, banner, headline, deck, scene) -- mediums
# are numbered 4 to 13; decks fit two lines in the v2 grid.
MEDIUMS = [
    (4, "WORLD", "ANTALYA", "CLIMATE", "COP31: NO DEAL",
     "COP31 ends its final day with no deal",
     "Draft drops fossil fuels and the $120bn goal; talks run into "
     "overtime.",
     "cop31"),
    (5, "EUROPE", "BRUSSELS", "DIPLOMACY", "UK-EU DEAL",
     "UK and EU seal reset deal",
     "100,000 youth visas a year; food checks end; carbon markets "
     "linked.",
     "ukeu"),
    (6, "ASIA-PACIFIC", "TOKYO", "ECONOMY", "JAPAN +2.3%",
     "Japan inflation 2.3%; rate rise eyed",
     "CPI 2.3% headline, 2.2% core; BoJ seen hiking to 1.50% in "
     "December.",
     "japan"),
    (7, "AFRICA", "TURKANA, KENYA", "ENERGY", "KENYA: OIL",
     "Kenya drills its first oil well",
     "Amosing 1 spudded in Turkana; first oil 1 Dec at 20,000 barrels "
     "a day.",
     "kenya"),
    (8, "MIDDLE EAST", "CENTRAL IRAQ", "SECURITY", "IRAQ: ARMY IN",
     "Iraqi troops enter militia stronghold",
     "Troops enter Jurf al-Sakhar, a Kataib Hezbollah base near "
     "Baghdad.",
     "iraq"),
    (9, "AFRICA", "BLANTYRE, MALAWI", "FUEL", "FUEL CRISIS",
     "Malawi rations fuel to 20 litres a day",
     "Queues for hours in Blantyre; black-market petrol $17 for two "
     "litres.",
     "malawi"),
    (10, "EUROPE", "ROME", "LABOUR", "ITALY: STRIKE",
     "Italy hit by 24-hour general strike",
     "Tens of thousands march in 100+ cities against the 2027 budget.",
     "italy"),
    (11, "ASIA-PACIFIC", "SEOUL", "COURTS", "SEOUL: IMPEACH",
     "Seoul moves to impeach top judge",
     "Ruling party moves against Chief Justice Cho Hee-dae in the Han "
     "case.",
     "seoul"),
    (12, "OCEANIA", "WELLINGTON", "CRICKET", "PHILLIPS: 118",
     "Phillips 118 powers New Zealand",
     "Phillips 118, Nicholls 175 not out; New Zealand 368 in "
     "Wellington.",
     "cricket"),
    (13, "AMERICAS", "LAS VEGAS", "FORMULA 1", "RUSSELL: P1",
     "Russell fastest in wet Las Vegas",
     "Russell fastest in a wet FP2, 1:47.272; FP1 washed out.",
     "vegas"),
]

# (region, one-line brief) -- numbered 14 to 33 in the page.
ALSO = [
    ("EUROPE", "POLAND: Kh-101 missile and a drone come down near the border; no injuries; Warsaw calls it a provocation."),
    ("EUROPE", "LVIV: Strike on Sknyliv station kills two and wrecks the ticket hall; 10 in hospital."),
    ("MIDDLE EAST", "OMAN: Tanker hit by an unknown projectile off Khasab; fire on board, no casualties. Brent about $92.50."),
    ("AMERICAS", "EL SALVADOR: Bukele files for a third term at Thursday night's deadline; vote 28 Feb 2027."),
    ("ASIA-PACIFIC", "CHINA-AUSTRALIA: Xi hails a 'comprehensive turnaround' as he meets Albanese in Shenzhen."),
    ("ASIA-PACIFIC", "CHINA: Lending rates held for an 18th month - 1-year 3.00%, 5-year 3.50%."),
    ("EUROPE", "ATP FINALS: Medvedev beats Tiafoe 6-3, 6-4 for the last semi; Alcaraz beats Cobolli 6-4, 6-1."),
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
    ("AMERICAS", "WALL ST: S&P -3.70% in correction, Nasdaq -5.28% as the AI rout reaches the US; Dow -1.93%."),
]

NUMBERS = [
    ("110+", "MISSILES FIRED AT UKRAINE"),
    ("300,000+", "EVACUATED IN ODISHA"),
    ("-6.63%", "TAIEX CLOSE, FRIDAY"),
    ("100,000", "YOUTH VISAS A YEAR"),
    ("20,000", "BARRELS A DAY, KENYA"),
    ("2.3%", "JAPAN INFLATION, OCT"),
]

# (story number, lon, lat, dx, dy) -- pins on the map. Europe's pins
# fan out with leader lines: the true positions sit within a few pixels.
# Fan offsets are tuned so every disc (glow r=10) stays >=4 px inside
# the panel -- 15 and 31 used to poke 4-6 px over the top edge.
PINS = [
    (1, 30.5, 50.4, 8, 10),
    (14, 22.0, 50.6, -41, -6),
    (15, 24.0, 49.8, 20, -8),
    (5, -0.1, 51.5, -26, 0),
    (10, 12.5, 41.9, -4, 22),
    (31, 13.4, 52.5, -2, -8),
    (20, 7.7, 45.1, -16, 16),
    (4, 30.7, 36.9, 28, 14),
    (2, 84.9, 19.3, 0, 0),
    (11, 127.0, 37.5, 0, 0),
    (6, 139.7, 35.7, 0, 0),
    (7, 36.0, 3.5, 0, 0),
    (12, 174.8, -41.3, 0, -8),
    (13, -115.1, 36.2, 0, 0),
]

REGION_COLOR = {
    "EUROPE": NAVY3,
    "ASIA-PACIFIC": TEAL,
    "AMERICAS": DARKRED,
    "MIDDLE EAST": (128, 90, 0),
    "AFRICA": (34, 110, 60),
    "OCEANIA": PURPLE,
    "WORLD": GREY,
}

# Date-check box content as (text, bold, colour): the title, the two
# section markers and the four biggest left-out stories are bold
# (labels red, stories navy); everything else is regular ink.
DATE_CHECK = [
    ("DATE CHECK -", True, RED),
    ("LEFT OUT AS 19 NOVEMBER NEWS:", True, NAVY),
    ("Shenzhen summit; Anthropic IPO; ICJ Myanmar verdict; GTA VI launch;",
     True, NAVY),
    ("Fiona the hippo; U17 Australia 2-0 Argentina; Lula-Raoni land deal; "
     "South Africa Test win; Senegal budget decree.", False, INK),
    ("NOT YET:", True, RED),
    ("BepiColombo Mercury arrival (21 Nov).", False, INK),
    ("IN THIS EDITION:", True, RED),
    ("US close; Medvedev win; COP31 overtime.", False, INK),
]

FOOTER = [
    "Sources: Reuters, CNN, AP, AFP, BBC, IMD, The Hindu, Morningstar, Aju Press, Cricbuzz, Formula1.com, ATP, UKMTO, UN News, Carbon Brief.",
    "Original drawings. Contested claims are attributed; market figures are Friday closes unless labelled intraday. Press time 21:00 UTC.",
]

ART = {"kyiv": art_kyiv, "akvan": art_akvan, "markets": art_markets}

# ---------------------------------------------------------------- layout
def build():
    base = os.path.dirname(os.path.abspath(__file__))
    serif = Font(os.path.join(base, "LiberationSerif-Regular.ttf"))
    serif_b = Font(os.path.join(base, "LiberationSerif-Bold.ttf"))
    serif_i = Font(os.path.join(base, "LiberationSerif-Italic.ttf"))
    cv = Canvas(W, H, CREAM)
    cv.fill_rect(0, 0, W, 80, NAVY)

    # masthead, dark band: gold label, near-white date, gold rule
    draw_spaced(cv, serif_b, W // 2, 24, "THE WORLD IN ONE DAY", 15, GOLD, 4)
    draw_centered(cv, serif_b, W // 2, 66, "Friday 20 November 2026", 44,
                  (251, 247, 234))
    cv.hline(24, 1000, 74, GOLD, 2)

    # story / region count strip, computed from the data
    # (leads and mediums carry the region at index 1, briefs at 0)
    counts = {}
    total = 0
    for item in LEADS + MEDIUMS:
        counts[item[1]] = counts.get(item[1], 0) + 1
        total += 1
    for (region, _text) in ALSO:
        counts[region] = counts.get(region, 0) + 1
        total += 1
    order = ["EUROPE", "ASIA-PACIFIC", "AMERICAS", "MIDDLE EAST", "AFRICA",
             "OCEANIA", "WORLD"]
    strip = "%d STORIES" % total
    for r in order:
        strip += "  |  %s %d" % (r, counts.get(r, 0))
    draw_centered(cv, serif_b, W // 2, 94, strip, 12, NAVY)

    # numbers strip: each box gets its own accent -- a tinted
    # background, a coloured border and the number in that colour
    # (same rotation as the also-list numbers, plus orange and gold)
    NUM_BOXES = [
        (RED, (248, 232, 232)),
        (BLUE, (232, 240, 248)),
        (TEAL, (228, 242, 244)),
        (PURPLE, (240, 234, 248)),
        (ORANGE, (255, 240, 224)),
        (GOLD, (248, 242, 222)),
    ]
    for i, (num, label) in enumerate(NUMBERS):
        x = 24 + i * 163
        col, tint = NUM_BOXES[i]
        cv.fill_rect(x, 102, 160, 46, tint)
        cv.rect_outline(x, 102, 160, 46, col, 2)
        draw_centered(cv, serif_b, x + 80, 128, num, 21, col)
        draw_centered(cv, serif_b, x + 80, 144, label, 9, INK)

    # three leads: art, then tag, headline and deck right under it
    # (no dead gap between art and text -- see the 19 Nov lead-gap fix)
    font = serif_b
    font.draw(cv, 24, 160, "THE DAY'S THREE BIG STORIES", 12, NAVY)
    cv.hline(24, 1000, 166, MIDGREY, 1)
    cols = [24, 352, 680]
    for (num, region, place, field, head, deck, art), x in zip(LEADS, cols):
        ART[art](cv, x, 172, 320, 118, serif_b)
        cv.rect_outline(x, 172, 320, 118, NAVY, 1)
        tag = "%d - %s - %s" % (num, place, field)
        serif_b.draw(cv, x, 302, tag, 11, RED)
        lines = wrap_text(serif_b, head, 19, 320)
        for j, ln in enumerate(lines):
            serif_b.draw(cv, x, 301 + j * 20 + 19, ln, 19, INK)
        dy = 301 + len(lines) * 20 + 8
        draw_wrapped(cv, serif, x, dy, deck, 12, INK, 320, 13)

    # medium grid, 5 columns x 2 rows, full HUD scenes
    cv.hline(24, 1000, 396, INK, 1)
    serif_b.draw(cv, 24, 412, "MORE OF THE DAY", 12, NAVY)
    for (num, region, place, field, banner, head, deck, scene) in MEDIUMS:
        idx = num - 4
        col = idx % 5
        row = idx // 5
        x = 24 + col * 196
        y = 420 + row * 136
        SCENES[scene](cv, x, y, 188, 58)
        scene_banner(cv, serif_b, x, y, 188, banner)
        cv.rect_outline(x, y, 188, 58, NAVY, 1)
        tag = "%d - %s - %s" % (num, place, field)
        serif_b.draw(cv, x, y + 72, tag, 10, REGION_COLOR[region])
        draw_wrapped(cv, serif_b, x, y + 76, head, 12, INK, 188, 14)
        draw_wrapped(cv, serif, x, y + 108, deck, 10, INK, 188, 11)

    # world map, dot-matrix HUD
    cv.hline(24, 1000, 696, INK, 1)
    serif_b.draw(cv, 24, 712, "WHERE IT HAPPENED", 12, NAVY)
    serif.draw(cv, 1000 - serif.text_width("14 OF TODAY'S 33 STORIES PINNED", 11),
               712, "14 OF TODAY'S 33 STORIES PINNED", 11, GREY)
    draw_map(cv, 24, 718, 976, 116, PINS, serif_b)

    # also list: each number wears its pin's colour (num_colour); only
    # the country/subject lead-in is bold navy, the rest is regular ink
    cv.hline(24, 1000, 842, INK, 1)
    serif_b.draw(cv, 24, 858, "ALSO ON FRIDAY 20 NOVEMBER", 12, NAVY)
    for i, (region, text) in enumerate(ALSO):
        col = i // 10
        row = i % 10
        x = 24 + col * 498
        y = 864 + row * 10
        num = "%d." % (14 + i)
        lead, rest = text.split(": ", 1)
        lead += ":"
        w = (serif_b.text_width(num, 9) + 3
             + serif_b.text_width(lead, 9) + 3
             + serif.text_width(rest, 9))
        if w > 474:
            print("also item %d too wide: %.0f" % (14 + i, w),
                  file=sys.stderr)
        serif_b.draw(cv, x, y + 9, num, 9, num_colour(14 + i))
        lx = x + serif_b.text_width(num, 9) + 3
        serif_b.draw(cv, lx, y + 9, lead, 9, NAVY)
        rx = lx + serif_b.text_width(lead, 9) + 3
        serif.draw(cv, rx, y + 9, rest, 9, INK)

    # date check box: red 2px border; title, section markers and the
    # four biggest left-out stories bold (labels red, stories navy)
    cv.fill_rect(24, 970, 976, 28, LIGHT)
    cv.rect_outline(24, 970, 976, 28, RED, 2)
    dc = [(t, serif_b if b else serif, c) for (t, b, c) in DATE_CHECK]
    draw_wrapped_mixed(cv, 32, 970, dc, 10, 960, 12)

    # footer, one line
    draw_centered(cv, serif, W // 2, 1010, " ".join(FOOTER), 8, GREY)
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
