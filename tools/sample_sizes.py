#!/usr/bin/env python3
"""Sample individual plant sizes from each species' real data (deterministic per position).

    python3 tools/sample_sizes.py [N]       # N positions per species, default 2000

The same function is what the game will use: size = f(world seed, x, z, species), so a
plant keeps its size forever and the same seed gives the same world.
  * height comes from the species' real height range (mostly within `common_max`, with a rare
    tail up to the maximum, when the source says large sizes are rare; otherwise uniform); width from its width envelope, correlated with height by
    config/variation.yaml `size_correlation`.
  * a species with no size data (size.source: pending) is not varied: 1 block.
  * blocks = ceil(cm / cm_per_block), at least 1.
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


def draw(rg, lo, hi, mode=None):
    return rg.triangular(lo, hi, mode) if mode is not None else rg.uniform(lo, hi)


def sample(plant, x, z, cfg):
    """-> (height_cm, width_cm or None) for the plant at world position (x, z)."""
    sz = plant["size"]
    if sz["source"] == "pending":
        return None, None
    h = sz["height_cm"]
    hi = h["max"]
    lo = h.get("min", hi * cfg["unknown_min_fraction"])
    c = cfg["size_correlation"]
    pid, seed = plant["id"], cfg["world_seed"]
    u = rng_for(seed, x, z, pid, "h").random()          # this plant's vigour
    v = rng_for(seed, x, z, pid, "w").random()          # independent part of its width
    if "common_max" in h:  # sources say bigger sizes are rare: most plants sit in [lo, common_max]
        tail = rng_for(seed, x, z, pid, "t").random() < cfg["rare_tail_probability"]
        height = (h["common_max"] + u * (hi - h["common_max"])) if tail else lo + u * (h["common_max"] - lo)
    else:
        height = lo + u * (hi - lo)
    width = None
    sp = sz.get("spread_cm")
    if sp:
        wu = c * u + (1 - c) * v
        wlo = sp.get("min", sp["max"] * cfg["unknown_min_fraction"])
        width = wlo + wu * (sp["max"] - wlo)
    return height, width


def blocks(cm, per):
    return max(1, math.ceil(cm / per))


def main(argv):
    n = int(argv[0]) if argv else 2000
    cfg = yaml.safe_load((ROOT / "config" / "variation.yaml").read_text())
    per = float(yaml.safe_load((ROOT / "config" / "scale.yaml").read_text())["cm_per_block"])
    print(f"{n} plants per species, {per:g} cm per block, correlation {cfg['size_correlation']}\n")
    print(f"{'species':22}{'blocks tall (share of plants)':44}{'blocks wide'}")
    for f in sorted((ROOT / "plants").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        th, tw = Counter(), Counter()
        for i in range(n):
            h, w = sample(d, i % 50, i // 50, cfg)
            if h is None:
                th[1] += 1; tw[1] += 1
                continue
            th[blocks(h, per)] += 1
            tw[blocks(w, per) if w else 1] += 1
        fmt = lambda c: "  ".join(f"{k}:{'<1' if 0 < 100 * v / n < 1 else round(100 * v / n)}%" for k, v in sorted(c.items()))
        note = "  (no size data: fixed)" if d["size"]["source"] == "pending" else ""
        print(f"{d['names']['scientific']:22}{fmt(th):44}{fmt(tw)}{note}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
