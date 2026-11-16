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


def render(pix, palette):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    for (x, y), ch in pix.items():
        if 0 <= x < SIZE and 0 <= y < SIZE:
            img.putpixel((x, y), palette[ch] if ch in palette else hx("#ff00ff"))  # magenta = missing palette key
    return img


def line(pix, x0, y0, x1, y1, ch):
    """Bresenham line into pix."""
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
            sides = (1, -1) if tree == "euc" else ((1, -1)[ni % 2],)           # eucalyptus: opposite pairs; peach: alternate
            for sd in sides:
                lx, ly = round(x + sd * nx * 2.2), round(y + sd * ny * 2.2)
                if leafless and rng.random() < 0.75:
                    continue
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
    if pid == "eucalyptus_deglupta":
        if stage == "seed":
            return euc_seed()
        if stage == "sapling":
            return euc_sapling()
        return foliage_tile("euc", stage)
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
    raise KeyError((pid, role))


def sheet(images, labels, title, scale=6):
    pad, lab = 6, 12
    n = len(images)
    w = n * (SIZE * scale + pad) + pad
    h = SIZE * scale + 2 * pad + lab + 14
    out = Image.new("RGBA", (w, h), (46, 52, 60, 255))
    d = ImageDraw.Draw(out)
    d.text((pad, 3), title, fill=(230, 235, 240, 255))
    for i, (im, lb) in enumerate(zip(images, labels)):
        x = pad + i * (SIZE * scale + pad)
        y = 14 + pad
        bg = Image.new("RGBA", (SIZE * scale, SIZE * scale))
        bd = ImageDraw.Draw(bg)
        for cy in range(SIZE):
            for cx in range(SIZE):
                c = (88, 96, 108, 255) if (cx + cy) % 2 else (72, 80, 92, 255)
                bd.rectangle([cx * scale, cy * scale, cx * scale + scale - 1, cy * scale + scale - 1], fill=c)
        big = im.resize((SIZE * scale, SIZE * scale), Image.NEAREST)
        bg.alpha_composite(big)
        out.paste(bg, (x, y))
        d.text((x, y + SIZE * scale + 1), lb[:16], fill=(200, 208, 216, 255))
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
