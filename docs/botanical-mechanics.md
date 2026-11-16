# Botanical reproduction mechanics (FUTURE SCOPE: design proposal, not implemented)

> Agreed to keep this as future scope. The data and graphics phases continue first; nothing here is built or added to the
> plant-file schema yet. Propagation facts found along the way are collected below so they are not lost.

**Principle:** whatever starts a new plant (seed, pit, grain, cutting) can only come from the real biological step
that makes it. No saplings from breaking leaves.

```
flower opens -> pollinated (or self-fertile) -> fertilised -> fruit/seed develops -> ripe -> released -> dispersed
   -> right conditions to germinate -> seedling -> grows until old enough to flower again
```

## Proposed rules

1. **Seeds and saplings come only from ripe fruit, capsules or grain** that a flowered, fertilised plant actually
   produced. Breaking a young tree or its leaves never drops a sapling.
2. **Fertilisation is per species.** Self-fertile plants set fruit alone; the others need a pollinator at the right
   time (night-flowering Datura needs moths, not bees).
3. **Fruit takes time**, through the stages already drawn (fruit set, unripe, ripe; green capsule, split capsule).
4. **Dispersal is part of the plant.** Some release seed on their own (split capsules), some use animals.
5. **Germination has conditions** (temperature, soil, disturbance, dormancy), where the sources give them.
6. **Age matters.** Plants flower only when old enough; some propagation (cuttings) is age-limited.
7. **Vegetative routes exist where real**: cuttings, ratoon regrowth.

## What our sources already say

| Plant | Reproduction facts in the sources |
|---|---|
| *Prunus persica* | Flowers self-fertile, outcross about 5% (Wikipedia); a poor nectar and pollen source for honey bees; fruits 2-3 years after sprouting; seed is the stone (pit); has a chilling period when it appears dormant |
| *Datura stramonium* | Flowers open at night and are fed on by nocturnal moths; seeds can lie dormant for years and germinate when soil is disturbed; seeds thought carried by birds |
| *Datura innoxia* | Capsule splits open irregularly; spiny capsule clings to animal fur and is carried away; seeds long-lived, dormant for many years |
| *Datura metel* | Capsule breaks up irregularly; seeds heavy, no wind adaptation, fruits not eaten by birds (Wikipedia argues against wind and bird dispersal) |
| *Salvia rosmarinus* | Seeds often hard to start, low germination rate; bush should mature 2-3 years before harvest |
| *Eucalyptus deglupta* | Seed germinates at about 20-22 C; cuttings work only from trees younger than 5 years (root inhibition after that); capsules hold 3-12 minute winged seeds |
| *Oryza sativa* | Self-fertile; grain planted directly or as seedlings raised in a seedbed and transplanted; about 6 months seed to harvest; tropical plants can give a ratoon crop |
| *Olea europaea* subsp. *europaea* | Propagated by cuttings and layering (roots easily; suckers rise from a cut stump); trees from seed or suckers yield poorly and are budded or grafted; to help seed germinate, the oily pericarp is softened by slight rotting or soaked in hot water or alkaline solution; a frost-killed tree resprouts from its rootstock; seeds are spread by foxes and birds (starling, emu) where feral. Pollination: wind and self-fertile (PFAF) vs many cultivars self-incompatible and planted in pairs (Wikipedia) |
| *Ipomoea tricolor* | Seeds carry a symbiotic fungus; grows as an annual in cool climates; pollination not stated |
| *Chara braunii* | Monoecious; oogonia and antheridia on the same plant; reproduces by oospores |

Many species have **no pollinator, dormancy or germination data yet**; that is the research queue.

## What the plant files would need (data phase)

A `propagation` section per species, every field sourced: how seed is released, pollinators (and time of day),
self-fertility, dormancy, germination temperature/soil/disturbance, age at first flowering, vegetative routes
(cuttings with their limits, ratoon), and typical lifespan. Rosemary's 35-year lifespan and the peach's roughly
20-year lifespan are already in the sources.

## Design questions to settle first

- **Time scale.** Real durations (rice about 6 months, peach 2-3 years to first fruit) must be mapped onto game time
  by one configurable ratio, or the mod is unplayable.
- **Where does the first seed come from?** Worldgen would place plants already in flower and fruit, and loot or
  villagers could supply a starter set.
- **Strictness.** A setting from "strict" (pollination and conditions enforced) to "relaxed" (bone meal and
  self-pollination shortcuts), so servers can choose.
- **Seasons.** The peach chilling period, rosemary's off-season flowering and most flowering windows depend on seasons,
  which vanilla lacks. Options: a day-count season clock, or a season mod hook.
- **Genetics.** The peach's 5% outcrossing and Datura's variable flowers could allow variants; not needed at first.
