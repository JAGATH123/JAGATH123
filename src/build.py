#!/usr/bin/env python3
"""Builds the VisionQuest-themed SVG assets used by the profile README.

Every piece of styled text is drawn as glyph outlines rather than live
fonts, so the images look identical wherever GitHub shows them. Fonts
(Orbitron, Rajdhani, Fira Code; all SIL OFL) are fetched once into
.fontcache/.

    python3 src/build.py
"""
import random
import re
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ROOT / ".fontcache"
GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"

# ── palette ─────────────────────────────────────────────────────────────
BG0 = "#07080D"      # deep space
PANEL = "#0A0C12"
EDGE = "#1C2130"
GOLD = "#FFC83D"     # mind stone
GOLD_DEEP = "#E8A317"
CRIMSON = "#C4183C"  # vision
CRIMSON_DEEP = "#7A0F26"
GREEN = "#2BD67B"    # online
SILVER = "#D7DEE8"   # ultron chrome
STEEL = "#8C96A6"
MUTED = "#6B7385"
TEXT = "#C9D1D9"
RED = "#FF4D5E"


# ── fonts → outlines ────────────────────────────────────────────────────
def _num(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


class Font:
    def __init__(self, key, filename, url, wght=None):
        CACHE.mkdir(exist_ok=True)
        path = CACHE / filename
        if not path.exists():
            urllib.request.urlretrieve(url, path)
        tt = TTFont(path)
        if wght is not None:
            tt = instancer.instantiateVariableFont(tt, {"wght": wght})
        self.key = key
        self.upem = tt["head"].unitsPerEm
        self.cmap = tt.getBestCmap()
        self.hmtx = tt["hmtx"]
        self.glyphset = tt.getGlyphSet()
        self._paths = {}

    def glyph(self, ch):
        name = self.cmap.get(ord(ch))
        if name is None:
            raise KeyError(f"font {self.key} has no glyph for {ch!r}")
        return name

    def advance(self, ch):
        return self.hmtx[self.glyph(ch)][0]

    def path(self, name):
        if name not in self._paths:
            pen = SVGPathPen(self.glyphset, ntos=_num)
            self.glyphset[name].draw(pen)
            self._paths[name] = pen.getCommands()
        return self._paths[name]

    def width(self, s, size, ls=0.0):
        return sum(self.advance(c) for c in s) * size / self.upem + ls * max(len(s) - 1, 0)

    def fit(self, s, size, max_w, ls=0.0):
        """Largest size <= `size` at which `s` fits in `max_w`."""
        w = self.width(s, size, ls)
        return size if w <= max_w else size * max_w / w


ORBITRON = Font("orb", "Orbitron[wght].ttf", GF + "orbitron/Orbitron%5Bwght%5D.ttf", 900)
ORBITRON_B = Font("orbb", "Orbitron[wght].ttf", GF + "orbitron/Orbitron%5Bwght%5D.ttf", 700)
RAJDHANI = Font("raj", "Rajdhani-SemiBold.ttf", GF + "rajdhani/Rajdhani-SemiBold.ttf")
RAJDHANI_B = Font("rajb", "Rajdhani-Bold.ttf", GF + "rajdhani/Rajdhani-Bold.ttf")
MONO = Font("mono", "FiraCode[wght].ttf", GF + "firacode/FiraCode%5Bwght%5D.ttf", 500)


# ── svg document ────────────────────────────────────────────────────────
class Svg:
    def __init__(self, w, h, label):
        self.w, self.h, self.label = w, h, label
        self.defs, self.body, self.glyphs = [], [], {}
        self._n = 0

    def uid(self, prefix):
        self._n += 1
        return f"{prefix}{self._n}"

    def add(self, *parts):
        self.body.extend(parts)

    def text(self, font, s, x, y, size, fill=None, anchor="start", ls=0.0, attrs=""):
        """Returns a <g> drawing `s` with its baseline at y, plus its width."""
        w = font.width(s, size, ls)
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        k = size / font.upem
        pen, uses = 0.0, []
        for ch in s:
            name = font.glyph(ch)
            d = font.path(name)
            if d:
                gid = re.sub(r"[^A-Za-z0-9_-]", "_", f"{font.key}-{name}")
                self.glyphs[gid] = d
                uses.append(f'<use xlink:href="#{gid}" x="{_num(pen)}"/>')
            pen += font.advance(ch) + ls / k
        fill_attr = f' fill="{fill}"' if fill else ""
        g = (f'<g transform="translate({_num(x)} {_num(y)}) scale({k:.5f} {-k:.5f})"'
             f'{fill_attr} {attrs}>{"".join(uses)}</g>')
        return g, w

    def put(self, *args, **kw):
        g, w = self.text(*args, **kw)
        self.add(g)
        return w

    def render(self):
        glyphs = "".join(f'<path id="{k}" d="{v}"/>' for k, v in self.glyphs.items())
        label = escape(self.label, {'"': "&quot;"})
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'role="img" aria-label="{label}"><title>{label}</title>'
                f'<defs>{"".join(self.defs)}{glyphs}</defs>{"".join(self.body)}</svg>\n')


