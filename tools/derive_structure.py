#!/usr/bin/env python3
"""Derive block-structure sizes from each plant's real size data.

    python3 tools/derive_structure.py [cm_per_block ...]     (default: 100 60 50)

Blocks tall = ceil(height / cm_per_block), never less than 1. Nothing is typed by hand:
change the scale and every species follows. Species whose size source is 'pending'
are reported as 1 block and flagged, because their height is not real data yet.
"""
import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def blocks(cm, per):
    return max(1, math.ceil(cm / per))


def main(argv):
    scales = [float(a) for a in argv] or [100, 60, 50]
    rows = []
    for f in sorted((ROOT / "plants").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        z = d["size"]
        h = z["height_cm"]
        lo, hi = h.get("min"), h["max"]
        cells = []
        for per in scales:
            t_hi = blocks(hi, per)
            t_lo = blocks(lo, per) if lo else None
            tall = f"{t_lo}-{t_hi}" if t_lo and t_lo != t_hi else f"{t_hi}"
            if "spread_cm" in z:
                tall += f" x{blocks(z['spread_cm']['max'], per)}w"
            cells.append(tall)
        rng = f"{lo or '?'}-{hi}" if z["source"] != "pending" else "no data"
        rows.append((d["names"]["scientific"], rng + " cm", z["habit"], cells, z["source"] == "pending"))
    print(f"{'species':24}{'real height':14}{'habit':14}" + "".join(f"{int(s)}cm/block".ljust(14) for s in scales))
    for name, rng, habit, cells, pend in rows:
        print(f"{name:24}{rng:14}{habit:14}" + "".join(c.ljust(14) for c in cells) + ("  (size pending)" if pend else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
