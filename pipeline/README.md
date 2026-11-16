# Species pipeline

Gathers the base information for hundreds of species at once and writes schema-valid draft plant
files. It builds on `tools/fetch.py` (kept as is) and adds name resolution, concurrency, resumability,
a range envelope from GBIF, grounded LLM extraction, and a coverage report.

```
names ─► 1 RESOLVE ─► 2 FETCH ─► 2b PHOTOS ─► 3 EXTRACT ─► 4 ASSEMBLE ─► 5 REPORT
(lists/)  resolve.py  fetch.py   photos.py    extract.py   assemble.py   report.py
          GBIF match  APIs +     licence-     quote-       schema-valid  coverage
          accepted    native     filtered     checked      drafts        table
          names only  range     photos by    facts
                                 role
```

## Quick start

```bash
pip install pyyaml jsonschema            # required (photos need no extra packages)
pip install anthropic                    # only for the extract stage
export ANTHROPIC_API_KEY=...             # only for the extract stage

python3 pipeline/run.py pipeline/lists/example.txt
```

No API key? Run the free stages, then either export prompts or skip extraction:

```bash
python3 pipeline/run.py my.txt --stages resolve fetch      # no key needed
python3 pipeline/run.py my.txt --stages extract --export-prompts   # one ready-made prompt per species
python3 pipeline/extract.py --import-dir answers/          # verify + import answers made elsewhere
python3 pipeline/run.py my.txt --stages assemble report    # drafts work without extraction too (low confidence)
```

Input list lines: `Quercus robur`, `genus:Datura`, `family:Lamiaceae` (use `--limit`). Synonyms are mapped to
the accepted name (`Amygdalus persica` becomes `Prunus persica`); typos and fuzzy matches go to a review
list instead of being fetched. Every stage caches to disk, so re-running the same command resumes.

## What each stage does

| Stage | Reads | Writes | Notes |
|---|---|---|---|
| resolve | names list | `data/pipeline/resolved.jsonl` | GBIF backbone match; flags fuzzy, non-species, duplicate inputs |
| fetch | resolved.jsonl | `data/raw/<id>.json` | Wikipedia, Wikidata, GBIF, Commons (parsers reused from `tools/fetch.py`), plus `gbif_range` (latitude/elevation envelope, includes cultivated plants) and **`distribution`: native and introduced regions** from the World Checklist of Vascular Plants via GBIF (TDWG level-3 regions), plus Wikidata's taxon range as a cross-check |
| photos | resolved.jsonl, raw | `data/photos/<id>/*.jpg`, `manifest.json` | Reference photos from Wikimedia Commons: flower, fruit, seed, leaf, bark, branches, illustration, habit. Only CC0, public domain, CC BY and CC BY-SA; the best few per role, different authors first. Authors and licences are in `manifest.json`; roles in `must_have` (flower, fruit) are reported when missing. Images are git-ignored, manifests are tracked |
| extract | raw files | `data/pipeline/extracted/<id>.json` | Model must quote the source for every fact; quotes are verified verbatim (numeric facts must quote a number), facts that fail are dropped |
| assemble | raw + extracted | `data/pipeline/drafts/<id>.yaml` | Validates against `schema/plant.schema.json`. `--write` copies to `plants/` and never overwrites an existing file without `--force` |
| report | everything | `data/pipeline/coverage.md/.csv` | Per-species field coverage, dropped fields, names needing a human, failures |

## What a draft contains

Besides the base sections (taxonomy, names, description, habitat, reproduction, uses, sources, images), a draft has
these quote-backed sections. Each item names its `source` and a verbatim `quote`; an absent section means the text did
not say, never a guess.

| Section | What it holds | What it enables |
|---|---|---|
| `size` | height, spread, trunk diameter, built from `measurements` (a `pending` placeholder when the text has no height) | multi-block growth, per-plant size variation |
| `measurements` | every number in the text with its unit: height, spread, trunk/crown/bole/branch sizes, leaf, flower, fruit and seed sizes, lifespan, age to flower, time to harvest | sizing branches and organs, growth timing |
| `appearance` | colours, shapes, textures of each part, by growth stage | the sprite artist (human or AI) |
| `architecture` | branching pattern, branch angle or droop, crown shape, trunk and twig form, leaf and flower arrangement, tillering, climbing, roots, buttresses | realistic tree branching, realistic small-plant structure |
| `phenology` | when flowering, fruiting, ripening, seed release, leaf fall happen | flowers and fruit, seasons |
| `propagation` | pollination, self-fertility, dispersal, germination, dormancy, cuttings, regeneration, maturity age, lifespan | reproduction mechanics (saplings only from fertilised trees) |
| `uses_real` | human uses with `category` (food, medicine, material, fuel, ornamental, cultural, ecological, forage, toxic, research), `part_used` and a quote | the use phase |
| `habitat.native_regions` | where it grows natively (TDWG regions), and `introduced_regions` | world generation, biome choice |
| `images` | downloaded photos with `role`, local `file`, author and licence | reference for sprites; show flowering and fruiting |

