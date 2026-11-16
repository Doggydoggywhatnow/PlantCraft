# AGENTS.md: where to pick this project up

PlantCraft is a Minecraft: Java mod (Fabric, **Minecraft 26.3, Java 25**) that adds real plant species named by their
scientific names. Every plant is described by one data file in `plants/`; the sprites, the sampler and the mod are all
generated from those files. Work happens on branch `claude/eager-newton-bcwkw1` (the repo is
`Doggydoggywhatnow/PlantCraft`; `main` is still empty). Read `README.md` first, then this file.

## Repo map

| Path | What it is |
|---|---|
| `plants/*.yaml` | One file per species, validated by `schema/plant.schema.json` (`python3 tools/validate.py`). 33 species. |
| `pipeline/` | Species pipeline: resolve, fetch, photos, extract, assemble, report. See `pipeline/README.md`. |
| `tools/` | `make_textures.py` (sprites), `make_index.py` (previews), `sample_sizes.py` (per-plant size sampler), `derive_structure.py`, `make_mod_assets.py` (mod assets from plant files). |
| `config/` | `scale.yaml` (1 block = 100 cm), `variation.yaml` (size-variation settings). |
| `textures/`, `docs/preview/` | Generated sprites and contact sheets (`docs/preview/all.png`, `grasses.png`, `INDEX.md`). |
| `mod/` | Fabric mod project. Java in `mod/src/main/java/com/plantcraft/`. Built jar copy in `dist/`. |
| `data/raw/`, `data/photos/*/manifest.json` | Fetched source data and photo manifests (photo images are git-ignored). |
| `docs/` | Design notes: `plant-structure.md`, `flower-fruit-system.md`, `botanical-mechanics.md` (future scope). |

## Commands

```bash
python3 tools/validate.py                      # validate plants/*.yaml
python3 tools/make_textures.py                 # redraw every sprite + docs/preview sheets
python3 tools/make_index.py                    # docs/preview/INDEX.md
python3 tools/make_mod_assets.py               # regenerate mod resources from plants/
python3 -m unittest discover -s pipeline/tests # 14 offline pipeline tests
cd mod && JAVA_HOME=/usr/lib/jvm/java-25-openjdk-amd64 ./gradlew build --no-daemon   # jar in mod/build/libs/
python3 pipeline/run.py pipeline/lists/tall_grasses.txt                              # full pipeline run
```

The Gradle wrapper is 9.8.2; Java 25 must be installed (`apt-get install openjdk-25-jdk-headless`). Use `python3 -I`
for the repo's tools when you want isolated mode (the tools do not need the script directory on the path).

## State of the work

**Done and committed (last good state `a35f1adf`, jar in `dist/` is from there):**
- 33 species with sourced data, 16x16 sprites (32x32 for the pipeline grasses), plantable and growable in the mod;
  trees grow from saplings; bone meal works; seeds and saplings are in a creative tab.
- Pipeline with photos (Commons, licence-filtered), native range (WCVP via GBIF), quote-verified extraction facts.
  Ran on 12 tall grasses (timings in `pipeline/README.md`).

**Uncommitted at the time of writing, now committed on the branch but NOT yet working:**
1. **Multi-block growth for tall plants (BROKEN, see below).** `make_mod_assets.py` emits a `tall` entry (sourced height
   range) and a `<id>_stem` block for herbs taller than 1 block; `StemBlock.java` is new; `PlantBlock.java` moves its top
   block up one and leaves a stem (`growTaller`) until `TreeGen.blocksTall(...)`; `PlantCraft.java` registers the stems.
2. **32x32 grass sprites** (`grass32_stage`, `g_head`, `g_cane` in `tools/make_textures.py`): working and reviewed in
   `docs/preview/grasses.png`. `render()` and the preview/index tools now accept any texture size.
3. The dist jar was deliberately **not** updated with item 1.

## Known bug to fix first: tall plants vanish

Reproduction (dedicated server, `mod/run`, random tick speed 4000): planting a tall plant
(`plantcraft:arundo_donax[age=1]` on grass) leaves **air at y+0..y+3 within 5 seconds**; no stem ever appears. A short
plant (`cenchrus_alopecuroides`, 1 block) in the same test grows normally. No exception is logged.

