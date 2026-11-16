You extract botanical facts about ONE plant species from the source text below, for a Minecraft mod
that models real plants. Be conservative: a missing field is better than a wrong one.

Rules
1. Use only the SOURCE TEXT. Do not use outside knowledge, even if you are sure of it.
2. Every field you fill in must carry a `quote`: a short passage copied EXACTLY, character for
   character, from the source text that supports it. Quotes are checked by program; a quote that
   is not found verbatim in the source causes the field to be thrown away.
3. If the source does not say, omit the field (or use null). Never guess, never average, never infer
   from the genus or family.
4. Heights and widths are in centimetres. Convert from m/ft/in yourself. Give the range the source
   states for an adult plant; `common_max` only if the source says larger sizes are rare.
5. `life_form` is one of: alga, annual_herb, perennial_herb, shrub, vine, tree. Biennials count as
   annual_herb. Pick the closest fit only if the source supports it.
6. `description` is 1-3 plain sentences summarising appearance and growth, written from the source.
   Its `quote` is the single most informative sentence it is based on.
7. `uses_real`: up to 5 real-world uses the source states (food, medicine, timber, ornamental, ...).
   Do not list a use the source does not mention.

Call the `record_species_facts` tool exactly once with your answer.

SPECIES: {name}
SOURCE TEXT (Wikipedia, {url}):
{text}
