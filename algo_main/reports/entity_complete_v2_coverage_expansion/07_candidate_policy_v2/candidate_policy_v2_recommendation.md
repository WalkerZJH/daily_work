# Candidate Policy V2 Recommendation

- recommended policy: multi_recall_union_top10
- mean candidate die recall: 0.4343
- mean manual review load: 8741.7
- v1 reference recall: 0.4452
- probability_top20 is the controlled-load fallback when union review load is too high.

| candidate_policy                |   candidate_die_recall |   candidate_rate |   candidate_positive_rate |   lift_vs_non_candidate |   manual_review_load |
|:--------------------------------|-----------------------:|-----------------:|--------------------------:|------------------------:|---------------------:|
| multi_recall_union_top20        |              0.648063  |        0.447106  |                  0.66128  |                 2.30472 |            14016.6   |
| multi_recall_union_top10        |              0.434333  |        0.278823  |                  0.708319 |                 1.99896 |             8741.71  |
| probability_top20               |              0.350434  |        0.200011  |                  0.793769 |                 2.17144 |             6284.76  |
| hybrid_business_guardrail_top15 |              0.23698   |        0.150017  |                  0.719448 |                 1.76206 |             4713.87  |
| probability_top10               |              0.183769  |        0.100017  |                  0.829753 |                 2.03217 |             3142.76  |
| recency_top10                   |              0.176785  |        0.100017  |                  0.798538 |                 1.93798 |             3142.76  |
| hybrid_50_30_20_top10           |              0.169035  |        0.100017  |                  0.766531 |                 1.83328 |             3142.76  |
| hybrid_40_30_30_top10           |              0.164167  |        0.100017  |                  0.745888 |                 1.76937 |             3142.76  |
| hybrid_40_40_20_top10           |              0.162801  |        0.100017  |                  0.739747 |                 1.75178 |             3142.76  |
| interval_top10                  |              0.155491  |        0.100017  |                  0.706184 |                 1.65872 |             3142.76  |
| business_priority_top10         |              0.153526  |        0.100017  |                  0.699564 |                 1.633   |             3142.76  |
| frequency_top10                 |              0.145427  |        0.100017  |                  0.662496 |                 1.5328  |             3142.76  |
| manufacturer_worklist_fill      |              0.0239577 |        0.0128249 |                  0.845024 |                 1.89791 |              398.4   |
| manufacturer_min_fill           |              0.0137355 |        0.0074428 |                  0.833743 |                 1.86659 |              230.044 |
