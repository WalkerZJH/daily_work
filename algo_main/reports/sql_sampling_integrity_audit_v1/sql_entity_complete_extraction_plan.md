# SQL Entity-Complete Extraction Plan

## Recommended Sequence

Recommendation: `manufacturer_complete_then_entity_complete`.

## Plan A: Entity-Complete Sample

1. Select a controlled list of entity keys from SQL: `manufacturer_code x hospital_code x drug_code`.
2. Pull every order for those entities across the full available time range.
3. Use this for algorithm development, sequence features, interval features, and leakage-safe backtests.
4. Advantage: bounded data volume and complete histories. Limitation: full-universe recall is still sampled.

## Plan B: Manufacturer-Complete Subset

1. Select several stable manufacturers.
2. Pull all hospitals, drugs, and orders for those manufacturers across the full available time range.
3. Use this to validate the stable-enterprise service-scope hypothesis.
4. Advantage: realistic customer/service scope. Limitation: manufacturer selection can skew global conclusions.

## Plan C: Time-Window-Complete Extraction

1. Pull every order in a full time window, for example 2020-01 through 2025-12.
2. Build features and labels only within that window.
3. Use this for full-universe candidate recall and coverage backtests.
4. Advantage: best for production-like full-universe recall. Limitation: data volume may be large and old history before the window remains truncated.

## Plan D: Hybrid Recommended

1. Start with a manufacturer-complete subset to validate stable service scope.
2. Add an entity-complete sample to stress-test low-history and lumpy/intermittent entities.
3. Move to time-window-complete extraction when SQL volume and runtime are confirmed.

This sequence avoids tuning models on potentially truncated histories and gives a clean bridge to full-universe interval/survival evaluation.
