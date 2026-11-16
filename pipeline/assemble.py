"""Stage 4 - ASSEMBLE: merge raw data + verified extracted facts into schema-valid plant YAML drafts.

    python3 pipeline/assemble.py                 # drafts -> data/pipeline/drafts/<id>.yaml
    python3 pipeline/assemble.py --write         # publish drafts to plants/ (never overwrites existing files)
    python3 pipeline/assemble.py --write --force # overwrite existing plants/<id>.yaml too (careful)

What comes from where:
  * taxonomy, names, sources, images ........ raw API data (GBIF, Wikidata, Wikipedia, Commons)
  * description, habitat, size, flowers,
    fruit, uses_real, life_form ............. extracted facts that passed quote verification
  * growth_stages, implementation ........... defaults.yaml (game design defaults, flagged as such)
  * spawn biomes ............................ habitat keywords, else median GBIF latitude (flagged as a guess)
Anything missing is left as an explicit "not found in sources" marker and lowers `confidence`.
Drafts always get status.data = draft. Hand-made files are never touched without --force.
"""
import argparse
import html
import json
import re
import sys

import jsonschema
import yaml

from common import CONFIG, HERE, PLANTS, RAW, ROOT, WORK, batch_raws, write_json

PHOTOS = ROOT / CONFIG['paths']['photos']

