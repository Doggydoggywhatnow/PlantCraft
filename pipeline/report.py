"""Stage 5 - REPORT: one coverage table so a person reviews a table instead of 100s of files.

    python3 pipeline/report.py

Writes data/pipeline/coverage.md and coverage.csv with, per species: which fields came from sources,
which were defaulted or missing, what was dropped for failing quote verification, and anything that
needs a human (review-list names, fetch failures). Also prints a short summary.
"""
import csv
import json
import sys
from collections import Counter

import yaml

from common import RAW, WORK, batch_raws, read_jsonl

FIELDS = ["life_form", "description", "height_cm", "spread_cm", "native_range", "environment",
          "flowers", "fruit", "uses_real"]


def main():
    rows = []
    for raw in batch_raws():
        eid = raw["id"]
        ext_p = WORK / "extracted" / f"{eid}.json"
        ext = json.loads(ext_p.read_text(encoding="utf-8")) if ext_p.exists() else None
        draft_p = WORK / "drafts" / f"{eid}.yaml"
        draft = yaml.safe_load(draft_p.read_text(encoding="utf-8")) if draft_p.exists() else {}
        rng = raw.get("gbif_range") or {}
        row = {
            "id": eid,
            "wikipedia": "yes" if raw["wikipedia"].get("found") else "NO",
            "gbif": "yes" if raw["gbif"].get("found") else "NO",
            "occurrences": rng.get("total_records", ""),
            "images": len(raw.get("commons_images", [])),
            "extracted": "yes" if ext else "no",
            "confidence": draft.get("confidence", ""),
            "dropped": ",".join(ext["dropped"]) if ext else "",
        }
        for f in FIELDS:
            row[f] = ("src" if ext and f in ext["facts"] else "-") if ext else "?"
        rows.append(row)

    cols = ["id", "wikipedia", "gbif", "occurrences", "images", "extracted", "confidence"] + FIELDS + ["dropped"]
    with (WORK / "coverage.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    resolved = read_jsonl(WORK / "resolved.jsonl")
    review = [r for r in resolved if r["status"] != "ok"]
    fails = read_jsonl(WORK / "failures.jsonl")
    lines = ["# Pipeline coverage", "",
             f"{len(rows)} species fetched, {sum(r['extracted'] == 'yes' for r in rows)} extracted.", "",
             "Legend: `src` filled from quote-verified source text, `-` not in sources (defaulted or blank), `?` not extracted yet.", "",
             "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    if review:
        lines += ["", "## Names needing a human (not fetched)", ""]
        lines += [f"- `{r['input']}`: {r['status']}" + (f" ({r['reason']})" if r.get("reason") else "")
                  + (f" -> {r['name']}" if r.get("name") else "") for r in review]
    if fails:
        lines += ["", "## Failures", ""] + [f"- {x['stage']} `{x['id']}`: {x['error'][:150]}" for x in fails]
    (WORK / "coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    ext_rows = [r for r in rows if r["extracted"] == "yes"]
    print(f"{len(rows)} fetched, {len(ext_rows)} extracted, {len(review)} names need review, {len(fails)} failures")
    if ext_rows:
        c = Counter(f for r in ext_rows for f in FIELDS if r[f] == "src")
        print("field coverage:", ", ".join(f"{f} {c[f]}/{len(ext_rows)}" for f in FIELDS))
    print(f"wrote {WORK / 'coverage.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
