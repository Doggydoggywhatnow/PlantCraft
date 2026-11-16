"""Stage 2 - FETCH: concurrent, resumable download of raw reference data for resolved species.

    python3 pipeline/fetch.py            # every "ok" species in data/pipeline/resolved.jsonl
    python3 pipeline/fetch.py --force    # refetch even if data/raw/<id>.json exists

Writes data/raw/<id>.json in the same format tools/fetch.py produces, plus a "gbif_range" block
(latitude/elevation envelope and top countries from GBIF occurrence records). The Wikipedia,
Wikidata, GBIF and Commons parsing is reused from tools/fetch.py; only the HTTP layer is swapped
for the thread-safe, per-host rate-limited client in common.py.
"""
import argparse
import importlib.util
import json
import random
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from common import CONFIG, RAW, ROOT, WORK, append_jsonl, get_json, read_jsonl, write_json

# Reuse the tested parsers from tools/fetch.py, but route their HTTP through our client.
_spec = importlib.util.spec_from_file_location("tools_fetch", ROOT / "tools" / "fetch.py")
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
legacy.get = get_json


def quantile(sorted_vals, p):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, round(p * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def gbif_range(key: int) -> dict:
    """Where the species actually grows, from georeferenced GBIF records (no API key needed).

    GBIF returns records in dataset order and deep paging (offset > ~5,000) is very slow, so a plain
    first page is geographically biased. Instead we take one small page from each of the top
    countries (random shallow offset), which spreads the sample across the real range.
    """
    base = "https://api.gbif.org/v1/occurrence/search?"
    common = dict(taxonKey=key, hasCoordinate="true", hasGeospatialIssue="false")
    facets = get_json(base + urllib.parse.urlencode({**common, "limit": 0, "facet": "COUNTRY", "facetLimit": 10}))
    total = facets.get("count", 0)
    top = [(c["name"], c["count"]) for f in facets.get("facets", []) for c in f.get("counts", [])]
    per = max(10, CONFIG["fetch"]["occurrence_sample"] // 6)
    rng = random.Random(key)  # deterministic per species
    results = []
    for code, n in (top[:6] or [(None, total)]):
        q = dict(common, limit=per, offset=rng.randint(0, max(0, min(n, 5000) - per)))
        if code:
            q["country"] = code
        results += get_json(base + urllib.parse.urlencode(q)).get("results", [])
    lats = sorted(r["decimalLatitude"] for r in results if "decimalLatitude" in r)
    lons = sorted(r["decimalLongitude"] for r in results if "decimalLongitude" in r)
    elev = sorted(r["elevation"] for r in results if isinstance(r.get("elevation"), (int, float)))
    countries = [c for c, _ in top]
    return {
        "total_records": total,
        "sampled": len(lats),
        "countries_top10": countries,
        "lat": {"p5": quantile(lats, .05), "p50": quantile(lats, .5), "p95": quantile(lats, .95)} if lats else None,
        "lon": {"p5": quantile(lons, .05), "p50": quantile(lons, .5), "p95": quantile(lons, .95)} if lons else None,
        "elevation_m": {"p5": quantile(elev, .05), "p95": quantile(elev, .95), "n": len(elev)} if len(elev) >= 20 else None,
        "note": "Records include cultivated and introduced plants; treat as an upper bound on range.",
    }


def fetch_one(rec: dict) -> dict:
    name = rec["name"]
    d = legacy.fetch(name)
    d["id"] = rec["id"]
    d["query"] = rec["input"]
    if d["gbif"].get("found"):
        d["gbif_range"] = gbif_range(d["gbif"]["key"])
    return d


def run(force=False, workers=None, only=None) -> int:
    recs = [r for r in read_jsonl(WORK / "resolved.jsonl") if r["status"] == "ok"]
    if only:
        recs = [r for r in recs if r["id"] in only or r["input"] in only]
    todo = [r for r in recs if force or not (RAW / f"{r['id']}.json").exists()]
    print(f"fetch: {len(todo)} to do, {len(recs) - len(todo)} cached")
    RAW.mkdir(parents=True, exist_ok=True)
    failures = 0
    t0 = time.time()

    def work(rec):
        try:
            d = fetch_one(rec)
            write_json(RAW / f"{rec['id']}.json", d)
            return rec, d, None
        except Exception as e:
            append_jsonl(WORK / "failures.jsonl", {"stage": "fetch", "id": rec["id"], "error": str(e)})
            return rec, None, e

    with ThreadPoolExecutor(workers or CONFIG["workers"]) as ex:
        for rec, d, err in ex.map(work, todo):
            if err:
                failures += 1
                print(f"  FAIL {rec['name']}: {err}")
            else:
                print(f"  ok   {rec['name']:30} wikipedia={'yes' if d['wikipedia'].get('found') else 'NO '} "
                      f"images={len(d['commons_images'])} occ={d.get('gbif_range', {}).get('total_records', '-')}")
    print(f"fetch done in {time.time() - t0:.0f}s, {failures} failed (see data/pipeline/failures.jsonl)")
    return failures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*", help="limit to these ids or input names")
    a = ap.parse_args()
    return 1 if run(a.force, only=set(a.only) if a.only else None) else 0


if __name__ == "__main__":
    sys.exit(main())
