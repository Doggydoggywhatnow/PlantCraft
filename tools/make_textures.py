#!/usr/bin/env python3
"""Graphics phase: draw a 16x16 pixel-art texture for every growth stage of every plant.

    python3 tools/make_textures.py            # textures/ + docs/preview/
    python3 tools/make_textures.py --check    # only verify every stage has a texture

Each plants/*.yaml lists its growth_stages (and segment_textures) with a planned `texture` path; this script
draws one PNG per entry at exactly that path, then writes preview sheets. Art is drawn from the descriptions in
the plant files; reference photos are not copied, so the textures are original pixel art.

Every plant shows its BRANCHES: the branching skeleton (forking stems, twigs, whorls) is drawn first and the
leaves, flowers and fruit hang off it. Datura forks repeatedly, with a leaf at each fork and a flower on the
tips (Wikipedia: Datura stramonium); rosemary has woody stems with needle leaves along them; eucalyptus and
peach foliage tiles are twigs with opposite (eucalyptus) or alternate (peach) leaves.

Species that differ only in recorded traits (leaf colour, flower colour, capsule shape, hairiness) are
distinguished by those traits. Where the sources are thin, the look is a placeholder variation on the genus
design and is marked so in the plant file's status, not invented botany.
"""
import argparse
import random
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SIZE = 16


# ------------------------------------------------------------------ helpers
def hx(c, a=255):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), a)


def parse(rows, ox=0, oy=0):
    """ASCII rows -> {(x, y): char}; '.' is transparent."""
    return {(ox + x, oy + y): ch for y, row in enumerate(rows) for x, ch in enumerate(row) if ch != "."}


def render(pix, palette, n=SIZE):
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    for (x, y), ch in pix.items():
        if 0 <= x < n and 0 <= y < n:
            img.putpixel((x, y), palette[ch] if ch in palette else hx("#ff00ff"))  # magenta = missing palette key
    return img


def line(pix, x0, y0, x1, y1, ch):
    """Bresenham line into pix (coordinates are rounded to whole pixels, so a float can never loop forever)."""
    x0, y0, x1, y1 = round(x0), round(y0), round(x1), round(y1)
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    pts = []
    while True:
        pix[(x0, y0)] = ch
        pts.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return pts
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def poly(pix, points, ch):
    """Draw a polyline, return its pixels in order (no repeats)."""
    out = []
    for (a, b), (c, d) in zip(points, points[1:]):
        seg = line(pix, a, b, c, d, ch)
        out += seg if not out else seg[1:]
    return out


def blob(pix, cx, cy, rx, ry, ch="L", edge="l"):
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            if (dx / (rx + 0.5)) ** 2 + (dy / (ry + 0.5)) ** 2 <= 1:
                pix[(cx + dx, cy + dy)] = edge if (dy == ry and ry > 0) else ch


def place(pix, shape, ox, oy, remap=None):
    for (dx, dy), ch in shape.items():
        pix[(ox + dx, oy + dy)] = (remap or {}).get(ch, ch)


def outlined(pix, shape, ox, oy, remap=None):
    """Place a shape with a 1px dark outline so it reads against the foliage."""
    cells = {(ox + dx, oy + dy) for (dx, dy) in shape}
    for (x, y) in cells:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in cells:
                pix[(nx, ny)] = "o"
    place(pix, shape, ox, oy, remap)


def normals(path, i):
    """Unit normal to a pixel path at index i."""
    a, b = path[max(0, i - 1)], path[min(len(path) - 1, i + 1)]
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = (dx * dx + dy * dy) ** 0.5 or 1
    return (-dy / n, dx / n)


# ------------------------------------------------------------------ Datura (forking stems)
SEED = [
    "................", "................", "................", "................", "................",
    "................", "................",
    ".....KK.........",
    "....KkKK..KK....",
    "....KKKK.KkKK...",
    ".....KK..KKKK...",
    "..KK......KK....",
    ".KkKK...........",
    ".KKKK....KK.....",
    "..KK....KkKK....",
    ".........KK.....",
]
SEEDLING = [
    "................", "................", "................", "................", "................",
    "................", "................", "................", "................", "................",
    "................",
    ".....LL....LL...",
    "....LLLL..LLLL..",
    ".....lLLTLLLl...",
    ".......T........",
    ".......T........",
]
TRUMPET_BIG = parse(["FHF", ".F.", ".f.", ".f."])        # large-flowered species: a flared mouth on a long tube
TRUMPET_SMALL = parse(["FHF", ".f."])                    # small-flowered species
BUD = parse(["B", "b"])
LEAF_L = parse(["LL.", "lLL"])                           # small leaves, drawn left- and right-leaning
LEAF_R = parse([".LL", "LLl"])
SPINY = parse(["pCp", "CcC", "pCp"])                     # ~3 px spiny capsule
LONG = parse(["p..p", ".CC.", "pCcp", "p..p"])           # D. ferox: few long thorns
SMOOTH = parse(["CC.", "CCC", "CcC", ".C."])             # D. ceratocaula: smooth, hanging egg shape
SPLIT = parse(["d..d", "DKKD", ".DD."])                  # ripe capsule split open, seeds showing
SPLIT_LONG = parse(["d.pd", "DKKD", ".DD."])

DATURA_DEFAULT = dict(
    leaf="#58903c", leaf_d="#3a6b2b", stem="#8fae5f",
    flower="#f4f1e8", rim="#ffffff", throat="#d4cbe6",
    bud="#e8e4d0", bud_d="#bdb89a",
    cap="#b6cf4e", cap_d="#7d9a2c", spine="#f3f7c8",
    ripe="#8a6a3a", ripe_d="#5e4527", seed="#1c1a1a", seed_hi="#4a4040",
    fuzz="#c8d0c0",
    capstyle="spiny", flowers="big",
)

DATURA = {
    "datura_stramonium": dict(),
    "datura_wrightii": dict(leaf="#6c9a6a", leaf_d="#4d7a50", flower="#f7f3ee", throat="#e6d8f0", fuzz="#cfd8cf", fuzzy=0.12),
    "datura_innoxia": dict(leaf="#8aa488", leaf_d="#627f63", stem="#a9b89a", fuzzy=0.30, fuzz="#d9e0d4"),
    "datura_metel": dict(leaf="#4a7a3a", leaf_d="#5b3f73", flower="#a276d6", rim="#d9c2f5", throat="#5f3f99",
                         bud="#b894e6", bud_d="#7a54b8", capstyle="warty"),
    "datura_ferox": dict(leaf="#6a9a46", leaf_d="#46732f", flower="#f0ecc4", rim="#fbf8de", throat="#cfc98f",
                         flowers="small", capstyle="long", cap="#7a5a3a", cap_d="#4a3320", spine="#e0c89a",
                         ripe="#7a4a2e", ripe_d="#4d2d1b"),
    "datura_quercifolia": dict(leaf="#3f7a3a", leaf_d="#2c5a2b", flower="#efe9f4", throat="#b9a6dc", capstyle="long", ragged=True),
    "datura_discolor": dict(leaf="#7cab5c", leaf_d="#55823f", stem="#8a3f8a", flower="#f7f4fb", rim="#ffffff",
                            throat="#7a3fa6", bud="#b894d4", bud_d="#7a3fa6"),
    "datura_ceratocaula": dict(leaf="#7a9a78", leaf_d="#58775a", stem="#8fa592", flower="#f3f0fb", throat="#e9b9d6",
                               rim="#ffffff", capstyle="smooth", cap="#c9d98a", cap_d="#8fa650", curve=True),
    "datura_leichhardtii": dict(leaf="#6e9a52", leaf_d="#4c7a3a", flower="#efe8bf", rim="#f8f3d6", throat="#cfc88f",
                                flowers="small", fuzzy=0.10),
    # Thin-source species: placeholder variations on traits the sources do give.
    "datura_kymatocarpa": dict(leaf="#7aa85a", leaf_d="#55823f", stem="#8a3f8a", throat="#7a3fa6", rim="#ffffff"),
    "datura_reburra": dict(leaf="#6ea057", leaf_d="#4d7a3d", stem="#8a3f8a", throat="#7a3fa6", rim="#ffffff"),
    "datura_lanosa": dict(leaf="#9ab294", leaf_d="#728c70", fuzzy=0.40, fuzz="#e8ece4", stem="#b5c4a8"),
    "datura_arenicola": dict(leaf="#9cb06a", leaf_d="#7a8f4c", stem="#c4b88a"),
    "datura_pruinosa": dict(leaf="#7fa49a", leaf_d="#5c8479", fuzzy=0.22, fuzz="#d6e4e0", stem="#9fb8ae"),
}


def datura_palette(p):
    return {
        "L": hx(p["leaf"]), "l": hx(p["leaf_d"]), "T": hx(p["stem"]), "w": hx(p["fuzz"]),
        "F": hx(p["flower"]), "H": hx(p["rim"]), "f": hx(p["throat"]),
        "B": hx(p["bud"]), "b": hx(p["bud_d"]),
        "C": hx(p["cap"]), "c": hx(p["cap_d"]), "p": hx(p["spine"]),
        "D": hx(p["ripe"]), "d": hx(p["ripe_d"]), "K": hx(p["seed"]), "k": hx(p["seed_hi"]),
        "o": hx("#25401c"),
    }


