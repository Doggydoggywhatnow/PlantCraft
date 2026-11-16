# Species pipeline

Gathers the base information for hundreds of species at once and writes schema-valid draft plant
files. It builds on `tools/fetch.py` (kept as is) and adds name resolution, concurrency, resumability,
a range envelope from GBIF, grounded LLM extraction, and a coverage report.

```
names list ──► 1 RESOLVE ──► 2 FETCH ──► 3 EXTRACT ──► 4 ASSEMBLE ──► 5 REPORT
 (lists/)      resolve.py    fetch.py    extract.py    assemble.py    report.py
               GBIF match    8 workers   quote-checked  schema-valid   coverage.md
               accepted      per-host    facts from     drafts in      one table to
               names only    rate limit  Wikipedia      data/pipeline  review
```

## Quick start

```bash
pip install pyyaml jsonschema            # required
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
| fetch | resolved.jsonl | `data/raw/<id>.json` | Wikipedia, Wikidata, GBIF, Commons (parsers reused from `tools/fetch.py`), plus `gbif_range`: country list, latitude and elevation envelope sampled across the top countries |
| extract | raw files | `data/pipeline/extracted/<id>.json` | Model must quote the source for every field; quotes are verified verbatim, fields that fail are dropped |
| assemble | raw + extracted | `data/pipeline/drafts/<id>.yaml` | Validates against `schema/plant.schema.json`. `--write` copies to `plants/` and never overwrites an existing file without `--force` |
| report | everything | `data/pipeline/coverage.md/.csv` | Per-species field coverage, dropped fields, names needing a human, failures |

Where each field in a draft comes from:

- **From sources:** taxonomy, names, sources, images (GBIF/Wikidata/Wikipedia/Commons); description, habitat, size,
  flowers, fruit, uses (extracted, quote-verified).
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
- Images are listed with licence and author only; nothing is downloaded.