Branching detail is often thin in Wikipedia text. When no `architecture` facts are found, the draft says so and points
to the `branches`, `habit` and `bark` photos instead of inventing geometry.

Where each field in a draft comes from:

- **From sources:** taxonomy, names, sources, images (GBIF/Wikidata/Wikipedia/Commons); native and introduced regions
  (WCVP via GBIF); description, habitat, size, measurements, appearance, architecture, phenology, propagation, flowers,
  fruit, uses (extracted, quote-verified).
- **From `defaults.yaml` (game design, flagged DEFAULT/DRAFT in the file):** growth stages, implementation type, spawn
  biomes (habitat keywords, else GBIF median latitude), rarity.
- **Missing:** written as `not found in fetched sources` and listed in `implementation.notes`; never guessed.

Drafts are always `status.data: draft`. Real verification (and the textures, tuning and uses that follow) stays a
human step, same as the hand-made files.

## Files

- `config.yaml`: worker count, per-host requests/second, model, paths.
- `defaults.yaml`: life-form templates for growth stages, biome guesses. Edit this to change every draft at once, then
  re-run `--stages assemble report`.
- `prompts/extract.md`, `extract.schema.json`: the extraction prompt and the shape of its answer.
- `lists/example.txt`: sample input. `tests/`: offline tests (`python3 -m unittest discover -s pipeline/tests`).

## Known limits and next steps

- Wikipedia is the only text source for extraction. Species without an article get raw data only (see the report).
  Adding POWO, PFAF or USDA PLANTS as extra text sources means extending `fetch.py` and the prompt; their licences
  and API terms need checking first.
- `gbif_range` is a latitude/elevation envelope, not a climate model. Joining it to WorldClim or Koppen rasters would
  give temperature and rainfall ranges for world generation.
- Wikipedia calls are the slow part (tens of seconds each through some networks); concurrency hides it. Expect on
  the order of minutes per hundred species, not seconds.
- Photos are Commons only (known licences). Roles come from titles, descriptions and category names, so a few photos
  can land in the wrong role; skim the contact sheet or manifest. Museum herbarium sheets are excluded.
- Native range comes from WCVP via GBIF. A species with no WCVP record in GBIF (some synonyms) gets no `native_regions`;
  the draft says so and falls back to the Wikipedia statement and Wikidata's taxon range.
- Download size: about 20 photos per species at 1024 px is a few MB. Set `photos.enabled: false` or lower `per_role` to trim.

## Example run: 12 tall grasses

`pipeline/lists/tall_grasses.txt` (hand-picked lush, somewhat tall grasses). Wall-clock times on this network:

| Stage | Time | Notes |
|---|---|---|
| resolve | 1 s | flagged `Pennisetum alopecuroides` (genus moved to *Cenchrus*) and `Andropogon gerardii` (GBIF spells it *gerardi*) for review |
| fetch | 116 s for 11 species | Wikipedia, Wikidata, GBIF, GBIF range and native regions, run concurrently |
| photos | 395 s for 11 species | about 36 s per species; limited by Commons rate limits |
| the review-list species (Andropogon) | 1 s + 9 s + 74 s | resolved with `--accept-fuzzy`, then fetched and photographed on its own |
| extract (verify only) | 0.1 s | the extraction itself was written by hand (see below), so its model time is not measured |
| assemble | 0.4 s | 12 schema-valid drafts |
| report | 0.5 s | |

About 10 minutes of network time for 12 species, roughly 50 s per species, almost all of it Wikipedia and Commons
rate limiting. It should scale about linearly, so a few hundred species is a few hours; photos dominate.

`pipeline/examples/tall_grasses_answers/` holds the extraction answers used in this run. They were written by hand to
match what the extraction model returns (no API key was available), with every quote asserted against the source
text. Import them with `python3 pipeline/extract.py --import-dir pipeline/examples/tall_grasses_answers`.

Lessons from the run:
- `resolve --force` rewrites the whole resolved list to the names given; re-resolve the full list afterwards.
- Number words ("three years") now count as numbers when quote-checking measurements.
- Poaceae get a flagged family default of a grain fruit, so every grass keeps a fruiting stage.
- Source text is uneven: *Cortaderia selloana*'s article has almost no morphology, so its draft is `low` confidence with a
  `pending` size. The sprite step falls back to photo colours and documented defaults for such species.
