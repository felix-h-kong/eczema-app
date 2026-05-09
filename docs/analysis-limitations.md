# Known data-quality limitations for flare / ingredient analysis

Living doc. Update when limitations are added, partially addressed, or resolved.

## L1. Under-recorded compound ingredients in home meal prep (OPEN)

User doesn't consistently log every pantry ingredient that goes into home-cooked meals. Specifically flagged:

- **Continental chicken stock pot** — user's stated rule: "every lentil stew has it unless declared otherwise." Pre-Apr-19 lentil stew entries may be missing it in `parsed_ingredients`. Partial retroactive fix applied via `scripts/retro_tag_stock_pot.py`.
- **Chicken powder** — contains yeast extract. Used in meal prep but specific meals unknown to user in retrospect.
- **Spice blends, bouillon, sauces** — any compound product used in home cooking without barcode scanning or explicit text entry.

**Impact:** systematic false negatives for hidden ingredients (especially yeast extract, MSG, salicylates). Any lift number for these is a lower bound.

**Mitigation options if/when addressed:**

- User-curated "pantry defaults" — declare a date range + list of default ingredients that apply to unannotated home-cooked meals.
- Bulk-edit UI to tag common meal prep entries.
- Manual walk-through of the 28-day dataset annotating meal prep entries.

## L2. OFF barcode ingredients in non-English languages (PARTIALLY FIXED, 2026-04-21)

Open Food Facts returns `ingredients_text` in the product's primary language. A German product (e.g. Ritter Sport, entry id 239) came back with German tokens (`Zucker`, `Salz`, `Kakaobutter`) and allergen-emphasis markers (`_Soja_`).

**Fix applied** to `backend/main.py::_lookup_open_food_facts`:
- Prefer `ingredients_text_en` when present
- Strip `_..._` allergen markers

**Remaining work:** existing `parsed_ingredients` for entry 239 still has the German tokens. Options: re-scan the barcode to refresh, or add aliases (zucker → sugar, salz → salt, etc.) during the bootstrap session.

## L3. Small n for rising-edge flare detection (INHERENT)

The current binary flare definition (rise ≥ 2 from previous check, per-day collapse) yields only **7 flare days** across the 28-day dataset. With flare windows pulling 10-20 meals each, per-ingredient lift estimates have wide uncertainty bands.

**Workarounds in place:**
- Phase 1 dump is descriptive (visual inspection), not statistical.
- Compound-product decomposition via `ingredient_compositions` increases the hit rate on hidden ingredients.

**Deferred to Phase 2:**
- Continuous severity model (per-meal effect on severity in the following 24h). Uses all 59 severity-check entries, not just the 7 rising-edge days.
- Proper risk-ratio / lift formulas with confidence intervals and sample-size guards.

## L4. Dose and portion size (UNTRACKED)

Meal log entries don't capture quantity. A teaspoon of yeast extract in a stock pot spread across 5 meals is dose-wise very different from a teaspoon of Vegemite on one piece of toast, but both currently show up as the same binary "yeast extract present" event.

**Realistic mitigation:** probably not worth retrofitting. Note it as a caveat when interpreting any one-ingredient signal. Future entries could capture portion size for a few high-suspicion ingredients (e.g. Vegemite servings).

## L5. Confounding by co-occurrence (OPEN, PHASE 2)

Ingredients strongly co-vary (yeast extract always appears alongside salt + MSG in stock pots; stews always have onion + garlic). The current analysis cannot separate their individual contributions. Deferred to Phase 2 (joint modelling or partial-regression approach).
