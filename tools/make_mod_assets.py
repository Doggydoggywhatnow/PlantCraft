#!/usr/bin/env python3
"""Generate the mod's assets and data from plants/*.yaml.

    python3 tools/make_mod_assets.py

Writes into mod/src/main/resources: plantcraft_plants.json (read by the mod at startup), blockstates, block and item
models, item model definitions, loot tables, lang, and textures (copied from the graphics phase).

  * herbs (no `sapling` stage): a growable plant block with one model per growth stage after the seed, plus a seed item
  * trees (has a `sapling` stage): a sapling block that grows into a trunk and crown, with log and leaves blocks;
    tree height and width come from the plants' sourced size ranges (tools/sample_sizes.py)
  * chara_braunii: item only (aquatic planting is not built yet)
"""
import importlib.util
import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "mod" / "src" / "main" / "resources"
NS = "plantcraft"
SEED_NAMES = {"oryza_sativa": "Rice Grain", "chara_braunii": "Braun's Stonewort Oospores", "prunus_persica": "Peach Pit",
              "olea_europaea_europaea": "Olive Stone"}
SEED_TEXTURE_OVERRIDE = {"prunus_persica": "textures/item/peach_pit.png"}   # the peach has no seed growth stage
LEAF_STAGE = {"prunus_persica": "young_tree", "eucalyptus_deglupta": "mature_tree", "olea_europaea_europaea": "mature_tree"}
ITEM_ONLY = {"chara_braunii"}


