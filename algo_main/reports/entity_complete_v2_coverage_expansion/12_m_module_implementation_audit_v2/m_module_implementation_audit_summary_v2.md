# M Module Implementation Audit V2

| module                              | status                 | note                                                                             |
|:------------------------------------|:-----------------------|:---------------------------------------------------------------------------------|
| M0                                  | implemented_current    | entity_complete_v2 data/feature/model foundation available                       |
| M1                                  | implemented_current    | candidate/worklist closure rows=393377                                           |
| M2                                  | intentionally_deferred | one-shot repeat model not rebuilt in this stage; one-shot attention is separated |
| M3                                  | implemented_current    | interval evidence rows=1172; not formal survival probability                     |
| M4                                  | implemented_current    | detector evidence rows=1180131; severity/confidence not probability              |
| M5                                  | implemented_current    | status rows=393377; auto_dispatch false                                          |
| M6                                  | interface_only         | evidence timeline/cache remains interface only                                   |
| M7                                  | implemented_current    | structured evidence bundle rows=393377; no LLM card                              |
| M8                                  | implemented_current    | closure validation and service gate decision generated                           |
| LLM line card                       | not_implemented        | LLM calls and formal line cards are forbidden in this stage                      |
| formal survival                     | intentionally_deferred | BG/NBD/Cox/AFT/discrete-time survival not trained                                |
| customer-facing probability service | rejected_or_abandoned  | not allowed for selected-subset v2                                               |
| auto dispatch                       | rejected_or_abandoned  | forbidden; all outputs keep auto_dispatch_allowed=false                          |
