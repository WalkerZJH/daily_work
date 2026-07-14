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
