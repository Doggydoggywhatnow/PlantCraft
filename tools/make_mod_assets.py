#!/usr/bin/env python3
"""Generate the mod's item assets from plants/*.yaml: seeds and saplings for the creative menu.

    python3 tools/make_mod_assets.py

Writes into mod/src/main/resources: plantcraft_items.json (read by the mod at startup), item model definitions,
item models, lang file and item textures (copied from the graphics phase). Every plant gets a seed item; trees
(plants with a `sapling` growth stage) also get a sapling item.
"""
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


def main():
    for sub in ("assets/%s/items" % NS, "assets/%s/models/item" % NS, "assets/%s/textures/item" % NS, "assets/%s/lang" % NS):
        shutil.rmtree(RES / sub, ignore_errors=True)
        (RES / sub).mkdir(parents=True)
    items, lang = [], {"itemGroup.%s" % NS: "PlantCraft"}
    for f in sorted((ROOT / "plants").glob("*.yaml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        pid, name, latin = d["id"], d["names"]["in_game"], d["names"]["scientific"]
        stages = {s["id"]: s["texture"] for s in d["growth_stages"]}
        seed_tex = SEED_TEXTURE_OVERRIDE.get(pid) or stages.get("seed") or stages.get("spore")
        entries = [(f"{pid}_seeds", SEED_NAMES.get(pid, f"{name} Seeds"), seed_tex)]
        if "sapling" in stages:
            entries.append((f"{pid}_sapling", f"{name} Sapling", stages["sapling"]))
        for iid, label, tex in entries:
            shutil.copy(ROOT / tex, RES / f"assets/{NS}/textures/item/{iid}.png")
            (RES / f"assets/{NS}/items/{iid}.json").write_text(json.dumps({"model": {"type": "minecraft:model", "model": f"{NS}:item/{iid}"}}, indent=1))
            (RES / f"assets/{NS}/models/item/{iid}.json").write_text(json.dumps({"parent": "minecraft:item/generated", "textures": {"layer0": f"{NS}:item/{iid}"}}, indent=1))
            lang[f"item.{NS}.{iid}"] = label
            items.append({"id": iid, "name": label, "latin": latin})
    (RES / f"assets/{NS}/lang/en_us.json").write_text(json.dumps(lang, indent=1, ensure_ascii=False))
    (RES / "plantcraft_items.json").write_text(json.dumps(items, indent=1, ensure_ascii=False))
    print(f"{len(items)} items")


if __name__ == "__main__":
    main()