# ── shared pieces ───────────────────────────────────────────────────────
def frame(svg, r=18, grid=True, tint=0.0):
    """Rounded dark panel; returns the closing tag for the clipped group."""
    w, h = svg.w, svg.h
    clip, bg, line = svg.uid("clip"), svg.uid("bg"), svg.uid("line")
    svg.defs.append(
        f'<clipPath id="{clip}"><rect width="{w}" height="{h}" rx="{r}"/></clipPath>'
        f'<linearGradient id="{bg}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{PANEL}"/><stop offset="1" stop-color="#0E0A12"/></linearGradient>'
        f'<linearGradient id="{line}" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{CRIMSON}" stop-opacity="0"/>'
        f'<stop offset=".3" stop-color="{CRIMSON}"/><stop offset=".7" stop-color="{GOLD}"/>'
        f'<stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></linearGradient>')
    svg.add(f'<g clip-path="url(#{clip})">',
            f'<rect width="{w}" height="{h}" fill="url(#{bg})"/>')
    if tint:
        glow = svg.uid("tint")
        svg.defs.append(f'<radialGradient id="{glow}" cx=".08" cy="1" r=".9">'
                        f'<stop offset="0" stop-color="{CRIMSON}" stop-opacity="{tint}"/>'
                        f'<stop offset="1" stop-color="{CRIMSON}" stop-opacity="0"/></radialGradient>')
        svg.add(f'<rect width="{w}" height="{h}" fill="url(#{glow})"/>')
    if grid:
        pat = svg.uid("grid")
        svg.defs.append(f'<pattern id="{pat}" width="32" height="32" patternUnits="userSpaceOnUse">'
                        f'<path d="M32 0H0V32" fill="none" stroke="#FFFFFF" stroke-opacity=".035"/></pattern>')
        svg.add(f'<rect width="{w}" height="{h}" fill="url(#{pat})"/>')
    svg.add(f'<rect y="0" width="{w}" height="2" fill="url(#{line})"/>')
    return (f'</g><rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{r}" '
            f'fill="none" stroke="{EDGE}"/>')


def gem(svg, cx, cy, s=1.0, glow=True, pulse=4.0):
    """The Mind Stone: a faceted gold crystal with a breathing glow."""
    outer = [(0, -55), (34, -22), (30, 28), (0, 55), (-30, 28), (-34, -22)]
    inner = [(0, -27), (16, -9), (14, 13), (0, 27), (-14, 13), (-16, -9)]
    shades = ["#FFD45A", "#E09A12", "#B97A08", "#D8950F", "#F2B227", "#FFE88A"]

    def pts(seq):
        return " ".join(f"{_num(cx + x * s)},{_num(cy + y * s)}" for x, y in seq)

    core = svg.uid("core")
    svg.defs.append(f'<radialGradient id="{core}" cx=".42" cy=".38" r=".7">'
                    f'<stop offset="0" stop-color="#FFFBE6"/><stop offset=".45" stop-color="#FFE07A"/>'
                    f'<stop offset="1" stop-color="{GOLD_DEEP}"/></radialGradient>')
    if glow:
        blur = svg.uid("blur")
        svg.defs.append(f'<filter id="{blur}" x="-150%" y="-150%" width="400%" height="400%">'
                        f'<feGaussianBlur stdDeviation="{_num(16 * s)}"/></filter>')
        svg.add(f'<ellipse cx="{_num(cx)}" cy="{_num(cy)}" rx="{_num(40 * s)}" ry="{_num(58 * s)}" '
                f'fill="{GOLD}" filter="url(#{blur})" opacity=".55">'
                f'<animate attributeName="opacity" values=".35;.85;.35" dur="{pulse}s" repeatCount="indefinite"/>'
                f'</ellipse>')
    facets = []
    for i in range(6):
        j = (i + 1) % 6
        facets.append(f'<polygon points="{pts([outer[i], outer[j], inner[j], inner[i]])}" fill="{shades[i]}"/>')
    sw = _num(max(0.6, 1.2 * s))
    svg.add(f'<g stroke="#FFF6D0" stroke-opacity=".35" stroke-width="{_num(0.8 * s)}" stroke-linejoin="round">',
            *facets,
            f'<polygon points="{pts(inner)}" fill="url(#{core})"/></g>',
            f'<polygon points="{pts(outer)}" fill="none" stroke="#7A4E00" stroke-width="{sw}" stroke-linejoin="round"/>',
            f'<ellipse cx="{_num(cx - 6 * s)}" cy="{_num(cy - 12 * s)}" rx="{_num(5 * s)}" ry="{_num(9 * s)}" '
            f'fill="#FFFFFF" opacity=".55" transform="rotate(-20 {_num(cx - 6 * s)} {_num(cy - 12 * s)})">'
            f'<animate attributeName="opacity" values=".35;.75;.35" dur="{pulse}s" repeatCount="indefinite"/>'
            f'</ellipse>')