def datura_skeleton(kind, s=1.0):
    """Forking stems. -> (stem polylines, leaves (x, y, 'L'|'R'), flower/fruit tips).

    'single' is a whole plant in one block, or the TOP block of a taller one: the trunk forks, each branch forks
    again, a small leaf sits at each fork, and a flower or capsule is on each tip. 'lower' is the block under it.
    s < 1 compresses the plant toward the bottom of the block (a plant shorter than 1 m)."""
    gy = lambda y: round(15 - (15 - y) * s)
    if kind == "lower":
        stems = [[(8, 15), (8, 0)], [(8, 12), (5, 9), (3, 6)], [(8, 8), (11, 5), (13, 3)], [(8, 5), (6, 3), (5, 1)], [(5, 9), (4, 11)]]
        leaves = [(5, 13, "L"), (9, 12, "R"), (1, 8, "L"), (6, 8, "R"), (11, 7, "R"), (9, 4, "L"), (13, 2, "R"), (3, 3, "L")]
        return stems, leaves, []
    stems = [
        [(8, 15), (8, gy(11))],
        [(8, gy(11)), (5, gy(8)), (2, gy(6))],
        [(5, gy(8)), (5, gy(4))],
        [(8, gy(11)), (11, gy(8)), (14, gy(6))],
        [(11, gy(8)), (11, gy(4))],
        [(8, gy(11)), (8, gy(3))],
    ]
    leaves = [(5, gy(13), "L"), (9, gy(13), "R"), (2, gy(10), "L"), (6, gy(10), "R"), (9, gy(10), "L"), (12, gy(10), "R"),
              (3, gy(7), "L"), (13, gy(7), "R")]
    tips = [(2, gy(6)), (5, gy(4)), (8, gy(3)), (11, gy(4)), (14, gy(6))]
    return stems, leaves, tips


def datura_stage(pid, stage, p, kind="single"):
    rng = random.Random(pid + ":" + kind)
    if stage == "seed":
        return parse(SEED)
    if stage == "seedling":
        return parse(SEEDLING)
    stems, leaves, tips = datura_skeleton(kind, p.get("s", 1.0))
    pix = {}
    for lx, ly, side in leaves:                         # leaves first so the branches show on top
        place(pix, LEAF_L if side == "L" else LEAF_R, lx, ly)
    if p.get("ragged"):
        for (x, y), ch in list(pix.items()):
            if any((x + dx, y + dy) not in pix for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) and rng.random() < 0.3:
                del pix[(x, y)]
    if p.get("fuzzy"):
        for (x, y), ch in list(pix.items()):
            if rng.random() < p["fuzzy"]:
                pix[(x, y)] = "w"
    for st in stems:                                    # the branches
        poly(pix, st, "T")
    cap = {"spiny": SPINY, "long": LONG, "smooth": SMOOTH, "warty": SPINY}[p["capstyle"]]
    remap = {"p": "c"} if p["capstyle"] == "warty" else None
    trump, up = (TRUMPET_SMALL, 1) if p["flowers"] == "small" else (TRUMPET_BIG, 3)
    if stage == "budding":
        for tx, ty in tips:
            place(pix, BUD, tx, ty - 1)
    elif stage == "flowering":
        for tx, ty in tips:
            place(pix, trump, tx - 1, ty - up)
    elif stage == "fruiting":
        w, h = (1, 1)
        for tx, ty in tips[::2]:                        # fruit does not set on every tip
            place(pix, cap, tx - w, ty - h, remap)
    elif stage == "ripe_capsule":
        for tx, ty in tips[::2]:
            place(pix, SPLIT_LONG if p["capstyle"] == "long" else SPLIT, tx - 1, ty - 1)
    if p.get("curve"):
        pix = {(x + round((15 - y) / 8), y): ch for (x, y), ch in pix.items()}
    return pix


# ------------------------------------------------------------------ Ipomoea tricolor (twining vine)
def ipomoea_stage(stage):
    import math
    leaf, leaf_d, stem = hx("#4f9a3c"), hx("#357a2c"), hx("#6aae48")
    pal = {"L": leaf, "l": leaf_d, "T": stem, "F": hx("#4a72e6"), "H": hx("#9bb8ff"), "f": hx("#2f4fb8"), "Y": hx("#f6e48a"),
           "B": hx("#a56ad8"), "b": hx("#7a45b0"), "P": hx("#8a8a4a"), "p": hx("#5e5e30"), "K": hx("#1c1a1a"), "k": hx("#4a4040")}
    if stage == "seed":
        return parse(SEED), pal
    if stage == "sprout":
        pix = parse(["................"] * 9 + [".....LL...LL....", "....LLLl.lLLL...", ".....lLLTLLl....", ".......T.T......", ".......TT.......", "......T.T.......", ".......T........"])
        return pix, pal
    vine_x = lambda y, which: (4, 11)[which] + round(1.4 * math.sin(y / 2 + (0.0, 2.0)[which]))
    pix = {}
    hearts = ((1, 1, 0), (10, 5, 1), (2, 9, 0), (9, 12, 1))     # leaf at (ox, oy) hangs off vine `which` on a side shoot
    heart = parse(["L.L", "LLL", ".l."])
    for ox, oy, _ in hearts:
        place(pix, heart, ox, oy)
    for y in range(SIZE):                                       # twining main stems
        for which in (0, 1):
            pix[(vine_x(y, which), y)] = "T"
    for ox, oy, which in hearts:                                # side branches carrying each leaf
        line(pix, vine_x(oy + 1, which), oy + 1, ox + 2, oy + 1, "T")
    for ox, oy in ((7, 3), (13, 9), (6, 14)):                   # small side shoots / tendrils
        line(pix, vine_x(oy, 0 if ox < 8 else 1), oy, ox, oy - 1, "T")
    if stage == "budding":
        for ox, oy in ((6, 2), (13, 7), (6, 10), (0, 13)):
            place(pix, parse(["B", "B", "b"]), ox, oy)
    elif stage == "flowering":
        big = parse(["HFH", ".Y.", ".f."])
        for ox, oy in ((1, 0), (9, 3), (1, 8), (10, 11), (6, 5), (12, 8)):
            place(pix, big, ox, oy)
    elif stage == "seed_pod":
        for ox, oy in ((6, 2), (12, 6), (6, 10), (1, 12)):
            place(pix, parse(["PP", "Pp"]), ox, oy)
    return pix, pal


# ------------------------------------------------------------------ Chara braunii (whorls of branchlets)
def chara_stage(stage):
    pal = {"G": hx("#7fd09a", 235), "g": hx("#4a9a6a", 235), "L": hx("#b4ecc4", 235),
           "M": hx("#5a4a38"), "m": hx("#3a2f24"), "S": hx("#241a14"), "O": hx("#e8863a")}
    pix = {}
    if stage == "spore":
        for x, y in ((3, 15), (6, 14), (7, 15), (10, 15), (12, 14), (9, 13)):
            pix[(x, y)] = "S"
        for x in range(SIZE):
            pix[(x, 15)] = pix.get((x, 15), "M" if x % 3 else "m")
        return pix, pal
    height, cys = {"sprout": (5, (11,)), "growing": (11, (12, 8, 4)), "fertile": (13, (13, 10, 7, 4))}[stage]
    for y in range(15, 15 - height, -1):
        pix[(8, y)] = "g" if y % 2 else "G"
    for cy in cys:                                   # a whorl: 6-10 branchlets (Wikipedia); drawn as a ring of short limbs
        for dx, dy in ((-4, -2), (-3, -3), (-3, 0), (-2, 2), (4, -2), (3, -3), (3, 0), (2, 2)):
            pts = line(pix, 8, cy, 8 + dx, cy + dy, "G")
            pix[pts[-1]] = "L"
    pix[(8, 15 - height)] = "L"
    pix[(7, 15 - height)] = "L"
    pix[(9, 15 - height)] = "L"
    if stage == "fertile":
        for cy in cys:
            pix[(7, cy + 1)] = "O"
            pix[(9, cy - 1)] = "O"
    return pix, pal


# ------------------------------------------------------------------ rosemary (woody stems, needle leaves)
ROSE_TOP = [[(4, 15), (2, 9), (1, 4)], [(8, 15), (8, 8), (8, 2)], [(12, 15), (14, 9), (15, 4)],
            [(4, 15), (6, 10), (5, 5)], [(12, 15), (10, 10), (11, 5)]]
ROSE_LOWER = [[(4, 0), (4, 15)], [(8, 0), (8, 15)], [(12, 0), (12, 15)], [(4, 8), (1, 5)], [(12, 8), (15, 5)], [(8, 6), (6, 3)]]
ROSE_YOUNG = [[(8, 15), (8, 9)], [(8, 15), (5, 11), (3, 8)], [(8, 15), (11, 11), (13, 8)]]