def sizes():
    spec = importlib.util.spec_from_file_location("sample_sizes", ROOT / "tools" / "sample_sizes.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False))


def copy_tex(src, name, kind):
    dst = RES / f"assets/{NS}/textures/{kind}/{name}.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / src, dst)


def item_def(iid, model):
    write(RES / f"assets/{NS}/items/{iid}.json", {"model": {"type": "minecraft:model", "model": model}})


def flat_item(iid, tex):
    copy_tex(tex, iid, "item")
    item_def(iid, f"{NS}:item/{iid}")
    write(RES / f"assets/{NS}/models/item/{iid}.json", {"parent": "minecraft:item/generated", "textures": {"layer0": f"{NS}:item/{iid}"}})


def loot(bid, entries, extra=None):
    pools = [{"rolls": 1, "entries": [{"type": "minecraft:item", "name": f"{NS}:{e}"} for e in entries]}]
    if extra:
        pools.append(extra)
    write(RES / f"data/{NS}/loot_table/blocks/{bid}.json", {"type": "minecraft:block", "pools": pools})


def main():
    ss = sizes()
    cfg, _ = ss.load_cfg()
    for sub in ("assets", "data"):
        shutil.rmtree(RES / sub, ignore_errors=True)
    plants, lang = [], {"itemGroup.%s" % NS: "PlantCraft"}
    for f in sorted((ROOT / "plants").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        pid, name, latin = d["id"], d["names"]["in_game"], d["names"]["scientific"]
        stages = {s["id"]: s["texture"] for s in d["growth_stages"]}
        order = [s["id"] for s in d["growth_stages"]]
        seed_tex = SEED_TEXTURE_OVERRIDE.get(pid) or stages.get("seed") or stages.get("spore")
        seed_id, seed_name = f"{pid}_seeds", SEED_NAMES.get(pid, f"{name} Seeds")
        flat_item(seed_id, seed_tex)
        lang[f"item.{NS}.{seed_id}"] = seed_name
        entry = {"id": pid, "name": name, "latin": latin, "seed_id": seed_id}
        if pid in ITEM_ONLY:
            entry["kind"] = "item"
        elif "sapling" in stages:                                         # ---- tree
            entry["kind"] = "tree"
            sap_id = f"{pid}_sapling"
            flat_item(sap_id, stages["sapling"])
            lang[f"item.{NS}.{sap_id}"] = f"{name} Sapling"
            lang[f"block.{NS}.{sap_id}"] = f"{name} Sapling"
            write(RES / f"assets/{NS}/blockstates/{sap_id}.json", {"variants": {"": {"model": f"{NS}:block/{sap_id}"}}})
            write(RES / f"assets/{NS}/models/block/{sap_id}.json", {"parent": "minecraft:block/cross", "textures": {"cross": f"{NS}:block/{sap_id}"}})
            copy_tex(stages["sapling"], sap_id, "block")
            loot(sap_id, [sap_id])
            tex_by_role = {s["role"]: s["texture"] for s in d["segment_textures"]}
            log_id, leaves_id = f"{pid}_log", f"{pid}_leaves"
            copy_tex(tex_by_role["trunk_side"], f"{log_id}_side", "block")
            copy_tex(tex_by_role["trunk_top"], f"{log_id}_top", "block")
            copy_tex(stages[LEAF_STAGE[pid]], leaves_id, "block")
            m = f"{NS}:block/{log_id}"
            write(RES / f"assets/{NS}/blockstates/{log_id}.json", {"variants": {
                "axis=y": {"model": m}, "axis=z": {"model": m, "x": 90}, "axis=x": {"model": m, "x": 90, "y": 90}}})
            write(RES / f"assets/{NS}/models/block/{log_id}.json", {"parent": "minecraft:block/cube_column",
                  "textures": {"end": f"{NS}:block/{log_id}_top", "side": f"{NS}:block/{log_id}_side"}})
            write(RES / f"assets/{NS}/blockstates/{leaves_id}.json", {"variants": {"": {"model": f"{NS}:block/{leaves_id}"}}})
            write(RES / f"assets/{NS}/models/block/{leaves_id}.json", {"parent": "minecraft:block/cube_all", "textures": {"all": f"{NS}:block/{leaves_id}"}})
            item_def(log_id, f"{NS}:block/{log_id}")
            item_def(leaves_id, f"{NS}:block/{leaves_id}")
            for bid, label in ((log_id, f"{name} Log"), (leaves_id, f"{name} Leaves")):
                lang[f"block.{NS}.{bid}"] = label
                lang[f"item.{NS}.{bid}"] = label
            loot(log_id, [log_id])
            # leaves: 5% chance of the sapling
            write(RES / f"data/{NS}/loot_table/blocks/{leaves_id}.json", {"type": "minecraft:block", "pools": [{
                "rolls": 1, "conditions": [{"condition": "minecraft:random_chance", "chance": 0.05}],
                "entries": [{"type": "minecraft:item", "name": f"{NS}:{sap_id}"}]}]})
            hs = d["size"].get("height_sources") or [dict(d["size"]["height_cm"])]
            lo, hi, _ = ss.typical_range(hs, cfg["range_mode"])
            entry["tree"] = {"sapling_id": sap_id, "log_id": log_id, "leaves_id": leaves_id, "height_lo": lo, "height_hi": hi,
                             "tail_hi": hs[0]["max"] if "common_max" in hs[0] else 0, "width_lo": 0, "width_hi": 0}
            if d["size"].get("spread_sources"):
                wlo, whi, _ = ss.typical_range(d["size"]["spread_sources"], cfg["range_mode"])
                entry["tree"].update(width_lo=wlo, width_hi=whi)
        else:                                                              # ---- herb
            entry["kind"] = "herb"
            grow = [s for s in order if s != "seed"]
            entry["max_age"] = len(grow) - 1
            variants = {}
            for age in range(6):
                sid = grow[min(age, len(grow) - 1)]
                bn = f"{pid}_{sid}"
                copy_tex(stages[sid], bn, "block")
                write(RES / f"assets/{NS}/models/block/{bn}.json", {"parent": "minecraft:block/cross", "textures": {"cross": f"{NS}:block/{bn}"}})
                variants[f"age={age}"] = {"model": f"{NS}:block/{bn}"}
            write(RES / f"assets/{NS}/blockstates/{pid}.json", {"variants": variants})
            lang[f"block.{NS}.{pid}"] = name
            ripe = f"{max(0, len(grow) - 1)}"
            loot(pid, [seed_id], {"rolls": 1, "entries": [{"type": "minecraft:item", "name": f"{NS}:{seed_id}"}],
                                   "conditions": [{"condition": "minecraft:block_state_property", "block": f"{NS}:{pid}", "properties": {"age": ripe}}]})
        plants.append(entry)
    write(RES / f"assets/{NS}/lang/en_us.json", lang)
    write(RES / "plantcraft_plants.json", plants)
    old = RES / "plantcraft_items.json"
    old.unlink(missing_ok=True)
    kinds = {k: sum(1 for p in plants if p["kind"] == k) for k in ("herb", "tree", "item")}
    print(f"{len(plants)} plants: {kinds}")


if __name__ == "__main__":
    main()
