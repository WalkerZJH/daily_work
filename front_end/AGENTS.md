# Frontend page boundaries

## `clues.html` is the detector-inspection page

`clues.html` is reserved exclusively for displaying entities hit by detector rules.
It must load rule-clue data through `loadRuleCluesData` and show detector family,
detector subtype, detector score, evidence, and rule-hit status.

Do not turn this page into a candidate-ranking list. In particular, do not call
`loadCandidateRankingData`, do not paginate candidates by loss probability or
involved amount, and do not label the navigation entry as a candidate ranking.

Candidate-object probability ranking belongs to `index.html`. When changing the
clues page, preserve the detector family and detector subtype filters and keep
the visible navigation label in the rule-inspection style (currently: `规则巡检结果`).

## `clue-detail.html` has mutually exclusive read-only modes

With `riskEntityId` (or compatible `id`), it is a Recurring candidate detail and
may use the risk-entity, detector-evidence, and probability-trend APIs. With
only `clueId`, it is a rule-only detector detail and must use only
`GET /api/v1/detectors/clues/{clueId}`. Do not map a rule-only clue to a risk
entity or show monthly probability, H3/H6/H12, amount, ranking, or trend data.

## `oneshot.html` is facts-only

`oneshot.html` is the One-shot/new-terminal facts workbench. It may display only
facts published by the formal `oneshot_terminals` table, including hospital,
drug, manufacturer, first-purchase date, first-purchase-point amount, elapsed
days, report month, cutoff date, and result-batch context.

Do not display or sort by repurchase propensity, predicted repurchase amount,
marketing priority, detector score, or any model-derived probability. If the
formal One-shot table is absent, show the unavailable state and never fall back
to Recurring `risk_entities`. One-shot detail and predictive modeling remain
outside P2-01.