def rosemary_stage(stage, kind="single"):
    rng = random.Random("rosemary:" + stage + kind)
    pal = {"a": hx("#2f5a35"), "b": hx("#44743f"), "c": hx("#7fa57a"), "d": hx("#b8cdb2"), "W": hx("#7a6044"),
           "B": hx("#6f7fe0"), "H": hx("#a9b4ff"), "h": hx("#4a50b8"), "s": hx("#8a6a3a"), "S": hx("#b08a50")}
    pix = {}
    if stage == "seed":
        for x, y in ((5, 9), (6, 9), (9, 11), (10, 11), (7, 13), (8, 13), (4, 12), (11, 8)):
            pix[(x, y)] = "s"; pix[(x, y + 1)] = "S" if (x + y) % 2 else "s"
        return pix, pal
    if stage == "seedling":
        poly(pix, [(8, 15), (8, 11)], "b")
        for dx, dy in ((-1, 11), (1, 10), (-2, 13), (2, 12), (0, 9)):
            pix[(8 + dx, dy)] = "c"; pix[(8 + dx, dy + 1)] = "b"
        return pix, pal
    stems = ROSE_LOWER if kind == "lower" else ROSE_YOUNG if stage == "young" else ROSE_TOP
    paths = [poly({}, st, "W") for st in stems]
    for path in paths:                                    # needles along every stem
        for i, (x, y) in enumerate(path):
            if i < 2 and kind != "lower":
                continue
            for side in (-1, 1):
                if rng.random() < 0.85:
                    pix[(x + side, y)] = rng.choice("aabbc")
                if rng.random() < 0.45:
                    pix[(x + 2 * side, y - rng.choice((0, 1)))] = rng.choice("abcd")
            if rng.random() < 0.5:
                pix[(x, y - 1)] = rng.choice("abc")
    for path in paths:                                    # the woody stems on top, so the branching shows
        for x, y in path:
            pix[(x, y)] = "W"
    if stage == "flowering":                              # groups of 2-3 flowers down the stems (Wikipedia)
        for path in paths:
            for i, (x, y) in enumerate(path):
                if i > 3 and i % 4 == 2:
                    side = 1 if (i // 4) % 2 else -1
                    pix[(x + side, y)] = "B"; pix[(x + 2 * side, y)] = "H"
                    if rng.random() < 0.7:
                        pix[(x + side, y + 1)] = "h"
    return pix, pal


# ------------------------------------------------------------------ rice (tillers, arching blades, branched panicle)
RICE_BASES = [5, 8, 11]                           # three tillers; the lower block uses the same x positions so the stems join


def rice_stage(stage, kind="single"):
    """Oryza sativa after the reference plate: a few upright jointed tillers, each with long slender blades arching
    outward, fibrous roots, and a branched panicle whose branches droop under the grain when ripe."""
    rng = random.Random("rice:" + stage + kind)
    ripe = stage == "ripe"
    pal = {"L": hx("#6fae48"), "l": hx("#4a8a38"), "y": hx("#b5bd4e"), "Y": hx("#d8cf60"), "S": hx("#8fb05a"), "s": hx("#c8b05a"),
           "r": hx("#c9b79a"), "R": hx("#8a7a60"),
           "G": hx("#e8c04a"), "g": hx("#c99a30"), "H": hx("#f4dc8a"), "P": hx("#cfe4a0"), "p": hx("#9fc070"), "A": hx("#f4e060"),
           "K": hx("#8a5a38"), "k": hx("#5e3a22")}
    pix = {}
    if stage == "seed":                                    # husked grains: pointed tip, pale highlight, darker seam
        grain = parse([".k.", "GHG", "GGg", ".g."])
        for ox, oy in ((3, 8), (9, 7), (6, 11)):
            place(pix, grain, ox, oy)
        return pix, pal
    if stage == "seedling":
        for x in (5, 7, 8, 9, 11):                         # fibrous roots
            pix[(x, 15)] = "r"
        for x in (6, 10):
            pix[(x, 14)] = "R"
        poly(pix, [(8, 14), (8, 8)], "L")
        poly(pix, [(7, 14), (5, 10)], "l")
        poly(pix, [(9, 14), (11, 10)], "l")
        pix[(8, 7)] = "L"
        return pix, pal
    tips = {5: (3, 6), 8: (8, 2), 11: (13, 5)}
    if stage == "tillering":
        tips = {5: (4, 9), 8: (8, 7), 11: (12, 9)}
    leaf, stem = ("y" if ripe else "L"), ("s" if ripe else "S")
    paths = {}
    for xb in RICE_BASES:
        tx, ty = tips[xb] if kind == "single" else (xb, 0)
        paths[xb] = poly(pix, [(xb, 15), (tx, ty)], stem)
    for xb, pts in paths.items():                          # one or two long slender blades from the nodes, arching outward
        side = -1 if xb < 8 else 1 if xb > 8 else 0
        for k, frac in enumerate((0.35, 0.65)):
            nx, ny = pts[min(len(pts) - 1, int(len(pts) * frac))]
            sd = side or (-1 if k == 0 else 1)
            if k == 1 and side:
                sd = -side
            blade = [(nx, ny), (nx + sd * 2, ny - 2), (nx + sd * 4, ny - 2), (nx + sd * 5, ny)]
            poly(pix, blade, leaf)
            pix[blade[-1]] = "l"
    if kind == "single" and stage in ("flowering", "ripe"):
        # panicle: a branched inflorescence from the last internode of the main tiller
        axis = poly({}, [(8, 6), (8, 3), (10, 1), (12, 2), (13, 4)] if ripe else [(8, 6), (8, 3), (8, 0)], "s")
        for x, y in axis:
            pix[(x, y)] = "s"
        for i, (x, y) in enumerate(axis[2:], 2):
            side = 1 if i % 2 else -1
            bx, by = x + side, y + (1 if ripe else 0)
            pix[(bx, by)] = "s"
            if ripe:
                pix[(bx + side, by + 1)] = "G"; pix[(bx + side, by + 2)] = "g"      # grain hangs from each branch tip
                pix[(bx, by + 1)] = "H"
            else:
                pix[(bx + side, by)] = "P"; pix[(bx, by - 1)] = "p"                 # spikelets
                if i % 2:
                    pix[(bx + 2 * side, by - 1)] = "A"                              # yellow anthers
    if kind == "single" and stage in ("tillering", "flowering", "ripe"):
        for x in (4, 6, 8, 10, 12):                         # roots at the foot of the clump
            if (x, 15) not in pix:
                pix[(x, 15)] = "r"
    return pix, pal


# ------------------------------------------------------------------ grasses, drawn from pipeline data
# Parameters come from a species' own data (appearance / architecture / measurements / description): colours, plume type,
# how arching and how clumped it is, and its height. Words are matched in the quoted source text; anything the text does
# not say falls back to a plain default listed here, never to another species' look.
PLUME_COLORS = [("silver", "#d6dccf"), ("white", "#f0ede2"), ("cream", "#ece3c0"), ("pink", "#d58fa6"), ("purple-brown", "#7a5a5a"),
                ("purplish", "#8a5a9a"), ("purple", "#8a5a9a"), ("violet", "#8a5a9a"), ("golden", "#d9b04a"), ("gold", "#d9b04a"),
                ("yellow", "#d8c85a"), ("straw", "#d8c27a"), ("tan", "#c8a86a"), ("tawny", "#c49a5a"), ("bronze", "#a8743a"),
                ("brown", "#8a6a3a"), ("reddish", "#a8503a"), ("red", "#b04a3a"), ("green", "#9ab45a"), ("bluish", "#7a8fb5")]
LEAF_COLORS = [("glaucous", ("#86b0a8", "#5f8f8a", "#47706e")), ("blue", ("#86b0a8", "#5f8f8a", "#47706e")),
               ("gray-green", ("#a3b894", "#7a9a78", "#5a7a5a")), ("grey-green", ("#a3b894", "#7a9a78", "#5a7a5a")),
               ("yellow-green", ("#b8cc5a", "#96b040", "#6e8a30")), ("light green", ("#a8d070", "#82b050", "#5a8a38")),
               ("bright green", ("#8ccc58", "#62ac3c", "#418028")), ("dark green", ("#58a040", "#3f7e30", "#2c5a24")),
               ("green", ("#7cc050", "#58a038", "#3c7a28"))]
INFLO_WORDS = [("bottlebrush", ["bottlebrush", "bottle-brush", "bristle", "foxtail"]),
               ("fingers", ["turkey", "three-branched", "three branches", "digitate", "finger"]),
               ("droop", ["dangling", "pendulous", "drooping spikelet", "nodding", "sea oats", "flat spikelet", "oat-like"]),
               ("plume", ["plume", "plumose", "feathery", "silky", "fluffy"]),
               ("spike", ["spike", "raceme"]),
               ("panicle", ["panicle"])]


def _text_of(d, parts=None):
    out = []
    for key in ("appearance", "architecture"):
        for it in d.get(key, []):
            if parts is None or it.get("part") in parts or key == "architecture":
                out.append(f"{it.get('part', '')} {it.get('attribute', it.get('aspect', ''))} {it.get('value', '')} {it.get('quote', '')}")
    return " ".join(out).lower()


def _has(text, word):
    import re
    return re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text) is not None