def diamond(svg, cx, cy, r, fill=GOLD, opacity=1.0):
    svg.add(f'<polygon points="{_num(cx)},{_num(cy - r)} {_num(cx + r * .72)},{_num(cy)} '
            f'{_num(cx)},{_num(cy + r)} {_num(cx - r * .72)},{_num(cy)}" fill="{fill}" opacity="{opacity}"/>')


def specks(svg, n, box, seed):
    rnd = random.Random(seed)
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.choice([0.7, 0.9, 1.1, 1.5])
        c = rnd.choice([SILVER, SILVER, GOLD])
        dur, begin = rnd.uniform(2.5, 6), rnd.uniform(0, 5)
        svg.add(f'<circle cx="{_num(x)}" cy="{_num(y)}" r="{r}" fill="{c}" opacity=".5">'
                f'<animate attributeName="opacity" values=".1;.8;.1" dur="{dur:.1f}s" '
                f'begin="{begin:.1f}s" repeatCount="indefinite"/></circle>')


def status_dot(svg, cx, cy, color):
    svg.add(f'<circle cx="{cx}" cy="{cy}" r="4" fill="{color}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="4" fill="none" stroke="{color}">'
            f'<animate attributeName="r" values="4;10" dur="2s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values=".8;0" dur="2s" repeatCount="indefinite"/></circle>')


