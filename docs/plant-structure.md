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
| other Datura | under 1 m, or no data | 1 |

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

No width figure was found for *D. arenicola*, *ceratocaula*, *discolor*, *ferox*, *kymatocarpa*, *lanosa*,
*leichhardtii*, *pruinosa*, *quercifolia*, *reburra* or *Chara braunii*; they have no `spread_cm` yet.
Horticultural sources (NC State, PFAF) describe garden plants and run larger than wild descriptions.

## Not done yet

- Sideways spread is recorded but not yet built: wide plants need extra blocks and a placement rule.
- Six species have no height in the sources (`size.source: pending`) and stay 1 block until a real figure is found.
