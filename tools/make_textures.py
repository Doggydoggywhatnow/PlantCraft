#!/usr/bin/env python3
"""Graphics phase: draw a 16x16 pixel-art texture for every growth stage of every plant.

    python3 tools/make_textures.py            # textures/ + docs/preview/
    python3 tools/make_textures.py --check    # only verify every stage has a texture

Each plants/*.yaml lists its growth_stages with a planned `texture` path; this script
draws one PNG per stage at exactly that path (and a few extra item sprites), then
writes preview sheets. Art is drawn from the descriptions in the plant files: the
reference photos are not copied, so the textures are original pixel art.

Species that differ only in recorded traits (leaf colour, flower colour, capsule
shape, hairiness) are distinguished by those traits. Where the sources are thin,
the look is a placeholder variation on the genus design and is marked so in the
plant file's status, not invented botany.
"""
import argparse
import random
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SIZE = 16


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


# ------------------------------------------------------------------ Datura
VEG = [
    "................",
    "................",
    "......L..L......",
    ".....LLlLLL.....",
    "..L.LLLLlLLL.L..",
    ".LLLlLLTLLlLLL..",
    "..LLLLLTLLLLL...",
    ".LLlLLLTLLlLLL..",
    "..LLLLlTLLLLL...",
    "...LLLLTLLLL....",
    "....lLLTLLl.....",
    ".....LLTLL......",
    "......LTL.......",
    ".......T........",
    ".......T........",
    ".......T........",
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
TRUMPET_BIG = parse(["FHHHF", ".FfF.", "..f..", "..f.."])
TRUMPET_SMALL = parse(["FHF", ".f.", ".f."])
BUD = parse(["B", "B", "b"])
SPINY = parse([".pCp.", "pCCCp", "CCcCC", "pCCCp", ".pCp."])
LONG = parse(["..p.p..", ".pCCCp.", "pCCcCCp", ".pCCCp.", "..p.p.."])
SMOOTH = parse([".CCC.", "CCCCC", "CCcCC", "CCCCC", ".CCC."])
SPLIT = parse(["d...d", "DkKkD", "DKKKD", ".DDD."])
SPLIT_LONG = parse(["d.p.d", "DkKkD", "DKKKD", ".DDD."])

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
    "datura_innoxia": dict(leaf="#8aa488", leaf_d="#627f63", stem="#a9b89a", fuzzy=0.30, fuzz="#d9e0d4",
                           ),
    "datura_metel": dict(leaf="#4a7a3a", leaf_d="#5b3f73", flower="#a276d6", rim="#d9c2f5", throat="#5f3f99",
                         bud="#b894e6", bud_d="#7a54b8", capstyle="warty"),
    "datura_ferox": dict(leaf="#6a9a46", leaf_d="#46732f", flower="#f0ecc4", rim="#fbf8de", throat="#cfc98f",
                         flowers="small", capstyle="long", cap="#7a5a3a", cap_d="#4a3320", spine="#e0c89a",
                         ripe="#7a4a2e", ripe_d="#4d2d1b"),
    "datura_quercifolia": dict(leaf="#3f7a3a", leaf_d="#2c5a2b", flower="#efe9f4", throat="#b9a6dc", capstyle="long",
                               ragged=True),
    "datura_discolor": dict(leaf="#7cab5c", leaf_d="#55823f", stem="#8a3f8a", flower="#f7f4fb", rim="#ffffff",
                            throat="#7a3fa6", bud="#b894d4", bud_d="#7a3fa6"),
    "datura_ceratocaula": dict(leaf="#7a9a78", leaf_d="#58775a", stem="#8fa592", flower="#f3f0fb", throat="#e9b9d6",
                               rim="#ffffff", capstyle="smooth", cap="#c9d98a", cap_d="#8fa650", curve=True),
    "datura_leichhardtii": dict(leaf="#6e9a52", leaf_d="#4c7a3a", flower="#efe8bf", rim="#f8f3d6", throat="#cfc88f",
                                flowers="small", short=True, fuzzy=0.10),
    # Thin-source species: placeholder variations on traits the sources do give.
    "datura_kymatocarpa": dict(leaf="#7aa85a", leaf_d="#55823f", stem="#8a3f8a", throat="#7a3fa6", rim="#ffffff",
                               short=True),
    "datura_reburra": dict(leaf="#6ea057", leaf_d="#4d7a3d", stem="#8a3f8a", throat="#7a3fa6", rim="#ffffff"),
    "datura_lanosa": dict(leaf="#9ab294", leaf_d="#728c70", fuzzy=0.40, fuzz="#e8ece4", stem="#b5c4a8", short=True),
    "datura_arenicola": dict(leaf="#9cb06a", leaf_d="#7a8f4c", stem="#c4b88a", short=True),
    "datura_pruinosa": dict(leaf="#7fa49a", leaf_d="#5c8479", fuzzy=0.22, fuzz="#d6e4e0", stem="#9fb8ae",
                            ),
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


def place(pix, shape, ox, oy, remap=None):
    for (dx, dy), ch in shape.items():
        pix[(ox + dx, oy + dy)] = (remap or {}).get(ch, ch)


def outlined(pix, shape, ox, oy, remap=None):
    """Place a shape with a 1px dark outline on empty-of-shape neighbours."""
    cells = {(ox + dx, oy + dy) for (dx, dy) in shape}
    for (x, y) in cells:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in cells:
                pix[(nx, ny)] = "o"
    place(pix, shape, ox, oy, remap)


def datura_stage(pid, stage, p):
    rng = random.Random(pid)
    pix = parse(SEEDLING if stage == "seedling" else VEG)
    if stage == "seed":
        return parse(SEED)
    if p.get("ragged"):
        for (x, y), ch in list(pix.items()):
            if ch in "Ll" and any((x + dx, y + dy) not in pix for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                if rng.random() < 0.45:
                    del pix[(x, y)]
    if p.get("fuzzy"):
        for (x, y), ch in list(pix.items()):
            if ch in "Ll" and rng.random() < p["fuzzy"]:
                pix[(x, y)] = "w"
    yoff = 0
    if p.get("short") and stage != "seedling":
        pix = {(x, y + 3): ch for (x, y), ch in pix.items() if y >= 5}
        yoff = 3
    if p.get("curve"):
        pix = {(x + round((15 - y) / 8), y): ch for (x, y), ch in pix.items()}
    cap = {"spiny": SPINY, "long": LONG, "smooth": SMOOTH, "warty": SPINY}[p["capstyle"]]
    remap = {"p": "c"} if p["capstyle"] == "warty" else None
    trump = TRUMPET_SMALL if p["flowers"] == "small" else TRUMPET_BIG
    if stage == "budding":
        for ox, oy in ((3, 1), (7, 0), (11, 2)):
            place(pix, BUD, ox, oy + yoff)
    elif stage == "flowering":
        spots = ((0, 2), (10, 2), (5, 0)) if trump is TRUMPET_BIG else ((2, 2), (11, 3), (6, 1), (8, 5))
        for ox, oy in spots:
            place(pix, trump, ox, oy + yoff)
    elif stage == "fruiting":
        for ox, oy in ((0, 4), (10, 4), (5, 2)):
            outlined(pix, cap, ox, oy + yoff, remap)
    elif stage == "ripe_capsule":
        for ox, oy in ((0, 5), (10, 5), (5, 3)):
            outlined(pix, SPLIT_LONG if p["capstyle"] == "long" else SPLIT, ox, oy + yoff)
    return pix


# ------------------------------------------------------------------ Ipomoea tricolor
def ipomoea_stage(stage):
    leaf, leaf_d, stem = hx("#4f9a3c"), hx("#357a2c"), hx("#6aae48")
    blue, blue_hi, blue_d, throat = hx("#4a72e6"), hx("#9bb8ff"), hx("#2f4fb8"), hx("#f6e48a")
    bud, bud_d = hx("#a56ad8"), hx("#7a45b0")
    pod, pod_d = hx("#8a8a4a"), hx("#5e5e30")
    pal = {"L": leaf, "l": leaf_d, "T": stem, "F": blue, "H": blue_hi, "f": blue_d, "Y": throat,
           "B": bud, "b": bud_d, "P": pod, "p": pod_d, "K": hx("#1c1a1a"), "k": hx("#4a4040")}
    pix = {}
    if stage == "seed":
        pix = parse(["................"] * 7 + [".....KK.........", "....KkKK..KK....", "....KKKK.KkKK...",
                     ".....KK..KKKK...", "..KK......KK....", ".KkKK...........", ".KKKK....KK.....", "..KK....KkKK...."])
        return pix, pal
    if stage == "sprout":
        pix = parse(["................"] * 10 + [".....LL...LL....", "....LLLl.lLLL...", ".....lLLTLLl....",
                     ".......T.T......", ".......TT.......", ".......T........"])
        return pix, pal
    heart = parse([".L.L.", "LLLLL", ".LlL.", "..L.."])
    for y in range(16):
        for base, ph in ((4, 0.0), (11, 2.0)):
            import math
            pix[(base + round(1.4 * math.sin(y / 2 + ph)), y)] = "T"
    for ox, oy in ((1, 1), (10, 5), (2, 9), (9, 12)):
        place(pix, heart, ox, oy)
    if stage == "budding":
        for ox, oy in ((6, 2), (13, 7), (6, 10), (0, 13)):
            place(pix, parse(["B", "B", "b"]), ox, oy)
    elif stage == "flowering":
        big = parse(["HFFFH", ".FYF.", "..f.."])
        for ox, oy in ((0, 0), (9, 3), (1, 8), (10, 11)):
            place(pix, big, ox, oy)
    elif stage == "seed_pod":
        for ox, oy in ((6, 2), (12, 6), (6, 10), (1, 12)):
            place(pix, parse(["PP", "Pp"]), ox, oy)
    return pix, pal


# ------------------------------------------------------------------ Chara braunii
def chara_stage(stage):
    g, g_d, g_l = hx("#7fd09a", 235), hx("#4a9a6a", 235), hx("#b4ecc4", 235)
    mud, mud_d = hx("#5a4a38"), hx("#3a2f24")
    spore, orange = hx("#241a14"), hx("#e8863a")
    pix = {}
    def whorl(cy):
        for dx in (-1, 1):
            pix[(8 + dx, cy)] = "G"
            pix[(8 + dx * 2, cy - 1)] = "G"
            pix[(8 + dx * 3, cy - 2)] = "L"
            pix[(8 + dx * 2, cy + 1)] = "g"
    pal = {"G": g, "g": g_d, "L": g_l, "M": mud, "m": mud_d, "S": spore, "O": orange}
    if stage == "spore":
        for x, y in ((3, 15), (6, 14), (7, 15), (10, 15), (12, 14), (9, 13)):
            pix[(x, y)] = "S"
        for x in range(16):
            pix[(x, 15)] = pix.get((x, 15), "M" if x % 3 else "m")
        return pix, pal
    height, cys = {"sprout": (5, (11,)), "growing": (11, (12, 8, 4)), "fertile": (13, (13, 10, 7, 4))}[stage]
    for y in range(15, 15 - height, -1):
        pix[(8, y)] = "g" if y % 2 else "G"
    for cy in cys:
        whorl(cy)
    pix[(8, 15 - height)] = "L"
    if stage == "fertile":
        for cy in cys:
            pix[(7, cy + 1)] = "O"
            pix[(9, cy - 1)] = "O"
    return pix, pal


# ------------------------------------------------------------------ Prunus persica
def peach_leaves(kind):
    rng = random.Random("peach:" + kind)
    greens = [hx("#5b9a3c"), hx("#4a8433"), hx("#3d7029"), hx("#6aae48")]
    hole = {"young": 0.10, "budding": 0.30, "blossom": 0.07, "fruit_set": 0.10, "unripe": 0.10, "ripe": 0.10}[kind]
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    pink = [hx("#f7a8c4"), hx("#f08fb2"), hx("#ffd6e4"), hx("#e4709d")]
    for y in range(SIZE):
        for x in range(SIZE):
            r = rng.random()
            if r < hole:
                continue
            if kind == "blossom" and rng.random() < 0.6:
                img.putpixel((x, y), rng.choice(pink))
            else:
                img.putpixel((x, y), rng.choice(greens))
    if kind == "budding":
        for _ in range(7):
            img.putpixel((rng.randrange(SIZE), rng.randrange(SIZE)), hx("#7a4a3a"))
        for _ in range(6):
            img.putpixel((rng.randrange(SIZE), rng.randrange(SIZE)), hx("#d9728f"))
    spots = ((2, 2), (10, 3), (5, 9), (11, 11))
    fruit = {
        "fruit_set": ([hx("#a4c25a"), hx("#86a844")], 2),
        "unripe": ([hx("#c9d567"), hx("#a9bb4a"), hx("#e8a05a")], 3),
        "ripe": ([hx("#f2a63f"), hx("#e4573d"), hx("#ffd27a")], 3),
    }.get(kind)
    if fruit:
        cols, n = fruit
        for ox, oy in spots:
            for dy in range(n):
                for dx in range(n):
                    if n == 3 and dx in (0, 2) and dy in (0, 2) and (dx, dy) != (0, 0):
                        continue
                    c = cols[0]
                    if n == 3 and (dx, dy) == (0, 0):
                        c = cols[2] if kind == "ripe" else cols[0]
                    elif n == 3 and (dx, dy) in ((2, 1), (1, 2)):
                        c = cols[1]
                    elif n == 2 and (dx, dy) == (1, 1):
                        c = cols[1]
                    img.putpixel((ox + dx, oy + dy), c)
    return img


def peach_sapling():
    pix = parse([
        "................", "................", "................", "................",
        "......LL........", ".....LLlL.......", "....LLLLlLL.....", ".....lLLLLL.....",
        "......LLL.......", ".......T........", ".......T........", ".......T........",
        ".......T........", ".......T........", ".......T........", ".......T........",
    ])
    return pix, {"L": hx("#5b9a3c"), "l": hx("#3d7029"), "T": hx("#7a5035")}


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


# ------------------------------------------------------------------ driver
def draw_stage(pid, stage):
    """Return a 16x16 RGBA image for (species id, stage id)."""
    if pid.startswith("datura_"):
        p = dict(DATURA_DEFAULT, **DATURA[pid])
        return render(datura_stage(pid, stage, p), datura_palette(p))
    if pid == "ipomoea_tricolor":
        return render(*ipomoea_stage(stage))
    if pid == "chara_braunii":
        return render(*chara_stage(stage))
    if pid == "prunus_persica":
        if stage == "sapling":
            return render(*peach_sapling())
        return peach_leaves({"young_tree": "young"}.get(stage, stage))
    raise KeyError(pid)


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
