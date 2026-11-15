# Flower and fruit system

One shared system drives every flowering plant in PlantCraft. A plant file only chooses a generic implementation `type` and fills in parameters, so adding a species means adding a data file, not new Java.

## The cycle

```
seed -> vegetative -> budding -> FLOWER -> (pollinated?) -> fruit set -> unripe fruit -> RIPE FRUIT
                                    |                                                       |
                                    +-- not pollinated: flower withers, no fruit            +-- harvested -> plant regrows to vegetative/budding
```

Every plant keeps its current stage as a block state property (`stage`, 0..N). Stages are named in the plant file's `growth_stages`, and the order of that list is the order of the property.

## What makes it "fully functioning"

1. **Flowering is real and visible.** Each plant's `reproduction.flowers` says what colour its flowers are and when they are open. In game:
   - `opens: day` / `morning_only` / `night` controls a daytime check on the flower stage. A night-blooming Datura flower is open and glowing slightly at night and closed in daylight; morning glory (*Ipomoea tricolor*) opens in the morning and is closed by afternoon.
   - Flowering needs the plant to have finished vegetative growth. Peach trees blossom as a block-state change on their leaves: blossom leaves, then fruit leaves.
2. **Pollination is required for fruit.** A flower only sets fruit if it is pollinated before it withers:
   - **Bees:** a bee that visits a flower that is in bloom marks it pollinated (vanilla bees already pathfind to flowers; we add our flowers to the `minecraft:flowers` tag and give them a pollination hook).
   - **Moths and other insects:** a lightweight stand-in (a `pollinated` chance per random tick if any other blooming plant of the same species is within a few blocks).
   - **Hand pollination:** the player can use a brush or a flower item on a bloom.
   - **Wind / self:** plants whose `pollination` lists `self` or `wind` use a random chance.
   - Bone meal can force the next stage as usual.
3. **Fruit grows through stages, not instantly.** Fruit set, unripe, then ripe, each driven by random ticks. Ripe fruit is the stage you harvest.
4. **Harvest is non-destructive.** Right-click ripe fruit (or break it) drops the fruit and resets the plant to an earlier stage, so it grows and fruits again. For trees, only the fruit state on the leaves is reset.
5. **Fruit drops seeds and propagates.** Ripe fruit left alone can fall or burst and drop seeds (this is how Datura capsules behave), which lets plants spread slowly.

## Generic implementation types

| `implementation.type` | Used by | Notes |
|---|---|---|
| `flower_fruit_plant` | Datura species | Bush or herb block with stages; fruit stage is a spiny capsule item source. |
| `fruit_tree` | *Prunus persica* | Sapling, trunk and leaves with a bloom/fruit property. Full tree growth via a configured feature. |
| `climbing_vine` | *Ipomoea tricolor* | Climbs walls and fences like vanilla vines; flowers open in the morning; seed pods. |
| `aquatic_plant` | *Chara braunii* | Underwater. Spore stages instead of flowers; no flower or fruit stage. |

Per-species oddities (the way *Datura ceratocaula* needs shallow water, say) hang off an optional `behavior` id.

## Parameters read from each plant file

- `growth_stages` - the stage list, in order, with names that become the block state values and texture names.
- `reproduction.flowers.opens` - when the flower is open.
- `reproduction.flowers.pollination` - which pollinators count.
- `reproduction.fruit` - whether there is fruit, what it is, whether it is edible, toxic or not.
- `implementation.growth` - requirements (light, water, soil), flowering/pollination/fruiting/regrowth notes that the code turns into parameters.
- `implementation.spawn` - biomes and feature type for world generation.

## Open decisions

- Seasons do not exist in vanilla Minecraft. Peach blossom timing is driven by tree age and a long random-tick cycle rather than a calendar. A season mod could later hook the same property.
- Poisonous plants (Datura, morning glory seeds) never poison without the player eating or brewing them, and the real-world hazard is handled as a game effect (nausea, darkness, hallucination-style visual effect) in the use phase.