Not yet established (a manual-column test was interrupted): does a hand-built column
`arundo_donax_stem` at y with `arundo_donax[age=1]` above it survive with random ticks off, and with them on?

Leads to check, in order:
1. `VegetationBlock.canSurvive` / `updateShape` in 26.3: confirm they call `mayPlaceOn(belowState, level, belowPos)`.
   `PlantBlock.mayPlaceOn` and `StemBlock.mayPlaceOn` use `below.is(stem)` / `below.is(this)`.
2. `growTaller` sets the old position to the stem and the position above to the plant with flag `2` (no neighbour
   updates). Try flag `3`, or place the plant first and then the stem, and check whether a pop happens.
3. Add temporary logging in `growTaller` and `randomTick`; confirm it is reached and what `TreeGen.blocksTall` returns
   (`hLo == hHi` plants must give the same count every time; `ceil(cm / 100)`).
4. Whether `isRandomlyTicking` returning true for max-age tall plants causes the removal (it should not).

When it works: test as in `docs/plant-structure.md` terms (a 6 m giant reed should stack ~6 blocks, a plant with range
80-200 cm 1-2 blocks), rebuild, copy the jar to `dist/`, and commit.

## Other open items

- **Seeds look too alike.** All grass seed sprites use one grain template; only colour changes. Data exists for some
  (`measurements: seed_length`, `appearance` part `seed`, `propagation` dispersal, e.g. Phragmites seeds carry long silky
  hairs, Panicum seeds 3-6 mm pink to golden brown). Make the grain shape and size follow the data (hairy tuft, awned,
  flat, round) and fall back to photos from the `seed` role. Datura seeds share one template too.
- **Extraction was never run with a real model** (no `ANTHROPIC_API_KEY` here). The 12 grasses use hand-written answers in
  `pipeline/examples/tall_grasses_answers/`. Run `pipeline/run.py ... --stages extract assemble report --force` with a key,
  then compare drafts to the hand-made species and to those answers.
- **Photo roles are heuristic** (a monitor-lizard photo landed in a eucalyptus `habit` set). Branch geometry is rarely in the
  text; `architecture` stays thin, so tree branching still relies on photos and design choices (`tree_structure`).
- **Peach and eucalyptus** branch designs exist as data and textures but the mod still builds a trunk and round crown.
- **Chara braunii** is item-only (no underwater planting). **Ipomoea** needs a climbing-support mechanic.
- **Botanical mechanics** (saplings only from fertilised trees, pollination, propagation) are future scope: see
  `docs/botanical-mechanics.md`. Do not start them without the owner's go-ahead.
- Sizes: individual plants vary within sourced ranges (`tools/sample_sizes.py`, consensus mode). Three numbers in
  `config/variation.yaml` are design choices, not data.

## Conventions and gotchas

- **Facts need sources.** Every sourced field carries a quote and a source; unknowns are `pending`/"not found", never
  guessed. Keep design choices separate from data (`tree_structure.design`, config files say which numbers are design).
- **No implementation of new species behaviour without being asked.** The owner steers scope: data and graphics first.
- Commit and push only to `claude/eager-newton-bcwkw1`. Use `git add -A -- . ':!data/photos/*/*.jpg'` (photo images are
  ignored). End commit messages with the `Co-Authored-By` and `Claude-Session` lines used in the history.
- **Wikimedia throttles hard.** `pipeline/common.py` rate-limits per host and caps `Retry-After`; do not run two photo jobs at
  once. Photos for 12 species take about 6-7 minutes.
- `resolve --force` rewrites the resolved list to only the names given; re-resolve the full list afterwards.
- Do not use `rm -rf` in commands: the environment's safety check blocks it. Use fresh file names instead.
- The environment sometimes returns "classifier gave no verdict" for Bash; retry once, or use Read/Glob for read-only steps.
- Dedicated-server tests: create `mod/run/eula.txt` (`eula=true`) and `server.properties`
  (`online-mode=false`, a fresh `level-name` each run); feed commands through a FIFO into `./gradlew runServer`. Auth-service
  errors in the log are harmless (no internet to Mojang's auth servers).
- A line-drawing helper bug once looped forever on float coordinates and exhausted memory; `line()` now rounds its inputs.
