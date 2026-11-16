"""Stage 1 - RESOLVE: turn a list of names into GBIF-accepted species.

    python3 pipeline/resolve.py lists/example.txt
    python3 pipeline/resolve.py lists/my.txt --accept-fuzzy

Input lines can be:
    Quercus robur          a scientific name (synonyms are mapped to the accepted name)
    genus:Datura           every accepted species in the genus
    family:Lamiaceae       every accepted species in the family (can be thousands: use --limit)

Output: data/pipeline/resolved.jsonl, one record per input line:
    {"input", "id", "name", "gbif_key", "status": "ok"|"review"|"not_found", "reason", ...}
Only status "ok" records go on to the fetch stage. "review" records (fuzzy or low-confidence
matches, synonyms that point at a different species, duplicates) are listed so a person can
fix the input name instead of the pipeline guessing.
"""
import argparse
import json
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from common import CONFIG, WORK, append_jsonl, get_json, read_jsonl, read_names, species_id

GBIF = "https://api.gbif.org/v1/"


def q(**kw):
    return urllib.parse.urlencode(kw)


def match(name: str) -> dict:
    return get_json(GBIF + "species/match?" + q(name=name, kingdom="Plantae", strict="false"))


def resolve_name(name: str, accept_fuzzy: bool) -> dict:
    rec = {"input": name}
    m = match(name)
    if not m.get("usageKey"):
        return {**rec, "status": "not_found", "reason": m.get("note") or "no GBIF match"}
    key = m.get("acceptedUsageKey") or m["usageKey"]
    accepted = get_json(GBIF + f"species/{key}")
    rank = accepted.get("rank")
    canonical = accepted.get("canonicalName") or accepted.get("scientificName")
    rec.update(gbif_key=key, name=canonical, rank=rank, match_type=m.get("matchType"),
               confidence=m.get("confidence"), synonym_of=canonical if m.get("synonym") else None,
               family=accepted.get("family"), id=species_id(canonical))
    reasons = []
    if rank not in ("SPECIES", "SUBSPECIES", "VARIETY"):
        reasons.append(f"resolved to rank {rank}, not a species")
    if m.get("matchType") not in CONFIG["resolve"]["accept_match_types"] and not accept_fuzzy:
        reasons.append(f"match type {m.get('matchType')}")
    if (m.get("confidence") or 0) < CONFIG["resolve"]["min_confidence"] and not accept_fuzzy:
        reasons.append(f"confidence {m.get('confidence')}")
    if accepted.get("taxonomicStatus") not in ("ACCEPTED", "DOUBTFUL", None) and not rec["synonym_of"]:
        reasons.append(f"status {accepted.get('taxonomicStatus')}")
    rec["status"] = "review" if reasons else "ok"
    rec["reason"] = "; ".join(reasons)
    return rec


def expand(line: str, limit: int) -> list:
    """'genus:Datura' -> accepted species names under that taxon."""
    kind, _, taxon = line.partition(":")
    kind, taxon = kind.lower().strip(), taxon.strip()
    m = match(taxon)
    if not m.get("usageKey"):
        return []
    names, offset = [], 0
    while len(names) < limit:
        page = get_json(GBIF + "species/search?" + q(
            highertaxonKey=m["usageKey"], rank="SPECIES", status="ACCEPTED",
            datasetKey="d7dddbf4-2cf0-4f39-9b2a-bb099caae36c",  # GBIF Backbone Taxonomy
            limit=min(200, limit - len(names)), offset=offset))
        names += [r["canonicalName"] for r in page.get("results", []) if r.get("canonicalName")]
        if page.get("endOfRecords") or not page.get("results"):
            break
        offset += len(page["results"])
    return names[:limit]


def run(lines, accept_fuzzy=False, limit=500, workers=None, force=False) -> list:
    out = WORK / "resolved.jsonl"
    done = {r["input"] for r in read_jsonl(out)} if not force else set()
    if force and out.exists():
        out.unlink()
    names = []
    for line in lines:
        names += expand(line, limit) if ":" in line else [line]
    todo = [n for n in dict.fromkeys(names) if n not in done]
    print(f"resolve: {len(todo)} to do, {len(names) - len(todo)} already resolved")

    def work(n):
        try:
            rec = resolve_name(n, accept_fuzzy)
        except Exception as e:
            rec = {"input": n, "status": "error", "reason": str(e)}
        append_jsonl(out, rec)
        return rec

    with ThreadPoolExecutor(workers or CONFIG["workers"]) as ex:
        for rec in ex.map(work, todo):
            tag = rec["status"].upper().ljust(9)
            extra = f" -> {rec.get('name')}" if rec.get("name") and rec["name"] != rec["input"] else ""
            print(f"  {tag}{rec['input']}{extra}" + (f"  [{rec['reason']}]" if rec.get("reason") else ""))

    # Two inputs that resolve to the same accepted species are one species: keep the first.
    seen, final = {}, []
    for rec in read_jsonl(out):
        if rec["status"] == "ok":
            if rec["id"] in seen:
                rec["status"], rec["reason"] = "review", f"duplicate of {seen[rec['id']]}"
            else:
                seen[rec["id"]] = rec["input"]
        final.append(rec)
    (WORK / "resolved.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in final),
                                         encoding="utf-8")
    counts = {}
    for r in final:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("resolve summary:", counts)
    return final


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("list")
    ap.add_argument("--accept-fuzzy", action="store_true")
    ap.add_argument("--limit", type=int, default=500, help="max species per genus:/family: line")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    from pathlib import Path
    run(read_names(Path(a.list)), a.accept_fuzzy or CONFIG["resolve"]["fuzzy_ok"], a.limit, force=a.force)


if __name__ == "__main__":
    sys.exit(main())