def photo_colors(pid):
    """Typical leaf greens and flower-head colour from the species' reference photos.

    Leaf tones: green pixels of leaf/habit photos (light, mid, dark). Head colour: the median of clearly coloured
    (saturated), non-green, non-sky pixels of flower/fruit photos; pale heads (silver, white) come from the text instead,
    since a photo's grey background cannot be told from a silver plume. The result is cached in the photo manifest
    (`sampled_colors`), which is tracked in git, so a fresh clone draws the same sprites without the images."""
    import colorsys
    import json as _json
    man = ROOT / "data" / "photos" / pid / "manifest.json"
    if not man.exists():
        return {}
    m = _json.loads(man.read_text())
    if "sampled_colors" in m:
        sc = m["sampled_colors"]
        return {"leaf": tuple(sc["leaf"]) if sc.get("leaf") else None, "plume": sc.get("plume")}
    photos = m["photos"]
    out = {}

    def pixels(roles):
        px = []
        for ph in photos:
            f = ROOT / ph["file"]
            if ph["role"] in roles and f.exists():
                try:
                    im = Image.open(f).convert("RGB")
                    im.thumbnail((64, 64))
                    px += [colorsys.rgb_to_hsv(*(c / 255 for c in rgb)) for rgb in im.getdata()]
                except Exception:
                    pass
        return px

    g = sorted(v for h, s_, v in pixels(("leaf", "habit")) if 0.15 < h < 0.47 and s_ > 0.25 and 0.2 < v < 0.95)
    if len(g) > 60:
        def hexof(v):
            r, gg, b = colorsys.hsv_to_rgb(0.26, 0.62, v)
            return "#%02x%02x%02x" % (round(r * 255), round(gg * 255), round(b * 255))
        out["leaf"] = (hexof(max(0.68, min(0.95, g[int(len(g) * .8)]))), hexof(max(0.52, g[len(g) // 2])), hexof(max(0.36, g[int(len(g) * .2)])))
    head = [(h, s_, v) for h, s_, v in pixels(("flower", "fruit"))
            if s_ > 0.28 and v > 0.4 and not (0.15 < h < 0.47) and not (0.5 < h < 0.72)]
    if len(head) > 40:
        hs = sorted(head, key=lambda x: x[2])
        h, s_, v = hs[len(hs) // 2]
        r, gg, b = colorsys.hsv_to_rgb(h, s_, v)
        out["plume"] = "#%02x%02x%02x" % (round(r * 255), round(gg * 255), round(b * 255))
    if pixels(("leaf", "habit", "flower", "fruit")):
        m["sampled_colors"] = {"leaf": list(out["leaf"]) if out.get("leaf") else None, "plume": out.get("plume")}
        man.write_text(_json.dumps(m, indent=2, ensure_ascii=False))
    return out


def grass_params(d):
    """Sprite parameters for one grass from its data. 'basis' records what each choice was read from."""
    pid = d["id"]
    allt = (_text_of(d) + " " + (d.get("description") or "").lower())
    leaf_t = _text_of(d, ("leaf",)) or allt
    infl_t = _text_of(d, ("inflorescence", "flower", "fruit", "seed")) or allt
    ph = photo_colors(pid)
    basis = {}
    leaf = next((c for w, c in LEAF_COLORS if _has(leaf_t, w)), None)
    basis["leaf"] = "text" if leaf else ("photos" if ph.get("leaf") else "default")
    leaf = leaf or ph.get("leaf") or LEAF_COLORS[-1][1]
    plume = next((c for w, c in PLUME_COLORS if _has(infl_t, w)), None)
    basis["plume"] = "text" if plume else ("photos" if ph.get("plume") else "default")
    plume = plume or ph.get("plume") or "#d8c27a"
    inflo = next((k for k, ws in INFLO_WORDS if any(_has(infl_t, w) for w in ws)), None)
    basis["inflorescence"] = "text" if inflo else "default"
    inflo = inflo or "panicle"
    arch = 0.85 if any(_has(allt, w) for w in ("arching", "fountain", "cascading", "recurved", "weeping", "drooping")) else \
           0.2 if any(_has(allt, w) for w in ("upright", "erect", "stiff")) else 0.5
    basis["arch"] = "text" if arch != 0.5 else "default"
    cane = any(_has(allt, w) for w in ("cane", "reed", "bamboo", "hollow", "jointed"))
    height = None
    try:
        import importlib.util
        sp = importlib.util.spec_from_file_location("sample_sizes", ROOT / "tools" / "sample_sizes.py")
        ss = importlib.util.module_from_spec(sp); sp.loader.exec_module(ss)
        cfg, per = ss.load_cfg()
        hs = d["size"].get("height_sources") or ([dict(d["size"]["height_cm"])] if d["size"]["source"] != "pending" else [])
        if hs:
            lo, hi, _ = ss.typical_range(hs, cfg["range_mode"])
            height = (lo + hi) / 2
            basis["height"] = "sourced size range"
    except Exception:
        pass
    if height is None:
        height, basis["height"] = 120.0, "default 1.2 m (no size data)"
    return {"leaf": leaf, "plume": plume, "inflo": inflo, "arch": arch, "cane": cane, "height_cm": height, "basis": basis}


def _shade(hexcol, f):
    c = hexcol.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v * f))) for v in (r, g, b))


def grass_palette(P, ripe=False):
    pl = _shade(P["plume"], 0.8) if ripe else P["plume"]
    return {"L": hx(P["leaf"][1]), "l": hx(P["leaf"][2]), "m": hx(P["leaf"][0]), "S": hx(_shade(P["leaf"][0], 1.05)),
            "N": hx(_shade(P["leaf"][2], 0.8)),
            "P": hx(pl), "p": hx(_shade(pl, 1.15)), "q": hx(_shade(pl, 0.7)), "G": hx("#e0bf55"), "g": hx("#b08e32"),
            "r": hx("#c9b79a"), "R": hx("#8a7a60"), "k": hx(_shade(P["leaf"][0], 0.95))}



# ================================================================== 32x32 grasses (finer detail)
# Same data-driven parameters as the 16x16 look, drawn on a 32x32 canvas: more blades with a lighter midrib, smoother
# arches, and larger heads with real structure (feather barbs, bristles, a three-branched turkey foot, dangling spikelets).
G = 32
GRAIN32 = [
    "...k..", "..kGk.", ".kGpGg", ".GpGGg", ".GGGGg", ".GGGgg", "..GGg.", "..ggg.", "...g..",
]


def g_blade(pix, bx, by, sd, rise, out, droop, main, tip="l"):
    """A broad grass blade: a smooth arch, two pixels wide near the base, with a lighter midrib."""
    pts = [(bx, by), (bx + sd * round(out * .22), by - round(rise * .45)), (bx + sd * round(out * .55), by - round(rise * .85)),
           (bx + sd * round(out * .88), by - rise + round(droop * .35)), (bx + sd * out, by - rise + droop)]
    path = poly(pix, pts, main)
    for x, y in path[: max(2, int(len(path) * .42))]:
        pix[(x + 1, y)] = main
    for i, (x, y) in enumerate(path):
        if i % 4 == 1 and i < len(path) * .75:
            pix[(x, y)] = "m"
    for x, y in path[-3:]:
        pix[(x, y)] = tip


def g_head(pix, kind, tx, ty, ripe, rng, lean=0):
    """One flower/seed head with its base at (tx, ty), growing up ~15 px; the top leans `lean` px."""
    def at(i, n=15):                                       # horizontal shift of row i (0 = top) from the lean
        return round(lean * (n - i) / n)
    if kind == "plume":                                    # feathery plume: barbs fan from a central axis
        hw = [0, 1, 2, 3, 4, 4, 5, 5, 5, 5, 4, 4, 3, 3, 2, 1]
        for i, w in enumerate(hw):
            y, cx = ty - 15 + i, tx + at(i)
            pix[(cx, y)] = "k"
            for dx in range(1, w + 1):
                if dx == w and rng.random() < .5:
                    continue                               # ragged edge
                c = "p" if (dx + i) % 3 == 0 else ("P" if (dx + i) % 3 == 1 else "q")
                pix[(cx - dx, y)] = c
                pix[(cx + dx, y + (1 if dx > 3 and i < 14 else 0))] = "P" if (dx + i) % 2 else "p"
        for i in range(3):
            pix[(tx, ty + 1 + i)] = "k"
    elif kind == "bottlebrush":                            # dense cylinder with bristles, arching at the tip
        for i in range(14):
            y, cx = ty - i, tx + round(lean * i / 14) + (1 if i > 10 else 0) + (1 if i > 12 else 0)
            pix[(cx, y)] = "P"; pix[(cx + 1, y)] = "q"
            ln = 3 if i % 2 == 0 else 2
            for d in range(1, ln + 1):
                pix[(cx - d, y - d // 2)] = "p"
                pix[(cx + 1 + d, y - d // 2)] = "p" if d < ln else "P"
        for i in range(3):
            pix[(tx, ty + 1 + i)] = "k"
    elif kind == "fingers":                                # three-branched "turkey foot": stout branches with spikelet pairs
        for i in range(4):
            pix[(tx, ty + i)] = "k"
        pix[(tx, ty - 1)] = "P"
        for dx, dy in ((-7, -12), (0, -15), (7, -12)):
            pts = poly({}, [(tx, ty - 1), (tx + dx // 2, ty + dy // 2 - 1), (tx + dx, ty + dy)], "P")
            for k, (x, y) in enumerate(pts):
                pix[(x, y)] = "P"; pix[(x + 1, y)] = "q"
                if k % 3 == 2:
                    pix[(x - 1, y)] = "p"; pix[(x + 2, y)] = "p"
            pix[(tx + dx, ty + dy - 1)] = "p"; pix[(tx + dx + 1, ty + dy - 1)] = "P"
    elif kind == "droop":                                  # arching axis; flat spikelets dangle like little fish
        pts = poly({}, [(tx, ty), (tx, ty - 6), (tx + 2, ty - 11), (tx + 8, ty - 12)], "k")
        fish = ["Pp.", "PPp", ".qP", "..q"]
        for k, (x, y) in enumerate(pts[6:], 6):
            if k % 3 == 0:
                for r, row in enumerate(fish):
                    for c, ch in enumerate(row):
                        if ch != ".":
                            pix[(x + c, y + 1 + r)] = ch
    elif kind == "spike":                                  # dense narrow spike with bristles
        for i in range(15):
            y, cx = ty - i, tx + round(lean * i / 14)
            pix[(cx, y)] = "P"; pix[(cx + 1, y)] = "q"
            if i % 2:
                pix[(cx - 1, y)] = "p"; pix[(cx + 2, y)] = "p"
    else:                                                  # open airy panicle: tiers of fine branchlets ending in seeds
        for i in range(15):
            pix[(tx + round(lean * i / 14), ty - i)] = "k"
        for i, ln in ((3, 4), (6, 5), (9, 5), (12, 4)):
            cx = tx + round(lean * i / 14)
            for sd in (-1, 1):
                pts = poly({}, [(cx, ty - i), (cx + sd * ln // 2, ty - i - ln // 2), (cx + sd * ln, ty - i - ln)], "P")
                for x, y in pts:
                    pix[(x, y)] = "P"
                pix[(cx + sd * (ln + 1), ty - i - ln - 1)] = "p"; pix[(cx + sd * ln, ty - i - ln - 1)] = "p"
    if ripe:                                               # seeds ripening: golden grains over the head
        for dx, dy in ((-2, -3), (2, -6), (-1, -9), (1, -12), (-3, -8), (3, -10)):
            if (tx + dx, ty + dy) in pix:
                pix[(tx + dx, ty + dy)] = "G"
                pix[(tx + dx, ty + dy + 1)] = "g"


def g_cane(pid, stage, P, kind):
    """Cane-like grasses: a thick jointed culm with long swordlike leaves alternating up it and a plume at the top."""
    rng = random.Random(f"cane32:{pid}:{stage}:{kind}")
    ripe = stage == "fruiting"
    pal = grass_palette(P, ripe)
    pix = {}
    flowering = stage in ("flowering", "fruiting")
    top = 0 if kind == "lower" else 2 + (17 if flowering and kind == "single" else 0)
    x0 = 14
    culm = []
    for y in range(G - 1, top - 1, -1):                    # four pixels wide: light, mid, mid, shadow
        x = x0 + (2 * (G - 1 - y)) // (G - 1) * (kind != "lower")
        culm.append((x, y))
        pix[(x, y)] = "S"; pix[(x + 1, y)] = "L"; pix[(x + 2, y)] = "L"; pix[(x + 3, y)] = "k"
    node_ys = [y for i, (x, y) in enumerate(culm) if i % 8 == 7]
    for x, y in culm:
        if y in node_ys or y + 1 in node_ys:
            for dx in range(4):
                pix[(x + dx, y)] = "N"
    for k, ny in enumerate(node_ys):                       # leaves alternate sides, arching out and drooping
        nx = x0 + (2 * (G - 1 - ny)) // (G - 1) * (kind != "lower")
        sd = -1 if k % 2 == 0 else 1
        bx = nx if sd < 0 else nx + 3
        g_blade(pix, bx, ny - 1, sd, 7 + (k % 2) * 2, 12 if k % 2 == 0 else 10, round(P["arch"] * 9) + 2, "L" if k % 2 == 0 else "m")
        for dy in (0, 1):                                  # leaf sheath wrapping the node
            pix[(bx - sd, ny - dy)] = "N"
    if kind == "single" and stage == "budding":
        x, y = culm[-1]
        for i in range(7):
            pix[(x + 1, y - i)] = "m" if i < 2 else "L"; pix[(x + 2, y - i)] = "S"
    if kind == "single" and flowering:
        x, y = culm[-1]
        g_head(pix, P["inflo"], x + 1, y, ripe, rng, lean=2)
    if kind == "single":
        for x in range(8, 24, 2):
            if (x, G - 1) not in pix:
                pix[(x, G - 1)] = "r"
    return pix, pal


def grass32_stage(pid, stage, P, kind="single"):
    rng = random.Random(f"grass32:{pid}:{stage}:{kind}")
    ripe = stage == "fruiting"
    pal = grass_palette(P, ripe)
    pix = {}
    if stage == "seed":                                    # three plump grains
        for ox, oy in ((5, 14), (18, 12), (11, 21)):
            place(pix, parse(GRAIN32), ox, oy)
        return pix, pal
    if stage == "seedling":
        for x in range(9, 24, 2):
            pix[(x, G - 1)] = "r"
            if x % 4 == 1:
                pix[(x, G - 2)] = "R"
        for sd, rise, out in ((-1, 9, 5), (1, 11, 6), (-1, 13, 2), (1, 7, 9), (0, 15, 0)):
            g_blade(pix, 16 + (0 if sd == 0 else sd), G - 3, sd or 1, rise, out, 3, "L" if rise % 2 else "m")
        return pix, pal
    if P["cane"] and P["height_cm"] > 100:
        return g_cane(pid, stage, P, kind)
    cm, arch = P["height_cm"], P["arch"]
    tall = cm > 100
    whole = kind == "single" and not tall
    plant_px = G if tall else max(14, round(G * cm / 100))
    flowering = stage in ("flowering", "fruiting")
    head_h = 16 if flowering and kind == "single" else 0
    cx_list = [12, 16, 20]
    culms = []
    for i, cx in enumerate(cx_list):
        if kind == "lower":
            culms.append((cx, cx, 0))
        else:
            top_y = (G - plant_px) if whole else 2
            lean = round((cx - 16) * arch * 1.6)
            culms.append((cx, max(2, min(29, cx + lean)), top_y + 2 + (i % 2) * 2 + head_h))
    droop = round(arch * 9)
    if kind == "single" and whole:                         # a short plant: a basal fan of broad arching blades
        leaf_h = max(8, round(plant_px * (0.5 + 0.2 * (1 - arch))))
        for j in range(16):
            sd = -1 if j < 8 else 1
            k = j % 8 + 1
            out = min(14, round(3 + k * (1.1 + 2.4 * arch)))
            g_blade(pix, 16 + sd * (k // 3), G - 1, sd, max(6, round(leaf_h - (k - 1) * 1.5)), out, droop, "L" if k % 2 else "m")
    elif kind == "single":                                 # top block of a tall plant: leaf blades arch off the culms
        for i, (cx, tx, ty) in enumerate(culms):
            sd = -1 if i == 0 else 1 if i == 2 else (1 if rng.random() < .5 else -1)
            g_blade(pix, cx, 26, sd, 9, 6 + round(7 * arch), droop, "L")
            g_blade(pix, cx, 17, -sd, 7, 5 + round(6 * arch), max(2, droop - 2), "m")
    else:                                                  # lower block: long blades arch out from the culms
        for i, (cx, tx, ty) in enumerate(culms):
            sd = -1 if i == 0 else 1 if i == 2 else (1 if i % 2 else -1)
            g_blade(pix, cx, 27, sd, 11, 6 + round(8 * arch), droop, "L")
            g_blade(pix, cx, 15, -sd, 9, 6 + round(6 * arch), droop, "m")
            g_blade(pix, cx, 5, sd, 7, 5 + round(5 * arch), max(2, droop - 2), "L")
    for cx, tx, ty in culms:                               # culms drawn over the blades
        path = poly(pix, [(cx, G - 1), ((cx + tx) // 2, (G - 1 + ty) // 2), (tx, ty)], "S")
        for x, y in path:
            pix[(x + 1, y)] = "k"
    if kind == "single" and stage == "budding":
        for cx, tx, ty in culms:
            for i in range(7):
                pix[(tx, ty - i)] = "m" if i < 2 else "L"; pix[(tx + 1, ty - i)] = "S"
    if kind == "single" and flowering:
        # shape-distinct heads (turkey foot, dangling spikelets) read best singly; the others sit on the outer culms
        chosen = [culms[1]] if P["inflo"] in ("fingers", "droop") else [culms[0], culms[2]]
        for cx, tx, ty in chosen:
            g_head(pix, P["inflo"], tx, ty, ripe, rng, lean=round((tx - 16) * 0.35))
    if kind == "single":
        for x in range(8, 24, 2):
            if (x, G - 1) not in pix:
                pix[(x, G - 1)] = "r"
    return pix, pal


HEAD_H = {"plume": 7, "bottlebrush": 6, "fingers": 5, "droop": 5, "spike": 6, "panicle": 6}
# Head silhouettes, drawn base-down (last row sits on the stem). P = main colour, p = light, q = shadow, k = stalk.
PLUME_T = ["..p..", ".pPp.", "pPpPq", "PpPqP", ".PqPq", "..Pq.", "..k.."]
BRUSH_T = [".Pq.", "pPqp", ".Pq.", "pPqp", ".Pq.", ".kk."]


def grass_head(pix, kind, tx, ty, ripe, rng, lean=0):
    """One flower/seed head whose base is at (tx, ty), growing upward; the top leans `lean` pixels (the head bends)."""
    def put(rows, ox, oy, bend=lean):
        for r, row in enumerate(rows):
            shift = round(bend * (len(rows) - 1 - r) / max(1, len(rows) - 1))
            for c, ch in enumerate(row):
                if ch != ".":
                    pix[(ox + c + shift, oy + r)] = ch
    if kind == "plume":                                   # feathery tapered plume, widest in the middle
        put(PLUME_T, tx - 2, ty - 6)
    elif kind == "bottlebrush":                           # dense cylinder with bristles, arching at the tip
        put(BRUSH_T, tx - 1, ty - 5, bend=lean + 1)
    elif kind == "fingers":                               # three-branched "turkey foot", stout branches with darker tips
        pix[(tx, ty)] = "k"; pix[(tx, ty - 1)] = "P"
        for dx, dy in ((-2, -4), (0, -4), (2, -4)):
            for t in range(1, 4):
                x, y = tx + dx * t // 3, ty - 1 + (dy + 1) * t // 3
                pix[(x, y)] = "P"; pix[(x + (1 if dx >= 0 else -1) if dx else x + 1, y)] = "q" if t > 1 else "P"
            pix[(tx + dx, ty + dy)] = "p"
    elif kind == "droop":                                 # arching axis; flat spikelets dangle like little fish
        pts = poly({}, [(tx, ty), (tx, ty - 2), (tx + 1, ty - 4), (tx + 3, ty - 4)], "k")
        for x, y in pts:
            pix[(x, y)] = "k"
        for x, y in pts[2:]:
            pix[(x, y + 1)] = "P"; pix[(x + 1, y + 1)] = "p"; pix[(x, y + 2)] = "q"; pix[(x + 1, y + 2)] = "P"
    elif kind == "spike":
        for i in range(6):
            cx = tx + round(lean * i / 5)
            pix[(cx, ty - i)] = "P"
            if i % 2:
                pix[(cx - 1, ty - i)] = "p"; pix[(cx + 1, ty - i)] = "q"
    else:                                                 # open panicle: thin axis, branchlets that fan out and end in seeds
        for i in range(6):
            cx = tx + round(lean * i / 5)
            pix[(cx, ty - i)] = "k"
        for i, w in ((1, 1), (3, 2), (5, 1)):
            cx = tx + round(lean * i / 5)
            for d in range(1, w + 1):
                pix[(cx - d, ty - i - d // 2)] = "P"; pix[(cx + d, ty - i - d // 2)] = "P"
            pix[(cx - w - 1, ty - i - 1)] = "p"; pix[(cx + w + 1, ty - i - 1)] = "p"
    if ripe:                                              # seeds ripening: golden grains on the head
        for dx, dy in ((-1, -2), (1, -3), (0, -5), (-1, -4)):
            if (tx + dx, ty + dy) in pix:
                pix[(tx + dx, ty + dy)] = "G"


def cane_stage(pid, stage, P, kind):
    """Cane-like grasses (reeds, giant reed): a thick jointed culm with swordlike leaves alternating up it."""
    rng = random.Random(f"cane:{pid}:{stage}:{kind}")
    ripe = stage == "fruiting"
    pal = grass_palette(P, ripe)
    pix = {}
    flowering = stage in ("flowering", "fruiting")
    head_h = HEAD_H[P["inflo"]] if flowering and kind == "single" else 0
    top = 0 if kind == "lower" else 1 + head_h
    lean = 0 if kind == "lower" else 1
    x0 = 7
    culm = []
    for y in range(15, top - 1, -1):                       # two pixels wide
        x = x0 + (lean * (15 - y)) // 15
        culm.append((x, y))
        pix[(x, y)] = "S"; pix[(x + 1, y)] = "L"
    for i, (x, y) in enumerate(culm):                      # nodes: darker joint band every four rows
        if i % 4 == 3:
            pix[(x, y)] = "N"; pix[(x + 1, y)] = "N"
    node_ys = [y for i, (x, y) in enumerate(culm) if i % 4 == 3]
    for k, ny in enumerate(node_ys):                       # leaves alternate sides, arching out and drooping
        nx = x0 + (lean * (15 - ny)) // 15
        sd = -1 if k % 2 == 0 else 1
        bx = nx if sd < 0 else nx + 1
        reach = 6 if k % 2 == 0 else 5
        pts = [(bx, ny), (bx + sd * 2, ny - 2), (bx + sd * (reach - 1), ny - 2), (bx + sd * reach, ny + round(P["arch"] * 3) + 1)]
        poly(pix, pts, "m" if k % 2 else "L")
        pix[pts[-1]] = "l"
        pix[(bx + sd, ny)] = "N"                           # leaf sheath wrapping the node
    if kind == "single" and stage == "budding":
        x, y = culm[-1]
        pix[(x, y)] = "m"; pix[(x, y - 1)] = "L"; pix[(x, y - 2)] = "L"
    if kind == "single" and flowering:
        x, y = culm[-1]
        grass_head(pix, P["inflo"], x, y, ripe, rng, lean=1)
    if kind == "single":
        for x in (5, 7, 9, 11):
            if (x, 15) not in pix:
                pix[(x, 15)] = "r"
    return pix, pal


def grass_stage(pid, stage, P, kind="single"):
    rng = random.Random(f"grass:{pid}:{stage}:{kind}")
    ripe = stage == "fruiting"
    pal = grass_palette(P, ripe)
    pix = {}
    if stage == "seed":                                    # grains (caryopses): pointed tip, pale highlight
        grain = parse([".k.", "GPG", "GGg", ".g."])
        for ox, oy in ((3, 8), (9, 7), (6, 11)):
            place(pix, grain, ox, oy)
        return pix, pal
    if stage == "seedling":
        for x in (5, 7, 8, 9, 11):
            pix[(x, 15)] = "r"
        poly(pix, [(8, 14), (8, 8)], "L"); poly(pix, [(7, 14), (5, 10)], "l"); poly(pix, [(9, 14), (11, 10)], "l"); poly(pix, [(8, 14), (6, 12)], "m")
        return pix, pal
    if P["cane"] and P["height_cm"] > 100:
        return cane_stage(pid, stage, P, kind)
    cm, arch = P["height_cm"], P["arch"]
    tall = cm > 100
    whole = kind == "single" and not tall
    plant_px = 16 if tall else max(7, round(16 * cm / 100))             # how many rows the whole plant fills (short plants only)
    flowering = stage in ("flowering", "fruiting")
    head_h = HEAD_H[P["inflo"]] if flowering and kind == "single" else 0
    cbases = [6, 8, 10]
    culms = []
    for i, cx in enumerate(cbases):
        if kind == "lower":
            culms.append((cx, cx, 0))
        else:
            top_y = (16 - plant_px) if whole else 1
            lean = round((cx - 8) * arch * 1.2)
            culms.append((cx, max(1, min(14, cx + lean)), top_y + 1 + (i % 2) + head_h))
    # --- leaf blades
    def blade(bx, by, sd, rise, out, droop, main, tip="l"):
        pts = [(bx, by), (bx + sd * round(out * 0.35), by - round(rise * 0.55)), (bx + sd * round(out * 0.8), by - rise), (bx + sd * out, by - rise + droop)]
        poly(pix, pts, main); pix[pts[-1]] = tip
    droop = round(arch * 3.5)
    if whole or kind == "lower" and False:
        pass
    if kind == "single" and whole:                         # a short plant: a basal fan of blades fills the block
        leaf_h = max(4, round(plant_px * (0.5 + 0.2 * (1 - arch))))
        for j in range(8):
            sd = -1 if j < 4 else 1
            k = j % 4 + 1
            out = min(7, round(1.5 + k * (0.6 + 1.4 * arch)))
            blade(8 + sd * (k // 2), 15, sd, max(3, leaf_h - (k - 1)), out, droop, "L" if k % 2 else "m")
    elif kind == "single":                                 # top block of a tall plant: leaf blades arch off the culms
        for i, (cx, tx, ty) in enumerate(culms):
            sd = -1 if i == 0 else 1 if i == 2 else (1 if rng.random() < .5 else -1)
            blade(cx, 12, sd, 4, 3 + round(3 * arch), droop, "L")
            blade(cx, 8, -sd, 3, 2 + round(3 * arch), max(1, droop - 1), "m")
    else:                                                  # lower block: blades arch out from the culms at the sides
        for i, (cx, tx, ty) in enumerate(culms):
            sd = -1 if i == 0 else 1 if i == 2 else (1 if i % 2 else -1)
            blade(cx, 13, sd, 5, 3 + round(4 * arch), droop, "L")
            blade(cx, 7, -sd, 4, 3 + round(3 * arch), droop, "m")
    # --- culms (flowering stems) on top of the blades, with nodes on cane-like grasses
    for cx, tx, ty in culms:
        path = poly(pix, [(cx, 15), ((cx + tx) // 2, (15 + ty) // 2), (tx, ty)], "S")
        if P["cane"]:
            for k in range(3, len(path) - 1, 4):
                pix[path[k]] = "N"
    if kind == "single" and stage == "budding":
        for cx, tx, ty in culms:
            pix[(tx, ty)] = "m"; pix[(tx, ty - 1)] = "L"; pix[(tx, ty - 2)] = "L"
    if kind == "single" and flowering:
        # heads this shape-distinct (turkey foot, dangling spikelets) read best singly; the others cluster on the outer culms
        chosen = [culms[1]] if P["inflo"] in ("fingers", "droop") else [culms[0], culms[2]]
        for cx, tx, ty in chosen:
            grass_head(pix, P["inflo"], tx, ty, ripe, rng, lean=round((tx - 8) * 0.4))
    if kind == "single":
        for x in (5, 7, 9, 11):
            if (x, 15) not in pix:
                pix[(x, 15)] = "r"
    return pix, pal


# ------------------------------------------------------------------ twig foliage tiles (peach, eucalyptus)
TWIGS = [
    [(0, 15), (4, 11), (8, 8), (12, 4), (15, 1)],
    [(4, 11), (2, 7), (1, 3)],
    [(8, 8), (9, 12), (11, 15)],
    [(12, 4), (9, 2), (8, 0)],
]


def twig_paths():
    return [poly({}, t, "W") for t in TWIGS]


def tile_nodes(path, step=3, start=2):
    return [(i, path[i]) for i in range(start, len(path) - 1, step)]


def foliage_tile(tree, stage):
    """A 16x16 leaf-block texture that is a branching twig with leaves hanging off it, so branches show through."""
    rng = random.Random(f"{tree}:{stage}")
    if tree == "peach":
        pal = {"W": hx("#9a4638"), "w": hx("#6e2f25"), "L": hx("#5b9a3c"), "l": hx("#3d7029"), "m": hx("#6aae48"),
               "P": hx("#f7a8c4"), "Q": hx("#e4709d"), "R": hx("#ffd6e4"), "C": hx("#c94f7c"), "B": hx("#d9728f"), "b": hx("#a04860"),
               "g": hx("#a4c25a"), "G": hx("#86a844"), "u": hx("#c9d567"), "U": hx("#e8a05a"), "O": hx("#f2a63f"), "E": hx("#e4573d"), "H": hx("#ffd27a")}
    elif tree == "olive":
        pal = {"W": hx("#8a7a68"), "w": hx("#5e5040"), "L": hx("#7f9a7a"), "l": hx("#5f7a5f"), "m": hx("#c8d4c4"),
               "F": hx("#f4f0dc"), "f": hx("#ffffff"), "y": hx("#e6dfae"),
               "g": hx("#8fb04a"), "G": hx("#6e9038"), "u": hx("#c5c85a"), "B": hx("#3a2040"), "b": hx("#6a4a78"), "R": hx("#8a4a4a")}
    else:
        young = stage == "young_tree"
        pal = {"W": hx("#c89060"), "w": hx("#8a6a4a"),
               "L": hx("#82c09a" if young else "#4f8a6a"), "l": hx("#5f9a7a" if young else "#356a50"), "m": hx("#6fae8a" if young else "#3f7658"),
               "F": hx("#f6f0c8"), "f": hx("#fffbe6"), "y": hx("#f3e49a"), "K": hx("#7a5a3a"), "k": hx("#5e4527")}
    pix = {}
    paths = twig_paths()
    leafless = tree == "peach" and stage in ("budding", "blossom")
    for pi, path in enumerate(paths):
        for ni, (i, (x, y)) in enumerate(tile_nodes(path)):
            nx, ny = normals(path, i)
            sides = (1, -1) if tree in ("euc", "olive") else ((1, -1)[ni % 2],)   # eucalyptus/olive: pairs; peach: alternate
            for sd in sides:
                lx, ly = round(x + sd * nx * 2.2), round(y + sd * ny * 2.2)
                if leafless and rng.random() < 0.75:
                    continue
                if tree == "olive":
                    blob(pix, lx, ly, 2, 0, "L" if rng.random() < 0.65 else "m", "l")     # narrow oblong leaf, whitish underside shows
                else:
                    blob(pix, lx, ly, 2, 1, "L" if rng.random() < 0.6 else "m", "l")
    for path in paths:                                                         # twigs on top
        for i, (x, y) in enumerate(path):
            pix[(x, y)] = "w" if (tree == "euc" and i % 5 == 3) else "W"
    for pi, path in enumerate(paths):                                          # flowers / fruit at the nodes
        for ni, (i, (x, y)) in enumerate(tile_nodes(path)):
            nx, ny = normals(path, i)
            sd = (1, -1)[ni % 2]
            fx, fy = round(x + sd * nx * 1.6), round(y + sd * ny * 1.6)
            if tree == "peach":
                if stage == "budding":
                    pix[(fx, fy)] = "B"; pix[(fx + sd, fy)] = "b"
                elif stage == "blossom":
                    for dx, dy, c in ((0, 0, "C"), (1, 0, "P"), (-1, 0, "P"), (0, 1, "Q"), (0, -1, "R")):
                        pix[(fx + dx, fy + dy)] = c
                elif stage == "fruit_set":
                    for dx in (0, 1):
                        for dy in (1, 2):
                            pix[(fx + dx, fy + dy)] = "G" if dx and dy == 2 else "g"
                elif stage in ("unripe", "ripe"):
                    cols = ("u", "U", "g") if stage == "unripe" else ("O", "E", "H")
                    for dy in range(1, 4):
                        for dx in range(3):
                            if (dx, dy) in ((0, 1), (2, 3)):
                                continue
                            pix[(fx + dx - 1, fy + dy)] = cols[2] if (dx, dy) == (0, 2) and stage == "ripe" else cols[1] if (dx, dy) in ((2, 2), (1, 3)) else cols[0]
            elif tree == "olive":
                if stage == "flowering":                               # erect racemes from the leaf axils
                    for k in range(3):
                        pix[(fx, fy - k)] = "F" if k % 2 else "f"
                    pix[(fx - 1, fy - 1)] = "y"; pix[(fx + 1, fy - 2)] = "y"
                elif stage == "unripe":
                    pix[(fx, fy)] = "g"; pix[(fx, fy + 1)] = "G"
                    if ni % 2:
                        pix[(fx + 1, fy + 1)] = "u"
                elif stage == "ripe":
                    pix[(fx, fy)] = "B"; pix[(fx, fy + 1)] = "B"; pix[(fx + 1, fy)] = "b"
                    if ni % 3 == 0:
                        pix[(fx - 1, fy + 2)] = "R"                    # some still turning colour
            else:
                if stage == "flowering":
                    for dx, dy, c in ((0, 0, "F"), (1, 0, "f"), (-1, 1, "y"), (1, 1, "F")):
                        pix[(fx + dx, fy + dy)] = c
                elif stage == "fruiting":
                    pix[(fx, fy)] = "K"; pix[(fx + 1, fy)] = "k"; pix[(fx, fy + 1)] = "k"
    return render(pix, pal)


def peach_sapling():
    pix = {}
    for cx, cy in ((4, 7), (12, 6), (8, 3), (5, 10), (11, 9)):
        blob(pix, cx, cy, 2, 1, "L", "l")
    poly(pix, [(8, 15), (8, 9)], "T")
    for st in ([(8, 11), (5, 8), (4, 7)], [(8, 10), (11, 7), (12, 6)], [(8, 9), (8, 3)], [(8, 12), (5, 10)], [(8, 11), (11, 9)]):
        poly(pix, st, "t")
    return render(pix, {"L": hx("#5b9a3c"), "l": hx("#3d7029"), "T": hx("#7a5035"), "t": hx("#9a4638")})


def peach_item():
    pix = parse([
        "................", ".........GG.....", "........GGG.....", ".....OOOTOO.....",
        "....OOOOOOOO....", "...OOHOOOOOOR...", "...OHOOOOOORR...", "...OOOOOOOORR...",
        "...OOOOOOORRR...", "...OOOOOOORRR...", "....OOOOORRR....", "....OOOOORR.....",
        ".....OOOOR......", "......OOR.......", "................", "................",
    ])
    return pix, {"O": hx("#f2a63f"), "R": hx("#e4573d"), "H": hx("#ffd27a"), "G": hx("#5b9a3c"), "T": hx("#7a5035")}


def peach_pit_item():
    pix = parse([
        "................", "................", "................", "................", ".......PP.......",
        "......PppP......", ".....PpPPpP.....", ".....PPpPPP.....", ".....PpPPpP.....", ".....PPpPPP.....",
        "......PpPP......", ".......PP.......", "................", "................", "................", "................",
    ])
    return pix, {"P": hx("#8a5a38"), "p": hx("#5e3a22")}


# ------------------------------------------------------------------ bark textures (trunk, branch, buttress)
def bark(seed, colours, runs=(2, 7), widths=(1, 1, 2), base="#d9904a", flecks=14, fleck="#6e4a5a", skip=0.2):
    rng = random.Random(seed)
    img = Image.new("RGBA", (SIZE, SIZE), hx(base))
    for x in range(SIZE):
        y = 0
        while y < SIZE:
            run = rng.randint(*runs)
            col = hx(rng.choice(colours)) if rng.random() > skip else hx(base)
            w = rng.choice(widths)
            for yy in range(y, min(SIZE, y + run)):
                for xx in range(x, min(SIZE, x + w)):
                    img.putpixel((xx, yy), col)
            y += run + rng.randint(0, 2)
    for _ in range(flecks):
        img.putpixel((rng.randrange(SIZE), rng.randrange(SIZE)), hx(fleck))
    return img


EUC_BARK = ["#a9d08a", "#c8503a", "#e8883a", "#9a9a96", "#6e4a5a", "#d9904a", "#7fb86a", "#b5472f"]


def peach_bark(kind):
    rng = random.Random("peach:bark:" + kind)
    greys = ["#4a4543", "#3d3837", "#58524f", "#332f2e"] if kind == "trunk" else ["#6e4a44", "#5a3a36", "#7a5650", "#4a3430"]
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    for x in range(SIZE):
        col = hx(rng.choice(greys))
        for y in range(SIZE):
            img.putpixel((x, y), col if rng.random() < 0.75 else hx(rng.choice(greys)))
    for y in (3, 8, 12):  # horizontal lenticels (Wikipedia)
        for x in rng.sample(range(SIZE), 5):
            img.putpixel((x, y), hx("#8a7f73"))
    return img


def trunk_top(rim, a, b):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    for x in range(SIZE):
        for y in range(SIZE):
            d = max(abs(x - 7.5), abs(y - 7.5))
            if x in (0, 15) or y in (0, 15):
                img.putpixel((x, y), hx(rim[(x + y) % len(rim)]))
            else:
                img.putpixel((x, y), hx(a if int(d) % 2 == 0 else b))
    return img


def buttress_side():
    """Flared base: vertical ridges and grooves (Wikipedia: buttresses up to 4 m high)."""
    rng = random.Random("euc:buttress")
    img = Image.new("RGBA", (SIZE, SIZE), hx("#c8783a"))
    for x in range(SIZE):
        ridge = x % 5 in (0, 1)
        for y in range(SIZE):
            c = rng.choice(["#b5472f", "#8a4a3a", "#6e4a5a"]) if not ridge else rng.choice(["#e8883a", "#d9904a", "#a9d08a", "#c8503a"])
            if rng.random() < 0.8:
                img.putpixel((x, y), hx(c))
    return img


# ------------------------------------------------------------------ eucalyptus sapling and seed
def euc_sapling():
    pix = {}
    for y in (13, 10, 7, 4):                              # opposite leaf pairs along the stem
        blob(pix, 5, y, 2, 1, "L", "l"); blob(pix, 11, y, 2, 1, "L", "l")
    poly(pix, [(8, 15), (8, 2)], "T")
    for y in (13, 10, 7, 4):
        poly(pix, [(8, y), (6, y)], "T"); poly(pix, [(8, y), (10, y)], "T")
    return render(pix, {"L": hx("#5f9a7a"), "l": hx("#3f7658"), "T": hx("#d9904a")})


def olive_sapling():
    pix = {}
    for y, sd in ((12, 1), (9, -1), (6, 1), (3, -1)):
        poly(pix, [(8, y), (8 + sd * 3, y - 1)], "L")
        poly(pix, [(8, y + 1), (8 - sd * 3, y)], "m")
    poly(pix, [(8, 15), (8, 2)], "T")
    return render(pix, {"L": hx("#7f9a7a"), "m": hx("#c8d4c4"), "T": hx("#8a7a68")})


def olive_stone():
    stone = parse([".k.", "PpP", "pPP", "PpP", ".P."])           # the hard, pitted stone
    out = {}
    for ox, oy in ((4, 8), (9, 6), (7, 11)):
        place(out, stone, ox, oy)
    return render(out, {"P": hx("#9a7a56"), "p": hx("#6e5236"), "k": hx("#4a3624")})


def gnarled_bark(kind):
    """Grey, twisted bark: long grooves that wander sideways, lighter ridges between them."""
    rng = random.Random("olive:bark:" + kind)
    greys = ["#6e6a64", "#5a5650", "#85807a", "#4a4640"] if kind == "trunk" else ["#8a857e", "#78736c", "#9a958e", "#66625b"]
    img = Image.new("RGBA", (SIZE, SIZE), hx(greys[0]))
    for y in range(SIZE):
        for x in range(SIZE):
            img.putpixel((x, y), hx(rng.choice(greys[:3])))
    for gx in (2, 6, 10, 14):                                    # twisting grooves
        x = gx
        for y in range(SIZE):
            x += rng.choice((-1, 0, 0, 1)) if kind == "trunk" else rng.choice((0, 0, 1))
            if 0 <= x < SIZE:
                img.putpixel((x, y), hx(greys[3]))
    return img


def euc_seed():
    pix = parse(["................"] * 8 + [".....SS.........", "....SsS...SS....", ".....SS..SsS....", "..SS......SS....", ".SsS...SS.......", "..SS..SsS.......", "........SS......", "................"])
    return render(pix, {"S": hx("#7a5a3a"), "s": hx("#a98456")})


# ------------------------------------------------------------------ driver
PLANTS = {}
_SIZES = None


def block_scale(pid):
    """How much of a block's height the plant fills, from its sourced size: a plant whose typical height is under one
    block is drawn only that tall, standing at the bottom of the block. Plants that can exceed a block fill it."""
    global _SIZES
    d = PLANTS.get(pid)
    if not d or d["size"]["source"] == "pending":
        return 1.0
    if _SIZES is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("sample_sizes", ROOT / "tools" / "sample_sizes.py")
        _SIZES = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_SIZES)
    cfg, per = _SIZES.load_cfg()
    hs = d["size"].get("height_sources") or [dict(d["size"]["height_cm"])]
    lo, hi, _ = _SIZES.typical_range(hs, cfg["range_mode"])
    if hi > per:
        return 1.0
    return max(0.4, min(1.0, (lo + hi) / 2 / per))


def draw_stage(pid, stage):
    """Return a 16x16 RGBA image for (species id, stage id)."""
    if pid.startswith("datura_"):
        p = dict(DATURA_DEFAULT, **DATURA[pid], s=block_scale(pid))
        return render(datura_stage(pid, stage, p), datura_palette(p))
    if pid == "ipomoea_tricolor":
        return render(*ipomoea_stage(stage))
    if pid == "chara_braunii":
        return render(*chara_stage(stage))
    if pid == "salvia_rosmarinus":
        return render(*rosemary_stage(stage))
    if pid == "oryza_sativa":
        return render(*rice_stage(stage))
    if pid == "prunus_persica":
        return peach_sapling() if stage == "sapling" else foliage_tile("peach", stage)
    if pid == "olea_europaea_europaea":
        if stage == "seed":
            return olive_stone()
        if stage == "sapling":
            return olive_sapling()
        return foliage_tile("olive", stage)
    if pid == "eucalyptus_deglupta":
        if stage == "seed":
            return euc_seed()
        if stage == "sapling":
            return euc_sapling()
        return foliage_tile("euc", stage)
    d = PLANTS.get(pid)
    if d and d["taxonomy"].get("family") == "Poaceae":
        P = grass_params(d)
        return render(*grass32_stage(pid, stage, P), n=G)
    raise KeyError(pid)


def draw_segment(pid, role):
    if pid.startswith("datura_") and role == "lower":
        p = dict(DATURA_DEFAULT, **DATURA[pid])
        return render(datura_stage(pid, "vegetative", p, "lower"), datura_palette(p))
    if pid == "salvia_rosmarinus" and role == "lower":
        return render(*rosemary_stage("mature", "lower"))
    if pid == "oryza_sativa" and role == "lower":
        return render(*rice_stage("tillering", "lower"))
    if pid == "prunus_persica":
        if role == "trunk_side":
            return peach_bark("trunk")
        if role == "branch_side":
            return peach_bark("branch")
        if role == "trunk_top":
            return trunk_top(["#3d3837"], "#946b45", "#7a5a3c")
    if pid == "olea_europaea_europaea":
        if role == "trunk_side":
            return gnarled_bark("trunk")
        if role == "branch_side":
            return gnarled_bark("branch")
        if role == "trunk_top":
            return trunk_top(["#4a4640"], "#b8a888", "#8a7a60")
    if pid == "eucalyptus_deglupta":
        if role == "trunk_side":
            return bark("euc:trunk:main", EUC_BARK)
        if role == "trunk_side_alt":
            return bark("euc:trunk:alt", EUC_BARK)
        if role == "branch_side":   # slimmer limbs: smoother, fewer, paler streaks
            return bark("euc:branch", ["#a9d08a", "#e8883a", "#9a9a96", "#d9904a"], runs=(4, 9), widths=(1, 2), base="#d9a070", flecks=6, skip=0.35)
        if role == "buttress_side":
            return buttress_side()
        if role == "trunk_top":
            return trunk_top(["#b5472f", "#e8883a", "#b5472f"], "#e8c98a", "#c9a060")
    d = PLANTS.get(pid)
    if d and d["taxonomy"].get("family") == "Poaceae" and role == "lower":
        return render(*grass32_stage(pid, "vegetative", grass_params(d), "lower"), n=G)
    raise KeyError((pid, role))


def sheet(images, labels, title, scale=6):
    pad, lab = 6, 12
    n = len(images)
    cell = 16 * scale                                    # every cell is the same size; 32x32 textures are drawn at half the zoom
    w = n * (cell + pad) + pad
    h = cell + 2 * pad + lab + 14
    out = Image.new("RGBA", (w, h), (46, 52, 60, 255))
    d = ImageDraw.Draw(out)
    d.text((pad, 3), title, fill=(230, 235, 240, 255))
    for i, (im, lb) in enumerate(zip(images, labels)):
        x = pad + i * (cell + pad)
        y = 14 + pad
        z = cell // im.width                              # pixel size in the preview
        bg = Image.new("RGBA", (cell, cell))
        bd = ImageDraw.Draw(bg)
        for cy in range(im.height):
            for cx in range(im.width):
                c = (88, 96, 108, 255) if (cx + cy) % 2 else (72, 80, 92, 255)
                bd.rectangle([cx * z, cy * z, cx * z + z - 1, cy * z + z - 1], fill=c)
        big = im.resize((cell, cell), Image.NEAREST)
        bg.alpha_composite(big)
        out.paste(bg, (x, y))
        d.text((x, y + cell + 1), lb[:16], fill=(200, 208, 216, 255))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    plants = {}
    for f in sorted((ROOT / "plants").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        plants[d["id"]] = d
    PLANTS.update(plants)
    missing = 0
    sheets = []
    for pid, d in plants.items():
        imgs, labels = [], []
        for st in d["growth_stages"]:
            out = ROOT / st["texture"]
            im = draw_stage(pid, st["id"])
            if not a.check:
                out.parent.mkdir(parents=True, exist_ok=True)
                im.save(out)
            if not im.getbbox():
                print(f"EMPTY {pid}:{st['id']}")
                missing += 1
            imgs.append(im)
            labels.append(st["id"])
        for sg in d.get("segment_textures", []):
            out = ROOT / sg["texture"]
            im = draw_segment(pid, sg["role"])
            if not a.check:
                out.parent.mkdir(parents=True, exist_ok=True)
                im.save(out)
            imgs.append(im)
            labels.append(sg["role"])
        if pid == "prunus_persica" and not a.check:
            for name, (pix, pal) in (("peach", peach_item()), ("peach_pit", peach_pit_item())):
                p = ROOT / "textures" / "item" / f"{name}.png"
                p.parent.mkdir(parents=True, exist_ok=True)
                render(pix, pal).save(p)
        sheets.append((pid, d, imgs, labels))
    if a.check:
        print("check ok" if not missing else f"{missing} empty textures")
        return 1 if missing else 0
    prev = ROOT / "docs" / "preview"
    prev.mkdir(parents=True, exist_ok=True)
    rows = []
    for pid, d, imgs, labels in sheets:
        s = sheet(imgs, labels, d["names"]["scientific"])
        s.save(prev / f"{pid}.png")
        rows.append(s)
    W = max(r.width for r in rows)
    H = sum(r.height for r in rows)
    allimg = Image.new("RGBA", (W, H), (46, 52, 60, 255))
    y = 0
    for r in rows:
        allimg.paste(r, (0, y))
        y += r.height
    allimg.save(prev / "all.png")
    n = sum(len(i) for _, _, i, _ in sheets)
    print(f"drew {n} stage textures for {len(sheets)} species")
    return 0


if __name__ == "__main__":
    sys.exit(main())
