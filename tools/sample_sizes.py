#!/usr/bin/env python3
"""Sample individual plant sizes from each species' published ranges (deterministic per position).

    python3 tools/sample_sizes.py [N] [--mode consensus|envelope]     N positions per species, default 2000

The same functions are what the game follows: size = f(world seed, x, z, species), so a plant keeps its
size forever and the same seed gives the same world.

Where the numbers come from (no invented values):
  * Each plant file lists every published height / width range it found (size.height_sources, size.spread_sources).
    A source that gives only a maximum ("up to 1.5 m") is read as 0..max.
  * consensus mode: an individual is drawn from the range all sources agree on (their overlap). If the sources
    do not overlap, the primary source (the first listed, a botanical description) is used and the disagreement is
    reported. If no source gives a minimum, there is no range to vary within and the plant is fixed at the stated
    maximum until a minimum is found.
  * envelope mode: lowest published minimum to highest published maximum.
  * A primary source that says big sizes are rare (common_max, e.g. the peach) gives a common range plus a small
    chance of a rare giant up to its maximum (config rare_tail_probability).
  * width is drawn with the same vigour as height, partly correlated (config size_correlation).
"""
import hashlib
import math
import random
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def rng_for(seed, x, z, pid, salt):
    h = hashlib.sha256(f"{seed}:{x}:{z}:{pid}:{salt}".encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def typical_range(sources, mode="consensus"):
    """-> (lo, hi, note) from a list of {min?, max, common_max?} source dicts."""
    if not sources:
        return None
    typ = [(s.get("min", 0), s.get("common_max", s["max"])) for s in sources]
    if mode == "envelope":
        mins = [s["min"] for s in sources if "min" in s]
        lo, hi = (min(mins) if mins else 0), max(s["max"] for s in sources)
        note = ""
    else:
        lo, hi = max(a for a, _ in typ), min(b for _, b in typ)
        note = ""
        if lo > hi:  # sources disagree: use the primary botanical description
            lo, hi = typ[0]
            note = "sources do not overlap; primary source used"
    if lo <= 0:      # nobody gave a minimum: nothing to vary within
        return (hi, hi, (note + "; " if note else "") + "no sourced minimum: fixed at stated maximum")
    return (lo, hi, note)


def sample(plant, x, z, cfg):
    """-> (height_cm, width_cm or None) for the plant at world position (x, z)."""
    sz = plant["size"]
    if sz["source"] == "pending":
        return None, None
    mode, pid, seed = cfg["range_mode"], plant["id"], cfg["world_seed"]
    hs = sz.get("height_sources") or [dict(sz["height_cm"])]
    lo, hi, _ = typical_range(hs, mode)
    u = rng_for(seed, x, z, pid, "h").random()   # this plant's vigour
    v = rng_for(seed, x, z, pid, "w").random()   # independent part of its width
    height = lo + u * (hi - lo)
    prim = hs[0]
    if "common_max" in prim and rng_for(seed, x, z, pid, "t").random() < cfg["rare_tail_probability"]:
        height = prim["common_max"] + u * (prim["max"] - prim["common_max"])   # a rare giant
    width = None
    ws = sz.get("spread_sources")
    if ws:
        wlo, whi, _ = typical_range(ws, mode)
        wu = cfg["size_correlation"] * u + (1 - cfg["size_correlation"]) * v
        width = wlo + wu * (whi - wlo)
    return height, width


def blocks(cm, per):
    return max(1, math.ceil(cm / per))


def load_cfg(mode=None):
    cfg = yaml.safe_load((ROOT / "config" / "variation.yaml").read_text())
    if mode:
        cfg["range_mode"] = mode
    per = float(yaml.safe_load((ROOT / "config" / "scale.yaml").read_text())["cm_per_block"])
    return cfg, per


def main(argv):
    mode = None
    if "--mode" in argv:
        i = argv.index("--mode"); mode = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    n = int(argv[0]) if argv else 2000
    cfg, per = load_cfg(mode)
    print(f"{n} plants per species, {per:g} cm per block, range mode: {cfg['range_mode']}, correlation {cfg['size_correlation']}\n")
    print(f"{'species':32}{'height range (cm)':20}{'blocks tall (share)':34}{'blocks wide'}")
    for f in sorted((ROOT / "plants").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        th, tw = Counter(), Counter()
        hs = d["size"].get("height_sources") or ([dict(d["size"]["height_cm"])] if d["size"]["source"] != "pending" else [])
        rng = typical_range(hs, cfg["range_mode"]) if hs else None
        for i in range(n):
            h, w = sample(d, i % 50, i // 50, cfg)
            if h is None:
                th[1] += 1; tw[1] += 1
                continue
            th[blocks(h, per)] += 1
            tw[blocks(w, per) if w else 1] += 1
        fmt = lambda c: "  ".join(f"{k}:{'<1' if 0 < 100 * v / n < 1 else round(100 * v / n)}%" for k, v in sorted(c.items()))
        shown = (f"{rng[0]:g}-{rng[1]:g}" if rng and rng[0] != rng[1] else (f"{rng[0]:g} (fixed)" if rng else "no data"))
        flag = "  [" + rng[2] + "]" if rng and rng[2] else ""
        print(f"{d['names']['scientific']:32}{shown:20}{fmt(th):34}{fmt(tw)}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
