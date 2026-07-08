# User TopEntity Backend Strategy

## Layer Decision

This requirement belongs to the `project/` backend API and service layer.

The algorithm layer (`risk_algorithm_core`) already produces a monthly `risk_result_batch`. The model layer (`risk_model_core`) reads that batch through repository/service abstractions. The new behavior is user scope resolution, manufacturer grouping, dynamic `top_n`, ranking policy selection, threshold handling, and response shaping. Those are backend query/worklist policy concerns, not model scoring, detector, or M-stage algorithm changes.

## Current Batch Field Review

Inspected formal batch:

```text
algo_main/data/entity_complete_v2_coverage_expansion/13_formal_algorithm_core_raw_to_batch/formal_result_batches/report_month=2025-12/batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw
```

`risk_entities` contains 1291 rows and 44 columns. Relevant available columns:

- `manufacturer_code`
- `manufacturer_display_name`
- `report_month`
- `primary_horizon`
- `risk_probability_value`
- `risk_score_display`
- `review_status`
- `final_candidate_status`
- `is_one_shot`
- `is_observation`
- `is_high_risk`
- `auto_dispatch_allowed`

The manifest caveats include:

- `bounded monthly worklist`
- `not full SQL universe claim`
- `business review required`

This means the current batch is broader than the frontend projection, but it is still a bounded monthly worklist rather than a full scored SQL universe.

## Field Sufficiency

The current batch is sufficient for a backend implementation of:

- current user to manufacturer scope filtering
- per-manufacturer TopN
- `group_by=manufacturer`
- `group_by=user_scope`
- `ranking_strategy=probability`
- `probability_threshold`
- threshold overflow policy
- recurring / one-shot / observation filtering
- observation or one-shot fill without high-risk escalation

The current batch is not sufficient for true `mixed_v2` scoring because `risk_entities` does not carry numeric interval, frequency, or business priority rank fields.

Missing optional fields for true `mixed_v2`:

- `probability_rank_score`
- `interval_rank_score`
- `frequency_rank_score`
- `business_priority_score_H`
- `value_at_risk_H`
- `overdue_ratio`
- `frequency_decay_baseline`
- `display_section`
- `probability_display_level`

## Implemented Backend Policy

The backend resolves:

```text
current_user
-> visible manufacturer_codes
-> risk_entities filtered by report_month and horizon
-> group by manufacturer_code by default
-> compute ranking score inside each group
-> return top_n per group
```

Non-admin users cannot expand scope through query parameters. If `manufacturer_codes` is passed, the backend intersects it with the user's configured scope. Admin users can specify manufacturer codes or default to all manufacturers present in the selected batch.

The first scope source is:

```text
project/config/user_manufacturer_scope.example.csv
```

This is a backend fixture/config hook and can later be replaced by a real permission system.

## Ranking Strategy

Supported request values:

- `mixed_v2`
- `probability`
- `business_priority`
- `interval`
- `frequency`

Current effective behavior:

- `probability` uses `risk_probability_value`.
- `mixed_v2` downgrades to `probability` because interval/frequency/business numeric rank fields are absent.
- `business_priority`, `interval`, and `frequency` also downgrade to `probability` when their required numeric source fields are absent.

The response keeps both:

- `ranking_strategy`: requested strategy
- `effective_ranking_strategy`: actual strategy used

Warnings record the downgrade, for example:

```text
MIXED_V2_DOWNGRADED_TO_PROBABILITY: missing interval,frequency,business_priority
```

`mixed_score`, business priority score, and detector severity are not exposed or interpreted as probability.

## TopN And Threshold

Default behavior:

- `top_n=20`
- `max_n=50`
- `group_by=manufacturer`
- `candidate_type=recurring`
- `fill_policy=none`

If `top_n > max_n`, the backend clamps to `max_n` and returns a warning.

If `probability_threshold` is set, each group reports:

- `threshold_hit_count`
- `overflow_count`
- `returned_count`

With `include_threshold_overflow=false`, returned rows do not exceed `top_n`. With `include_threshold_overflow=true`, threshold hits outside `top_n` may be included and counted as overflow.

## Fill Policy

`fill_policy=none` returns the actual eligible count and records shortage through `shortage_count`.

`observation_fill` can fill shortage with observation items, but those rows keep `candidate_type=observation` and `is_high_risk=false`.

`one_shot_fill` can fill shortage with one-shot attention items, but those rows keep `candidate_type=one_shot`, `is_high_risk=false`, and do not expose recurring churn probability.

## Why Not Global Top Then Allocate

Global TopK would suppress manufacturers that have lower absolute scores but still belong to a user's visible scope. The intended worklist is per-user and per-manufacturer workload shaping. Therefore ranking is computed after scope filtering and, by default, inside each manufacturer group.

## Frontend And Dependency Boundary

The frontend calls only the backend API:

```text
GET /api/risk/my/top-entities
```

The backend reads result batches through `risk_model_core` repository abstractions. The backend service does not import `algo_main` and does not read frontend files.

## No Algorithm Changes

This implementation does not:

- retrain models
- alter scoring
- alter detector behavior
- alter M1/M3/M4/M5 semantics
- add automatic dispatch
- expose customer-facing probability service switches

If future requirements need true `mixed_v2` instead of probability fallback, the recommended second-layer change is to add optional pass-through rank fields or an optional `rankable_entities` / `scored_entities` table to the result batch. Existing `risk_entities` frontend worklist semantics should remain stable.