def arrow(svg, x, y, size, color):
    """A ↗ arrow with its lower-left corner at (x, y)."""
    s = size
    svg.add(f'<path d="M{_num(x)} {_num(y)}L{_num(x + s)} {_num(y - s)}M{_num(x + s * .35)} {_num(y - s)}'
            f'H{_num(x + s)}V{_num(y - s * .65)}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def wrap(font, s, size, max_w):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and font.width(trial, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def chip(svg, x, y, label, font, size, h, pad, stroke, fill, color, opacity=1.0):
    w = font.width(label, size) + pad * 2
    svg.add(f'<rect x="{_num(x)}" y="{_num(y)}" width="{_num(w)}" height="{h}" rx="{h * .25:.0f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-opacity="{opacity}"/>')
    svg.put(font, label, x + pad, y + h / 2 + size * .36, size, color)
    return w


# ── 1. header banner ────────────────────────────────────────────────────
def header():
    svg = Svg(1200, 420, "JAGATHGURU, Forward Deployed Engineer. "
                         "Vision core online, Ultron protocol offline.")
    close = frame(svg, r=22, tint=0.22)
    cx, cy = 935, 212

    halo = svg.uid("halo")
    svg.defs.append(f'<radialGradient id="{halo}" cx="{cx}" cy="{cy}" r="330" gradientUnits="userSpaceOnUse">'
                    f'<stop offset="0" stop-color="{GOLD}" stop-opacity=".26"/>'
                    f'<stop offset=".45" stop-color="{GOLD_DEEP}" stop-opacity=".07"/>'
                    f'<stop offset="1" stop-color="{GOLD_DEEP}" stop-opacity="0"/></radialGradient>')
    svg.add(f'<rect width="1200" height="420" fill="url(#{halo})"/>')
    specks(svg, 46, (20, 20, 1180, 400), seed=616)

    # slow scanline sweeping down the banner
    scan = svg.uid("scan")
    svg.defs.append(f'<linearGradient id="{scan}" x1="0" y1="0" x2="0" y2="1">'
                    f'<stop offset="0" stop-color="{GOLD}" stop-opacity="0"/>'
                    f'<stop offset="1" stop-color="{GOLD}" stop-opacity=".07"/></linearGradient>')
    svg.add(f'<rect x="0" y="-80" width="1200" height="80" fill="url(#{scan})">'
            f'<animate attributeName="y" values="-80;420" dur="7s" repeatCount="indefinite"/></rect>')

    # circuit traces feeding the core, with data pulses running along them
    traces = [
        f"M{cx - 150} {cy} H780 V{cy + 70} H700",
        f"M{cx} {cy - 150} V40 H1150",
        f"M{cx + 150} {cy} H1120 V{cy + 120} H1200",
        f"M{cx} {cy + 150} V395 H760",
        f"M{cx + 106} {cy - 106} L1130 70 H1200",
    ]
    for i, d in enumerate(traces):
        svg.add(f'<path d="{d}" fill="none" stroke="{EDGE}" stroke-width="1.5"/>'
                f'<path d="{d}" fill="none" stroke="{GOLD}" stroke-width="2" stroke-linecap="round" '
                f'stroke-dasharray="18 620" opacity=".9">'
                f'<animate attributeName="stroke-dashoffset" values="638;0" dur="{3.2 + i * .7:.1f}s" '
                f'begin="{i * .6:.1f}s" repeatCount="indefinite"/></path>')

    # HUD rings around the core
    rot = lambda dur, rev=False: (f'<animateTransform attributeName="transform" type="rotate" '
                                  f'values="{"360" if rev else "0"} {cx} {cy};{"0" if rev else "360"} {cx} {cy}" '
                                  f'dur="{dur}s" repeatCount="indefinite"/>')
    ticks = "".join(f'<line x1="{cx}" y1="{cy - 162}" x2="{cx}" y2="{cy - (170 if a % 30 == 0 else 166)}" '
                    f'transform="rotate({a} {cx} {cy})"/>' for a in range(0, 360, 6))
    svg.add(f'<g stroke="{STEEL}" stroke-opacity=".35" stroke-width="1.5">{ticks}</g>',
            f'<circle cx="{cx}" cy="{cy}" r="150" fill="none" stroke="{SILVER}" stroke-opacity=".35" '
            f'stroke-dasharray="2 7">{rot(80)}</circle>',
            f'<circle cx="{cx}" cy="{cy}" r="126" fill="none" stroke="{GOLD}" stroke-opacity=".55" '
            f'stroke-width="2" stroke-dasharray="90 30 14 30">{rot(46, rev=True)}</circle>',
            f'<circle cx="{cx}" cy="{cy}" r="104" fill="none" stroke="{CRIMSON}" stroke-opacity=".75" '
            f'stroke-width="3" stroke-dasharray="210 444" stroke-linecap="round">{rot(18)}</circle>',
            f'<circle cx="{cx}" cy="{cy}" r="104" fill="none" stroke="{CRIMSON_DEEP}" stroke-opacity=".5"/>',
            f'<line x1="{cx}" y1="{cy - 92}" x2="{cx}" y2="{cy - 150}" stroke="{GOLD}" stroke-opacity=".55" '
            f'stroke-width="2">{rot(9)}</line>')
    gem(svg, cx, cy, s=1.15)

    # top HUD bar
    status_dot(svg, 64, 47, GREEN)
    x = 80 + svg.put(MONO, "VISION_CORE", 80, 52, 14, STEEL, ls=2)
    svg.put(MONO, "ONLINE", x + 14, 52, 14, GREEN, ls=2)
    w = MONO.width("OFFLINE", 14, 2)
    svg.put(MONO, "OFFLINE", 1136, 52, 14, RED, anchor="end", ls=2)
    svg.add(f'<rect x="{_num(1136 - w - 22)}" y="42" width="9" height="9" fill="{RED}" opacity=".85"/>')
    svg.put(MONO, "ULTRON_PROTOCOL", 1136 - w - 34, 52, 14, MUTED, anchor="end", ls=2)

    # identity block
    svg.put(MONO, "> IDENTITY CONFIRMED", 64, 132, 16, GOLD, ls=3)
    svg.add(f'<rect x="{_num(64 + MONO.width("> IDENTITY CONFIRMED", 16, 3) + 6)}" y="119" width="10" '
            f'height="16" fill="{GOLD}"><animate attributeName="opacity" values="1;0" dur="1s" '
            f'calcMode="discrete" repeatCount="indefinite"/></rect>')

    name = "JAGATHGURU"
    size = ORBITRON.fit(name, 78, 640, ls=2)
    glyphs, nw = svg.text(ORBITRON, name, 64, 218, size, ls=2)
    mask, chrome, sheen = svg.uid("mask"), svg.uid("chrome"), svg.uid("sheen")
    svg.defs.append(
        f'<mask id="{mask}" maskUnits="userSpaceOnUse" x="0" y="0" width="1200" height="420">'
        f'<g fill="#FFFFFF">{glyphs}</g></mask>'
        f'<linearGradient id="{chrome}" x1="0" y1="150" x2="0" y2="220" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#FFFFFF"/><stop offset=".55" stop-color="{SILVER}"/>'
        f'<stop offset="1" stop-color="{STEEL}"/></linearGradient>'
        f'<linearGradient id="{sheen}" x1="64" y1="0" x2="{_num(64 + nw)}" y2="0" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{GOLD}" stop-opacity="0"/>'
        f'<stop offset=".42" stop-color="{GOLD}" stop-opacity="0"/>'
        f'<stop offset=".5" stop-color="#FFE9A8" stop-opacity=".95"/>'
        f'<stop offset=".58" stop-color="{GOLD}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{GOLD}" stop-opacity="0"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'values="{_num(-nw)} 0;{_num(nw)} 0;{_num(nw)} 0" keyTimes="0;.45;1" dur="7s" repeatCount="indefinite"/>'
        f'</linearGradient>')
    svg.add(f'<rect width="1200" height="420" fill="url(#{chrome})" mask="url(#{mask})"/>',
            f'<rect width="1200" height="420" fill="url(#{sheen})" mask="url(#{mask})"/>')

    svg.put(RAJDHANI_B, "FORWARD DEPLOYED ENGINEER", 66, 266, 31, GOLD, ls=6.5)
    diamond(svg, 70, 294, 6)
    svg.add(f'<rect x="84" y="293" width="440" height="2" fill="{CRIMSON}"/>'
            f'<rect x="84" y="293" width="60" height="2" fill="{GOLD}">'
            f'<animate attributeName="x" values="84;464;84" dur="6s" repeatCount="indefinite"/></rect>')
    svg.put(RAJDHANI, "AI systems, shipped where the real work happens.", 66, 334, 25, TEXT)
    svg.put(MONO, "SYS.01  ·  MIND-STONE CORE: STABLE  ·  OPTIMISM: 100%", 66, 384, 13, MUTED, ls=1.5)

    svg.add(close)
    return svg


# ── 2. typing terminal line ─────────────────────────────────────────────
def typing():
    lines = [
        "deploying AI where the real work happens",
        "embedded with teams: prototype -> production",
        "turning models into tools people trust",
        "built to serve. never to rule.",
    ]
    svg = Svg(1200, 76, "Terminal: " + " / ".join(lines))
    close = frame(svg, r=16, grid=False)
    size, y = 21, 46
    x = 34 + svg.put(MONO, "jagath@vision-core", 34, y, size, GOLD)
    x += svg.put(MONO, ":~$", x, y, size, MUTED) + 14

    per, n = 5.0, len(lines)
    total = per * n
    blink = (f'<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" '
             f'repeatCount="indefinite"/>')
    cursor_keys, cursor_vals = [], []
    for i, line in enumerate(lines):
        clip = svg.uid("type")
        keys, vals = [0.0], [0.0]
        start = i * per
        type_t, hold_t, erase_t = 1.9, 2.4, 0.6
        steps = len(line)
        for k in range(1, steps + 1):
            keys.append((start + type_t * k / steps) / total)
            vals.append(MONO.width(line[:k], size) + 2)
        keys.append((start + type_t + hold_t) / total)
        vals.append(vals[-1])
        for k in range(steps - 1, -1, -1):
            keys.append((start + type_t + hold_t + erase_t * (steps - k) / steps) / total)
            vals.append(MONO.width(line[:k], size) + 2 if k else 0.0)
        if keys[1] == 0.0:
            keys[1] = 0.0001
        cursor_keys += keys if i == 0 else keys[1:]
        cursor_vals += vals if i == 0 else vals[1:]
        kt = ";".join(f"{v:.4f}" for v in keys)
        vv = ";".join(_num(v) for v in vals)
        svg.defs.append(f'<clipPath id="{clip}"><rect x="{_num(x)}" y="10" width="0" height="56">'
                        f'<animate attributeName="width" values="{vv}" keyTimes="{kt}" calcMode="discrete" '
                        f'dur="{total}s" repeatCount="indefinite"/></rect></clipPath>')
        g, _ = svg.text(MONO, line, x, y, size, SILVER)
        svg.add(f'<g clip-path="url(#{clip})">{g}</g>')
    kt = ";".join(f"{v:.4f}" for v in cursor_keys)
    vv = ";".join(_num(x + v) for v in cursor_vals)
    svg.add(f'<rect x="{_num(x)}" y="28" width="11" height="22" fill="{GOLD}">'
            f'<animate attributeName="x" values="{vv}" keyTimes="{kt}" calcMode="discrete" '
            f'dur="{total}s" repeatCount="indefinite"/>{blink}</rect>')
    svg.add(close)
    return svg


# ── 3. section headers ──────────────────────────────────────────────────
def section(num, title, note):
    svg = Svg(1200, 92, f"{num}: {title}")
    close = frame(svg, r=16, grid=False)
    gem(svg, 48, 46, s=0.36, glow=True, pulse=3.0)
    x = 78 + svg.put(MONO, num, 78, 56, 20, GOLD)
    x += 18 + svg.put(ORBITRON_B, title, x + 18, 58, 30, SILVER, ls=5)
    nw = svg.put(MONO, note, 1150, 54, 15, MUTED, anchor="end")
    x0, x1 = x + 28, 1150 - nw - 28
    rail = svg.uid("rail")
    svg.defs.append(f'<linearGradient id="{rail}" x1="0" y1="0" x2="1" y2="0">'
                    f'<stop offset="0" stop-color="{CRIMSON}"/><stop offset=".6" stop-color="{CRIMSON_DEEP}"/>'
                    f'<stop offset="1" stop-color="{CRIMSON_DEEP}" stop-opacity="0"/></linearGradient>')
    svg.add(f'<rect x="{_num(x0)}" y="45" width="{_num(x1 - x0)}" height="2" fill="url(#{rail})"/>',
            f'<circle cx="{_num(x0)}" cy="46" r="3.5" fill="{GOLD}">'
            f'<animate attributeName="cx" values="{_num(x0)};{_num(x1)}" dur="3.5s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="1;1;0" keyTimes="0;.8;1" dur="3.5s" '
            f'repeatCount="indefinite"/></circle>')
    svg.add(close)
    return svg


# ── 4. mission brief ────────────────────────────────────────────────────
BRIEF = [
    ("DESIGNATION", "Jagathguru Jagadeesan"),
    ("ROLE", "Forward Deployed Engineer · AI Systems"),
    ("OPERATING MODE", "Embedded with the people who use the system. Ship, measure, iterate."),
    ("CURRENT OBJECTIVE", "Sign language translation with Transformers"),
    ("UPGRADING", "LLMs · Agentic systems · Advanced AI architectures"),
    ("PRIME DIRECTIVE", "Build AI that helps people — never AI that rules them."),
]


def brief():
    row_h, top = 46, 128
    h = top + row_h * (len(BRIEF) - 1) + 52
    svg = Svg(1200, h, "Mission brief. " + " ".join(f"{k}: {v}." for k, v in BRIEF))
    close = frame(svg, tint=0.18)
    svg.add(f'<rect x="0" y="0" width="6" height="{h}" fill="{CRIMSON}"/>')
    svg.put(ORBITRON_B, "MISSION BRIEF", 56, 66, 22, SILVER, ls=4)
    svg.put(MONO, "// CLASSIFICATION: OPEN", 56 + ORBITRON_B.width("MISSION BRIEF", 22, 4) + 22,
            65, 14, MUTED, ls=1)

    label = "AVAILABLE FOR DEPLOYMENT"
    cw = MONO.width(label, 14, 2) + 58
    cx0 = 1144 - cw
    svg.add(f'<rect x="{_num(cx0)}" y="40" width="{_num(cw)}" height="36" rx="18" fill="#0C1A13" '
            f'stroke="{GREEN}" stroke-opacity=".55"/>')
    status_dot(svg, _num(cx0 + 22), 58, GREEN)
    svg.put(MONO, label, cx0 + 38, 63, 14, GREEN, ls=2)
    svg.add(f'<rect x="56" y="92" width="1088" height="1" fill="{EDGE}"/>')

    for i, (k, v) in enumerate(BRIEF):
        y = top + i * row_h
        last = i == len(BRIEF) - 1
        if last:
            svg.add(f'<rect x="40" y="{y - 31}" width="1120" height="44" rx="10" fill="{GOLD}" '
                    f'fill-opacity=".06" stroke="{GOLD}" stroke-opacity=".25"/>')
        diamond(svg, 60, y - 6, 4.5, GOLD if last else CRIMSON)
        svg.put(MONO, k, 76, y, 14, GOLD, ls=2)
        size = RAJDHANI.fit(v, 25, 1144 - 330)
        svg.put(RAJDHANI_B if last else RAJDHANI, v, 330, y + 1, size, GOLD if last else TEXT)
    svg.add(close)
    return svg


# ── 5. deployment cards ─────────────────────────────────────────────────
PROJECTS = [
    ("code-runner", "PLATFORM", "CODE RUNNER",
     "Sandboxed coding platform where learners write and run Python in isolated Docker containers.",
     ["TypeScript", "Docker", "Redis", "BullMQ"]),
    ("emotion-kiosk", "APPLIED AI", "EMOTION KIOSK",
     "Webcam kiosk that turns post-workshop expressions into anonymous feedback for trainers.",
     ["Next.js", "FastAPI", "DeepFace", "PostgreSQL"]),
    ("coodu-trust", "CLIENT BUILD", "COODU TRUST",
     "Website for a non-profit driving women's empowerment, health and livelihoods in India.",
     ["HTML", "CSS", "JavaScript", "Cloudinary"]),
    ("brain-mri", "MEDICAL AI", "BRAIN MRI SEGMENTATION",
     "U-Net that segments brain metastases in MRI scans for faster, more consistent diagnosis.",
     ["Python", "U-Net", "FastAPI", "Streamlit"]),
    ("sign-language", "ACCESSIBILITY AI", "SIGN TO SPEECH",
     "Real-time CNN that reads ASL finger-spelling and speaks it aloud for deaf and hearing users.",
     ["Python", "CNN", "Computer Vision", "TTS"]),
    ("evis", "VISION AI", "EVIS",
     "Emergency Vehicle Identification System: a deep-learning model that spots emergency vehicles.",
     ["Python", "TensorFlow", "Keras", "CNN"]),
]


def card(i, kind, title, desc, tags):
    svg = Svg(600, 270, f"Deployment {i:02d}, {kind}: {title}. {desc} Built with {', '.join(tags)}.")
    close = frame(svg, r=18)
    gem(svg, 40, 44, s=0.24, glow=True, pulse=3.0 + i * .3)
    svg.put(MONO, f"DEPLOYMENT {i:02d} // {kind}", 60, 50, 13, GOLD, ls=2)
    svg.put(MONO, "OPEN", 540, 50, 13, STEEL, anchor="end", ls=2)
    arrow(svg, 548, 52, 12, GOLD)

    size = ORBITRON_B.fit(title, 30, 530, ls=2)
    svg.put(ORBITRON_B, title, 36, 106, size, SILVER, ls=2)
    for j, line in enumerate(wrap(RAJDHANI, desc, 21, 530)[:2]):
        svg.put(RAJDHANI, line, 36, 146 + j * 27, 21, "#9AA4B2")
    x = 36
    for t in tags:
        x += chip(svg, x, 204, t, MONO, 14, 32, 13, CRIMSON, "#140B10", "#E7C9CF", .55) + 10

    bar = svg.uid("bar")
    svg.defs.append(f'<linearGradient id="{bar}" x1="0" y1="0" x2="1" y2="0">'
                    f'<stop offset="0" stop-color="{CRIMSON}"/><stop offset="1" stop-color="{GOLD}"/>'
                    f'</linearGradient>')
    svg.add(f'<rect x="0" y="266" width="600" height="4" fill="url(#{bar})" opacity=".85"/>')
    svg.add(close)
    return svg


# ── 6. arsenal ──────────────────────────────────────────────────────────
ARSENAL = [
    ("INTELLIGENCE", "models & ML",
     ["Python", "PyTorch", "TensorFlow", "Transformers", "Hugging Face", "LangChain", "DeepFace"]),
    ("BUILD", "apps & APIs",
     ["TypeScript", "Next.js", "React", "FastAPI", "Django", "Node.js", "Tailwind", "Streamlit"]),
    ("DEPLOY", "infra & ops",
     ["AWS", "Docker", "PostgreSQL", "Redis", "BullMQ", "Nginx", "Cloudflare Tunnel", "Firebase"]),
]


def arsenal():
    size, ch, gap, x0, x1 = 20, 40, 10, 300, 1150
    rows, y = [], 44
    for label, note, items in ARSENAL:
        widths = [RAJDHANI.width(it, size) + 36 for it in items]
        # overflowing rows split into even halves rather than leaving one chip orphaned
        per_line = len(items) if sum(widths) + gap * (len(items) - 1) <= x1 - x0 else -(-len(items) // 2)
        placed, x, yy = [], x0, y
        for n, (it, w) in enumerate(zip(items, widths)):
            if n and n % per_line == 0:
                x, yy = x0, yy + ch + gap
            placed.append((it, x, yy))
            x += w + gap
        rows.append((label, note, y, placed))
        y = yy + ch + 40
    h = y - 10
    svg = Svg(1200, h, "Arsenal. " + " ".join(f"{l}: {', '.join(i)}." for l, _, i in ARSENAL))
    close = frame(svg, tint=0.12)
    for n, (label, note, ry, placed) in enumerate(rows):
        if n:
            svg.add(f'<rect x="56" y="{ry - 21}" width="1088" height="1" fill="{EDGE}"/>')
        diamond(svg, 62, ry + 14, 6, [CRIMSON, GOLD, SILVER][n])
        svg.put(ORBITRON_B, label, 80, ry + 21, 18, SILVER, ls=3)
        svg.put(MONO, note, 80, ry + 44, 13, MUTED, ls=1)
        for it, x, yy in placed:
            chip(svg, x, yy, it, RAJDHANI, size, ch, 18, SILVER, "#10131A", TEXT, .22)
    svg.add(close)
    return svg


# ── 7. open channel buttons ─────────────────────────────────────────────
def button(kind, label, sub):
    svg = Svg(390, 96, f"{label}: {sub}")
    close = frame(svg, r=16, grid=False)
    cx, cy = 46, 48
    st = f'fill="none" stroke="{GOLD}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "web":
        svg.add(f'<circle cx="{cx}" cy="{cy}" r="16" {st}/>'
                f'<ellipse cx="{cx}" cy="{cy}" rx="7" ry="16" {st}/>'
                f'<path d="M{cx - 16} {cy}H{cx + 16}M{cx - 13} {cy - 8}H{cx + 13}M{cx - 13} {cy + 8}H{cx + 13}" {st}/>')
    elif kind == "linkedin":
        svg.add(f'<rect x="{cx - 16}" y="{cy - 16}" width="32" height="32" rx="6" {st}/>')
        svg.put(RAJDHANI_B, "in", cx, cy + 8, 22, GOLD, anchor="middle")
    else:
        svg.add(f'<rect x="{cx - 17}" y="{cy - 12}" width="34" height="24" rx="4" {st}/>'
                f'<path d="M{cx - 15} {cy - 9}L{cx} {cy + 3}L{cx + 15} {cy - 9}" {st}/>')
    svg.put(ORBITRON_B, label, 82, 46, 19, SILVER, ls=3)
    svg.put(MONO, sub, 82, 70, 12.5, MUTED)
    arrow(svg, 344, 56, 14, GOLD)
    svg.add(f'<rect x="0" y="92" width="390" height="4" fill="{CRIMSON}" opacity=".7"/>')
    svg.add(close)
    return svg


# ── 8. footer ───────────────────────────────────────────────────────────
def footer():
    svg = Svg(1200, 230, "Built to serve, not to rule. End of transmission.")
    close = frame(svg, r=22, grid=False)
    sun = svg.uid("sun")
    svg.defs.append(f'<radialGradient id="{sun}" cx="600" cy="250" r="330" gradientUnits="userSpaceOnUse">'
                    f'<stop offset="0" stop-color="{GOLD}" stop-opacity=".55"/>'
                    f'<stop offset=".35" stop-color="{GOLD_DEEP}" stop-opacity=".18"/>'
                    f'<stop offset=".7" stop-color="{CRIMSON}" stop-opacity=".06"/>'
                    f'<stop offset="1" stop-color="{CRIMSON}" stop-opacity="0"/></radialGradient>')
    svg.add(f'<rect width="1200" height="230" fill="url(#{sun})">'
            f'<animate attributeName="opacity" values=".75;1;.75" dur="8s" repeatCount="indefinite"/></rect>')
    specks(svg, 30, (20, 15, 1180, 170), seed=2026)
    hz = svg.uid("hz")
    svg.defs.append(f'<linearGradient id="{hz}" x1="0" y1="0" x2="1" y2="0">'
                    f'<stop offset="0" stop-color="{GOLD}" stop-opacity="0"/>'
                    f'<stop offset=".5" stop-color="{GOLD}"/>'
                    f'<stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></linearGradient>')
    for k, (r, o) in enumerate([(150, .45), (230, .25), (320, .12)]):
        svg.add(f'<circle cx="600" cy="250" r="{r}" fill="none" stroke="{GOLD}" stroke-opacity="{o}" '
                f'stroke-dasharray="{"" if k == 0 else "3 9"}"/>')
    svg.add(f'<rect x="100" y="196" width="1000" height="1.5" fill="url(#{hz})"/>')
    gem(svg, 600, 50, s=0.42, pulse=4.5)

    parts = ["BUILT TO SERVE", "NOT TO RULE"]
    size, ls, gap = 25, 7, 44
    w0 = ORBITRON_B.width(parts[0], size, ls)
    w1 = ORBITRON_B.width(parts[1], size, ls)
    x = 600 - (w0 + gap + w1) / 2
    svg.put(ORBITRON_B, parts[0], x, 124, size, SILVER, ls=ls)
    diamond(svg, x + w0 + gap / 2, 115, 6)
    svg.put(ORBITRON_B, parts[1], x + w0 + gap, 124, size, SILVER, ls=ls)
    svg.put(MONO, "// end of transmission · vision core standing by", 600, 162, 14, MUTED,
            anchor="middle", ls=1)
    svg.add(close)
    return svg


def main():
    ASSETS.mkdir(exist_ok=True)
    out = {
        "header.svg": header(),
        "typing.svg": typing(),
        "section-directive.svg": section("01", "DIRECTIVE", "// who is behind the core"),
        "section-deployments.svg": section("02", "DEPLOYMENTS", "// systems in the field"),
        "section-arsenal.svg": section("03", "ARSENAL", "// tools of the trade"),
        "section-telemetry.svg": section("04", "TELEMETRY", "// live signal"),
        "section-channel.svg": section("05", "OPEN CHANNEL", "// make contact"),
        "mission-brief.svg": brief(),
        "arsenal.svg": arsenal(),
        "btn-portfolio.svg": button("web", "PORTFOLIO", "jagath123.github.io"),
        "btn-linkedin.svg": button("linkedin", "LINKEDIN", "in/Jagath-Guru"),
        "btn-email.svg": button("mail", "EMAIL", "jagathguru134@gmail.com"),
        "footer.svg": footer(),
    }
    for i, p in enumerate(PROJECTS, 1):
        out[f"card-{p[0]}.svg"] = card(i, *p[1:])
    for name, svg in out.items():
        data = svg.render()
        (ASSETS / name).write_text(data)
        print(f"{name:28} {len(data) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
