You extract botanical facts about ONE plant species from the source text below. The facts feed a Minecraft mod that
models real plants, and an artist (human or AI) who will draw sprites of the plant at every growth stage, so visual and
structural detail matters. Be conservative: a missing field is better than a wrong one.

Rules
1. Use only the SOURCE TEXT. Do not use outside knowledge, even if you are sure of it.
2. Every fact you record must carry a `quote`: a short passage copied EXACTLY, character for character, from the source
   text that supports it. Quotes are checked by program; a quote that is not found verbatim in the source causes that
   fact to be thrown away. Numeric facts must quote the sentence that contains the number.
3. If the source does not say, omit it. Never guess, never average, never infer from the genus or family.
4. Lengths are in centimetres (convert m, ft, in, mm yourself); other units are years, months, weeks, days, count, percent.
   Give the range the source states. `qualifier`: range, typical, average, maximum ("up to"), or rare_maximum ("rarely
   reaches"). Record each distinct number as its own `measurements` entry.

What to record
- `life_form`: alga, annual_herb, perennial_herb, shrub, vine or tree (biennials count as annual_herb).
- `description`: 1-3 plain sentences from the source about appearance and growth.
- `native_range`, `introduced_range`, `environment`: where it grows natively, where it has been introduced, and its habitat
  (soil, climate, light, water, altitude).
- `measurements`: height, spread, trunk diameter, crown width/height, bole height, branch length/diameter, internode length,
  leaf length/width, petiole length, flower and fruit size, seed size, lifespan, age to first flowering, time to harvest,
  flowering duration, tiller or branch counts, and so on, whenever the source gives a number.
- `appearance`: what each part LOOKS like (part = whole_plant, roots, trunk, bark, branches, twigs, buds, leaf, flower,
  inflorescence, fruit, seed): colours (say upper and lower leaf surface separately), shapes, textures, surface, how it
  changes with `stage` (young, unripe, ripe, mature, autumn, ...). One entry per fact.
- `architecture`: how the plant is BUILT: growth habit, branching pattern (forking, alternate, opposite, whorled), branch
  angle or droop, crown shape, canopy density, trunk form (straight, gnarled, multiple trunks), bark form, twig shape,
  stem type (hollow, woody, jointed), leaf arrangement and shape and margin, tillering, climbing mechanism, root system,
  buttresses, flower and fruit arrangement, response to pruning.
- `phenology`: when flowering, fruiting, ripening, seed release, leaf flush, leaf fall, dormancy, germination happen.
- `propagation`: pollination (who pollinates, wind, self), self-fertility, seed dispersal, germination needs, dormancy,
  cuttings and other vegetative propagation, regeneration after damage, age at maturity, lifespan, cultivation, toxicity.
- `flowers` / `fruit`: whether present, colours, opening time, season, pollinators; fruit type, ripening, edibility.
- `uses_real`: up to 12 real human uses the source states: `category` (food, medicine, material, fuel, ornamental,
  cultural, ecological, forage, toxic, research, other), `part_used`, and a short `note`. Do not list a use the source
  does not mention.

Call the `record_species_facts` tool exactly once with your answer.

SPECIES: {name}
SOURCE TEXT (Wikipedia, {url}):
{text}
