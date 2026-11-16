"""Stage 3 - EXTRACT: turn each species' Wikipedia text into structured, quote-backed facts.

    python3 pipeline/extract.py                  # call the Anthropic API for every raw file without one
    python3 pipeline/extract.py --export         # no API: write one ready-to-paste prompt per species
    python3 pipeline/extract.py --import-dir D   # read tool-call JSON answers produced elsewhere

Output: data/pipeline/extracted/<id>.json with {"facts": {...}, "dropped": [...], "model": ...}.

Grounding: the model must quote the source for every field. Each quote is checked as a verbatim
substring of the source text (whitespace-normalised); a field whose quote is missing is dropped and
recorded under "dropped". Fields are never guessed or back-filled here.

Needs: `pip install anthropic` and ANTHROPIC_API_KEY (not needed for --export / --import-dir).
"""
import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from common import CONFIG, HERE, RAW, WORK, append_jsonl, batch_raws, write_json

SCHEMA = json.loads((HERE / "extract.schema.json").read_text(encoding="utf-8"))
PROMPT = (HERE / "prompts" / "extract.md").read_text(encoding="utf-8")
OUT = WORK / "extracted"
TOOL = {"name": "record_species_facts",
        "description": "Record the facts found in the source text for this species.",
        "input_schema": SCHEMA}


def norm(s: str) -> str:
    """Normalise for quote matching: collapse whitespace, unify quotes/dashes, lowercase."""
    s = (s or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def source_text(raw: dict) -> str:
    wp = raw.get("wikipedia", {})
    text = wp.get("extract", "") if wp.get("found") else ""
    # Drop reference-style tail sections; they add tokens but no botanical facts.
    text = re.split(r"\n==+\s*(References|External links|Further reading|See also|Notes)\s*==+", text)[0]
    return text[:CONFIG["extract"]["max_source_chars"]]


def build_prompt(raw: dict) -> str:
    wp = raw.get("wikipedia", {})
    return PROMPT.format(name=raw["query"], url=wp.get("url", ""), text=source_text(raw))


LIST_FIELDS = ("measurements", "appearance", "architecture", "phenology", "propagation", "uses_real")


def _label(item: dict) -> str:
    return str(item.get("what") or item.get("part") or item.get("aspect") or item.get("event") or item.get("topic") or item.get("use") or "?")


def _quote_ok(item: dict, hay: str, numeric: bool) -> bool:
    q = norm(item.get("quote"))
    return bool(q) and q in hay and (not numeric or bool(re.search(r"\d", q)))


def verify(facts: dict, text: str):
    """Keep only facts whose quote(s) appear verbatim in the source text (numeric facts must quote a number)."""
    hay = norm(text)
    kept, dropped = {}, []
    for field, val in facts.items():
        if field in LIST_FIELDS:
            good = [i for i in val if _quote_ok(i, hay, field == "measurements")]
            dropped += [f"{field}:{_label(i)}" for i in val if i not in good]
            if good:
                kept[field] = good
        elif isinstance(val, dict):
            q = norm(val.get("quote"))
            if q and q in hay:
                kept[field] = val
            else:
                dropped.append(field)
    return kept, dropped


def call_model(client, prompt: str) -> dict:
    msg = client.messages.create(
        model=CONFIG["extract"]["model"], max_tokens=CONFIG["extract"]["max_tokens"],
        tools=[TOOL], tool_choice={"type": "tool", "name": TOOL["name"]},
        messages=[{"role": "user", "content": prompt}])
    for block in msg.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("model returned no tool call")


def finish(raw: dict, facts: dict, model: str) -> dict:
    kept, dropped = verify(facts, source_text(raw))
    rec = {"id": raw["id"], "model": model, "facts": kept, "dropped": dropped,
           "source_chars": len(source_text(raw))}
    write_json(OUT / f"{raw['id']}.json", rec)
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", action="store_true", help="write prompts to data/pipeline/prompts/ instead of calling the API")
    ap.add_argument("--import-dir", help="directory of <id>.json tool-call answers to verify and import")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--all", action="store_true", help="every file in data/raw/, not just the resolved batch")
    a = ap.parse_args()

    raws = []
    for raw in batch_raws(a.only, a.all):
        if not raw.get("wikipedia", {}).get("found"):
            print(f"  skip {raw['id']}: no Wikipedia article (nothing to extract from)")
            continue
        if (OUT / f"{raw['id']}.json").exists() and not a.force:
            continue
        raws.append(raw)
    print(f"extract: {len(raws)} species")

    if a.export:
        d = WORK / "prompts"
        d.mkdir(parents=True, exist_ok=True)
        for raw in raws:
            (d / f"{raw['id']}.md").write_text(build_prompt(raw), encoding="utf-8")
        print(f"wrote {len(raws)} prompts to {d}; answer each with JSON matching pipeline/extract.schema.json, "
              f"save as <id>.json in a folder, then run with --import-dir")
        return 0

    if a.import_dir:
        for raw in raws:
            f = os.path.join(a.import_dir, f"{raw['id']}.json")
            if os.path.exists(f):
                rec = finish(raw, json.load(open(f, encoding="utf-8")), "imported")
                print(f"  ok   {raw['id']}: {len(rec['facts'])} fields kept, {len(rec['dropped'])} dropped")
        return 0

    try:
        import anthropic
    except ImportError:
        sys.exit("pip install anthropic  (or use --export / --import-dir)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set  (or use --export / --import-dir)")
    client = anthropic.Anthropic()

    def work(raw):
        try:
            return raw, finish(raw, call_model(client, build_prompt(raw)), CONFIG["extract"]["model"]), None
        except Exception as e:
            append_jsonl(WORK / "failures.jsonl", {"stage": "extract", "id": raw["id"], "error": str(e)})
            return raw, None, e

    with ThreadPoolExecutor(CONFIG["extract"]["workers"]) as ex:
        for raw, rec, err in ex.map(work, raws):
            print(f"  FAIL {raw['id']}: {err}" if err else
                  f"  ok   {raw['id']}: {len(rec['facts'])} fields kept, {len(rec['dropped'])} dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
