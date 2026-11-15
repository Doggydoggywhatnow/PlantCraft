# PlantCraft

A Minecraft: Java Edition mod (Fabric) that adds plants based on real botanical species, named by their scientific binomial. Every plant is described by one data file, and everything else (textures, world generation, game uses) is built from those files.

## Workflow

| Phase | What happens | Output |
|---|---|---|
| **Ideas** | Choose species, define the file format, build the fetch tooling. | `schema/`, `tools/`, `docs/` |
| **Data** | Reference data is fetched from Wikipedia, Wikidata, GBIF and Wikimedia Commons into `data/raw/`; each plant file in `plants/` is written from it, with sources cited. Includes the draft `implementation` block (how it grows, where it spawns). | `plants/*.yaml` |
| **Graphics** | Textures for every growth stage, built from each file's `growth_stages`. | `textures/` |
| **Implementation** | Plants are registered and world generation spawns them in matching biomes. | mod code, generated JSON |
| **Use** | Gameplay uses (recipes, effects, brewing) are added for species that have real-world uses, recorded in `game_uses`. | `game_uses` + recipes |

Each plant's `status` block tracks which phases are done, so any phase can find its own work.

## Layout

```
plants/              one YAML file per species (schema-validated)
schema/plant.schema.json
tools/fetch.py       fetch raw reference data for species into data/raw/
tools/validate.py    validate plants/*.yaml against the schema
tools/make_textures.py  draw a 16x16 texture for every growth stage (graphics phase)
textures/            generated block and item textures
docs/preview/        contact sheets of every texture (all.png)
tools/species.txt    species list the fetch tool reads
data/raw/            cached raw API responses (inputs to the data phase)
docs/                design notes (flower and fruit system, ...)
```

## Commands

```bash
python3 tools/fetch.py --list tools/species.txt   # fetch / refresh raw data (cached; --force to refetch)
python3 tools/validate.py                         # validate plant files
python3 tools/make_textures.py                    # redraw textures and preview sheets
```

## Data and licensing

- Facts come from Wikipedia, Wikidata, GBIF and Wikimedia Commons, and every plant file lists its sources.
- Reference photos are only reference. Mod textures are original pixel art. Each recorded photo carries its licence and author.
- Entries marked `confidence: low` come from thin sources and are not yet verified against a primary source.