DEFAULTS = yaml.safe_load((HERE / "defaults.yaml").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schema" / "plant.schema.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
OUT = WORK / "drafts"
NOT_FOUND = "not found in fetched sources"


def first_paragraph(text: str) -> str:
    for para in (text or "").split("\n"):
        if len(para) > 80 and not para.startswith("="):
            return para.strip()
    return ""


def _entry(m, name, url):
    e = {"name": name, "url": url}
    if "min" in m:
        e["min"] = m["min"]
    e["max"] = m["max"]
    e["quote"] = m["quote"]
    return e


def range_sources(items, name, url):
    """One source entry for a quantity (height, spread ...) from the measurements the model found.

    A stated range wins; a single typical value or an 'up to' value becomes a maximum; if the text also says
    large sizes are rare, the typical top becomes common_max and the rare figure becomes max (see tools/sample_sizes.py)."""
    ranges = [m for m in items if m.get("qualifier") in (None, "range", "typical", "average")]
    rare = [m for m in items if m.get("qualifier") == "rare_maximum"]
    maxes = [m for m in items if m.get("qualifier") == "maximum"]
    prim = next((m for m in ranges if "min" in m), None) or (ranges[0] if ranges else (maxes[0] if maxes else None))
    if prim is None:
        return []
    e = _entry(prim, name, url)
    if rare:
        e["common_max"], e["max"] = e["max"], max(r["max"] for r in rare)
    return [e]


def build_size(facts, habit, wp):
    """The `size` section from measurements (or the older height_cm/spread_cm facts); a 'pending' placeholder if none."""
    meas = [m for m in facts.get("measurements", []) if m["unit"] == "cm"]
    for key, what in (("height_cm", "height"), ("spread_cm", "spread")):      # older extraction format
        if facts.get(key) and not any(m["what"] == what for m in meas):
            meas.append(dict(facts[key], what=what, unit="cm", qualifier="range" if "min" in facts[key] else "maximum"))
    name = f"Wikipedia: {wp['title']}" if wp.get("found") else "Wikipedia"
    url = wp.get("url", "")
    hs = range_sources([m for m in meas if m["what"] == "height"], name, url)
    if not hs:
        return {"height_cm": {"max": 1}, "habit": habit, "source": "pending",
                "quote": "No height figure in the fetched sources; max is a placeholder, not data."}
    h = {k: hs[0][k] for k in ("min", "max", "common_max") if k in hs[0]}
    size = {"height_cm": h, "habit": habit, "source": "wikipedia", "quote": hs[0]["quote"], "height_sources": hs}
    ss = range_sources([m for m in meas if m["what"] == "spread"], name, url)
    if ss:
        size["spread_cm"] = {k: ss[0][k] for k in ("min", "max") if k in ss[0]}
        size["spread_sources"] = ss
    trunk = [m for m in meas if m["what"] == "trunk_diameter"]
    if trunk:
        size["trunk_diameter_cm"] = {"max": max(m["max"] for m in trunk)}
    return size


def pick_biomes(life_form: str, env_text: str, lat: float):
    if life_form == "alga":
        return DEFAULTS["aquatic_biomes"], "aquatic life form"
    hits = []
    for kw, biomes in DEFAULTS["biome_keywords"].items():
        if re.search(rf"\b{kw}", (env_text or "").lower()):
            hits += [b for b in biomes if b not in hits]
    if hits:
        return hits[:4], "habitat text mentions it"
    if lat is not None:
        for band in DEFAULTS["biome_by_latitude"]:
            if abs(lat) <= band["max_abs_lat"]:
                return band["biomes"], f"median GBIF record latitude {lat:.0f} deg"
    return ["minecraft:plains", "minecraft:forest"], "no habitat or range data; generic fallback"


def build(raw: dict, ext: dict) -> dict:
    facts = (ext or {}).get("facts", {})
    gb, wd, wp = raw.get("gbif", {}), raw.get("wikidata", {}), raw.get("wikipedia", {})
    rng = raw.get("gbif_range") or {}
    cls = gb.get("classification", {})
    canonical = gb.get("canonical_name") or raw["query"]
    parts = canonical.split()
    sci = gb.get("scientific_name", "")
    authority = sci[len(canonical):].strip() if sci.startswith(canonical) else ""

    taxonomy = {"kingdom": cls.get("kingdom") or "Plantae", "order": cls.get("order"), "family": cls.get("family"),
                "genus": cls.get("genus") or parts[0], "species": parts[1] if len(parts) > 1 else ""}
    if authority:
        taxonomy["authority"] = authority
    if len(parts) > 2:
        taxonomy["subspecies"] = parts[-1]
    taxonomy = {k: v for k, v in taxonomy.items() if v}

    seen_names, commons = set(), []
    for c in wd.get("english_common_names", []) + gb.get("english_vernacular_names", []):
        if c.lower() not in seen_names and c.lower() != canonical.lower():
            seen_names.add(c.lower())
            commons.append(c)
    commons = commons[:6] or [canonical]
    life = facts.get("life_form", {}).get("value")
    lf = DEFAULTS["life_forms"][life] if life else DEFAULTS["life_forms"]["perennial_herb"]
    lat = (rng.get("lat") or {}).get("p50")

    env = facts.get("environment", {}).get("value")
    habitat = {"native_range": facts.get("native_range", {}).get("value") or
               ("; ".join(rng.get("countries_top10", [])[:5]) and
                f"Most GBIF records from: {', '.join(rng['countries_top10'][:5])} (includes introduced range)") or NOT_FOUND,
               "environment": env or NOT_FOUND}
    if facts.get("introduced_range"):
        habitat["introduced_range"] = facts["introduced_range"]["value"]
    if life:
        habitat["life_form"] = life
    dist = raw.get("distribution") or {}
    if dist.get("native"):
        habitat["native_regions"] = [{k: v for k, v in n.items() if k in ("region", "code", "source")} for n in dist["native"]]
        if not facts.get("native_range"):
            names = [n["region"] for n in dist["native"]]
            habitat["native_range"] = "Native regions (WCVP via GBIF): " + ", ".join(names[:14]) + (f" and {len(names) - 14} more" if len(names) > 14 else "")
    if dist.get("introduced"):
        habitat["introduced_regions"] = dist["introduced"]
    notes = [dist["note"]] if dist.get("note") else ["No GBIF distribution data was fetched."]
    if raw.get("wikidata_taxon_range"):
        notes.append("Wikidata taxon range (may include introduced areas; cross-check only): " + ", ".join(raw["wikidata_taxon_range"]))
    notes.append("GBIF occurrence latitude/elevation envelope (climate field) includes cultivated and introduced plants.")
    habitat["range_notes"] = notes
    if rng.get("lat"):
        habitat["climate"] = (f"GBIF records span latitude {rng['lat']['p5']:.0f} to {rng['lat']['p95']:.0f} deg"
                              + (f", elevation {rng['elevation_m']['p5']:.0f}-{rng['elevation_m']['p95']:.0f} m"
                                 if rng.get("elevation_m") else ""))

    fl, fr = facts.get("flowers"), facts.get("fruit")
    flowers = {"present": fl["present"] if fl else life != "alga"}
    if fl:
        for k in ("colors", "opens", "season", "pollination"):
            if fl.get(k):
                flowers[k] = fl[k]
    fam_default = DEFAULTS.get("fruit_by_family", {}).get(cls.get("family"))
    fruit = {"present": fr["present"] if fr else bool(fam_default)}
    if fam_default and not fr:
        fruit["type"] = fam_default["type"]
        fruit["description"] = "DEFAULT: " + fam_default["note"]
    if fr:
        for k in ("type", "description", "ripening", "edible"):
            if fr.get(k):
                fruit[k] = fr[k]

    biomes, why = pick_biomes(life or "perennial_herb", env or wp.get("extract", "")[:1500], lat)
    stages = [{"id": i, "name": n, "description": d, "texture": f"textures/block/{raw['id']}_{i}.png"} for i, n, d in lf["stages"]]
    if not fruit["present"]:
        stages = [s for s in stages if s["id"] != "fruiting"]
    if not flowers["present"]:
        stages = [s for s in stages if s["id"] not in ("flowering", "budding")]

    sources = [{"name": "GBIF" + (f" ({gb.get('status')}: {canonical})" if gb.get("found") else ""),
                "url": gb.get("url", ""), "id": str(gb.get("key", "")), "status": "checked"} if gb.get("found")
               else {"name": "GBIF", "status": "pending"}]
    sources.append({"name": f"Wikipedia: {wp['title']}", "url": wp["url"], "status": "checked"} if wp.get("found")
                   else {"name": "Wikipedia", "status": "pending"})
    sources.append({"name": "Wikidata", "url": wd["url"], "id": wd["id"], "status": "checked"} if wd.get("found")
                   else {"name": "Wikidata", "status": "pending"})
    sources.append({"name": "Plants of the World Online (Kew)", "url": "https://powo.science.kew.org", "status": "pending"})
    sources = [{k: v for k, v in s.items() if v} for s in sources]

    images = [{"url": im["page"], "license": im.get("license") or "unknown", "author": im.get("author") or "unknown",
               "shows": re.sub(r"^File:|\.\w+$", "", im["file"]).replace("_", " ")}
              for im in raw.get("commons_images", []) if im.get("page")][:5]
    man = PHOTOS / raw["id"] / "manifest.json"
    if man.exists():                                   # photos stage ran: richer list with local files and roles
        m = json.loads(man.read_text(encoding="utf-8"))
        images = [{"url": ph["page"], "license": ph["license"] or "unknown", "author": html.unescape(ph["author"] or "unknown"),
                   "shows": (re.sub(r"^File:|\.\w+$", "", ph["title"]) + (" - " + ph["description"][:100] if ph.get("description") else "")),
                   "role": ph["role"], "file": ph["file"], "width": ph["width"], "height": ph["height"], "hints": ph["hints"][:8]}
                  for ph in m["photos"]]

    draft = {
        "id": raw["id"],
        "status": {"data": "draft", "graphics": "pending", "implementation": "pending", "use": "pending"},
        "taxonomy": taxonomy,
        "names": {"scientific": canonical, "common": commons},
        "description": facts.get("description", {}).get("value") or first_paragraph(wp.get("extract", "")) or NOT_FOUND,
        "habitat": habitat,
        "growth_stages": stages,
        "reproduction": {"flowers": flowers, "fruit": fruit},
        "sources": sources,
        "implementation": {
            "type": lf["implementation_type"],
            "growth": {"summary": f"DEFAULT {life or 'unknown'} template: " + " -> ".join(s["name"] for s in stages) + ".",
                       "requirements": lf["requirements"]},
            "spawn": {"biomes": biomes, "feature": lf["feature"], "rarity": "uncommon",
                      "reason": f"DRAFT guess from {why}; review against real habitat."},
            "notes": "Auto-generated by pipeline/. Growth stages, spawn and rarity are defaults, not observations.",
        },
    }
    if commons != [canonical]:
        draft["names"]["in_game"] = commons[0].title()
    if images:
        draft["images"] = images
    if facts.get("uses_real"):
        draft["uses_real"] = [{k: u[k] for k in ("use", "note", "category", "part_used", "quote") if u.get(k)} for u in facts["uses_real"]]
    draft["size"] = build_size(facts, lf["habit"], wp)
    per = float(yaml.safe_load((ROOT / "config" / "scale.yaml").read_text())["cm_per_block"])
    if draft["size"]["source"] != "pending" and draft["size"]["height_cm"]["max"] > per:
        draft["segment_textures"] = [{"role": "lower", "texture": f"textures/block/{raw['id']}_lower.png",
                                      "note": "Lower block(s) under the stage texture when the plant is taller than one block."}]
    # Structured, quote-backed facts for the sprite artist and future mechanics. Never defaulted: absent means not in sources.
    srcname = f"Wikipedia: {wp['title']}" if wp.get("found") else "Wikipedia"
    for key in ("measurements", "appearance", "architecture", "phenology", "propagation"):
        if facts.get(key):
            draft[key] = [dict(item, source=srcname) for item in facts[key]]

    # Confidence: how many of the checkable facts were found in sources rather than defaulted.
    has_height = draft["size"]["source"] != "pending"
    checks = {"life_form": "life_form" in facts, "description": "description" in facts, "height": has_height,
              "native_range": "native_range" in facts or bool(habitat.get("native_regions")),
              "environment": "environment" in facts, "flowers": "flowers" in facts, "fruit": "fruit" in facts}
    found = sum(checks.values())
    draft["confidence"] = "high" if found >= 6 else "medium" if found >= 4 else "low"
    missing = [k for k, ok in checks.items() if not ok]
    if missing:
        draft["implementation"]["notes"] += " Not found in sources (blank or defaulted): " + ", ".join(missing) + "."
    if ext and not facts.get("architecture"):
        draft["implementation"]["notes"] += (" No branching/architecture facts in the text: use the branches and habit reference photos"
                                              " in `images` for tree branching and small-plant structure.")
    return draft


def assemble_all(write=False, force=False, only=None, everything=False):
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for raw in batch_raws(only, everything):
        ext_path = WORK / "extracted" / f"{raw['id']}.json"
        ext = json.loads(ext_path.read_text(encoding="utf-8")) if ext_path.exists() else None
        try:
            draft = build(raw, ext)
        except Exception as e:
            rows.append((raw["id"], "ERROR", str(e)))
            continue
        problems = [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in VALIDATOR.iter_errors(draft)]
        if problems:
            rows.append((raw["id"], "INVALID", "; ".join(problems)))
            continue
        text = yaml.safe_dump(draft, sort_keys=False, allow_unicode=True, width=100)
        (OUT / f"{raw['id']}.yaml").write_text(text, encoding="utf-8")
        dest = PLANTS / f"{raw['id']}.yaml"
        if write and dest.exists() and not force:
            rows.append((raw["id"], "kept", "plants/ file exists; use --force to overwrite"))
        elif write:
            dest.write_text(text, encoding="utf-8")
            rows.append((raw["id"], "written", f"confidence {draft['confidence']}"))
        else:
            rows.append((raw["id"], "draft", f"confidence {draft['confidence']}" + ("" if ext else "; no extraction (raw data only)")))
    for r in rows:
        print(f"  {r[1]:8} {r[0]:36} {r[2]}")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--all", action="store_true", help="every file in data/raw/, not just the resolved batch")
    a = ap.parse_args()
    rows = assemble_all(a.write, a.force, set(a.only) if a.only else None, a.all)
    return 1 if any(r[1] in ("ERROR", "INVALID") for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
