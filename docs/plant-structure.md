# Plant size and multi-block structure

**Scale: 1 block = 1 m** (`config/scale.yaml`). Every plant's real size is stored in its file under `size`
(centimetres, with the source wording). Block counts are *derived*, never typed by hand:

```
python3 tools/derive_structure.py        # table of blocks tall / wide for every species
```

blocks tall = ceil(height / cm_per_block), at least 1.

## Growth

1. **Seed** is planted and becomes a **seedling** (1 block).
2. The plant grows upward one block at a time until it reaches its own final height. Each plant draws that
   final height from the real range in its `size` data (for example 60-150 cm for *Datura stramonium*),
   seeded from its position so it is stable.
3. Flowers, fruit and capsules appear on the **top** block only. Blocks beneath are leafy stem.
4. A plant whose final height is 1 block just uses the single-block stage textures.

## Textures

| Case | Blocks |
|---|---|
| 1-block plant, or the top of a taller one | the stage textures (`growth_stages[].texture`) |
| Datura taller than 1 block | `segment_textures` role `lower` under the stage texture |
| Peach tree | `trunk_side` / `trunk_top` for the trunk, leaf stage textures for the crown |
| Morning glory | `climbing` texture repeated up the support; `flowering` / `seed_pod` on any segment |

Previews of 2-block stacks are in `docs/preview/INDEX.md`.

## At 1 m per block

| Plant | Real height | Blocks tall |
|---|---|---|
| *Datura discolor* | up to 140 cm | 2 |
| *Datura metel* | up to 180 cm | 2 |
| *Datura stramonium*, *D. innoxia* | 60-150 cm | 1-2 |
| *Datura wrightii* | 30-150 cm, up to 150 cm wide | 1-2 (+ sideways spread, not built yet) |
| *Ipomoea tricolor* | 2-4 m | 2-4 |
| *Prunus persica* | 3-10 m, crown 3-4 m wide | 3-10 |
| *Oryza sativa* (rice) | 80-120 cm, 30 cm wide | 1-2 (1 wide) |
| *Salvia rosmarinus* (rosemary) | 120-180 cm (upright forms), 91-122 cm wide | 2 (1-2 wide) |
| *Eucalyptus deglupta* (rainbow eucalyptus) | 60-78 m, trunk up to 240 cm across | 60-78 (trunk up to 3 wide) |
| other Datura | under 1 m, or no data | 1 |

## Individual variation

Every plant is its own size, drawn from **published** ranges only. `tools/sample_sizes.py` is the reference
implementation the game will follow:

- Each plant file lists every height and width range found (`size.height_sources`, `size.spread_sources`), with URL
  and quote. A source that says only "up to X" is read as 0..X.
- **Consensus mode (default):** an individual is drawn from the range all sources agree on. If the sources do not
  overlap (the peach crown: 3-4 m in Wikipedia, 4.6-7.6 m in NC State), the primary botanical description is used
  and the disagreement is reported. If no source gives a minimum, there is nothing to vary within and the plant is
  fixed at the stated maximum until a minimum is found (*D. discolor* 140 cm, *D. quercifolia* 90 cm).
  **Envelope mode:** lowest published minimum to highest published maximum. Switch in `config/variation.yaml`.
- A plant's **vigour** is a number in 0..1 from a hash of (world seed, x, z, species), so a plant keeps its size
  forever and the same seed gives the same world. Width uses the same vigour, partly correlated with height.
- If the primary source says large sizes are rare (the peach: "more typically 3 m", "rarely up to 10 m"), most
  trees land in the common range and about 3% are giants.
- Species with no size data are not varied: they stay 1 block until a source is found.

The correlation (0.7) and giant rate (3%) are **design choices, not botanical data**.

Possible next step: let nearby water and light shift vigour. Wikipedia's Datura article says the same species is a
flowering bush about 80 cm tall in a damp, half-shady spot but a thin plant of 13 cm or so in a very dry one.

## Branches

Every plant is drawn from its branching skeleton, with leaves, flowers and fruit hanging off it:

| Plant | Branching shown (source) |
|---|---|
| Datura | Stem forks repeatedly, a leaf at each fork, one erect flower on each tip (Wikipedia: *D. stramonium*) |
| *Salvia rosmarinus* | Several woody stems with needle leaves along them; flowers in groups of 2-3 down the stems |
| *Ipomoea tricolor* | Twining main stems with side shoots carrying each leaf |
| *Chara braunii* | Whorls of 6-10 branchlets (Wikipedia) |
| *Oryza sativa* | Several jointed tillers, a long slender leaf at each node; panicle is a branched inflorescence with up to 350 spikelets (Wikipedia: Rice) |
| *Prunus persica* | Smooth red twigs, alternate leaves, flowers before leaves; branches droop with age |
| *Eucalyptus deglupta* | Square-sectioned branchlets with opposite leaf pairs; buds in groups of seven at the axils |

Trees are built from a trunk, limbs (`branch_side`) and twig foliage tiles, so the branches show through the
leaves. `tree_structure` in each tree's file separates quoted facts from design choices.

The rainbow eucalyptus is **not capped**: typical trees are 60-78 m, so 60-78 blocks, with a trunk up to 3 blocks
across and a buttress flare (up to 4 m) at the base.

## Width

`size.spread_sources` keeps every width figure found, with its source URL and wording, because sources disagree
(wild plants vs garden plants, different authors). `size.spread_cm` is the envelope: lowest minimum to highest
maximum. Blocks wide uses the same rule as height: ceil(width / cm_per_block).

| Plant | Width found | Sources | Blocks wide at 1 m |
|---|---|---|---|
| *Datura stramonium* | 30-122 cm | PFAF (1 m), NC State (1-4 ft) | 1-2 |
| *Datura wrightii* | 30-183 cm | Wikipedia (up to 1.5 m), NC State (3-6 ft) | 1-2 |
| *Datura innoxia* | 91-183 cm | NC State (3-6 ft) | 1-2 |
| *Datura metel* | 91-122 cm | NC State (3-4 ft) | 1-2 |
| *Ipomoea tricolor* | 91-183 cm | NC State (3-6 ft) | 1-2 |
| *Prunus persica* | 300-762 cm | Wikipedia (3-4 m), PFAF (6 m), NC State (15-25 ft) | 3-8 |

No width figure was found for *Eucalyptus deglupta* (only trunk diameter), *D. arenicola*, *ceratocaula*, *discolor*, *ferox*, *kymatocarpa*, *lanosa*,
*leichhardtii*, *pruinosa*, *quercifolia*, *reburra* or *Chara braunii*; they have no `spread_cm` yet.
Horticultural sources (NC State, PFAF) describe garden plants and run larger than wild descriptions.

## Not done yet

- Sideways spread is recorded but not yet built: wide plants need extra blocks and a placement rule.
- Six species have no height in the sources (`size.source: pending`) and stay 1 block until a real figure is found.

## Short plants and sub-block sprites

A plant whose typical height is under one block is drawn only as tall as it really is, standing at the bottom of its
block (`block_scale` in `tools/make_textures.py`, from the same sourced size range the sampler uses). Plants that can
exceed one block fill the block. Plants with no size data are drawn full height until a source is found.
