# Candidate Policy V2 Recommendation

- recommended policy: multi_recall_union_top10
- mean candidate die recall: 0.4452
- mean manual review load per horizon-cutoff: 6012.4
- previous M1 mean recall reference: 0.1862
- load caveat: the recall-maximizing union policy is appropriate for analyst batch review; use `probability_top20` or `hybrid_business_guardrail_top15` if manual load must be capped more tightly.

| candidate_policy                |   candidate_die_recall |   candidate_rate |   candidate_positive_rate |   lift_vs_non_candidate |   manual_review_load |
|:--------------------------------|-----------------------:|-----------------:|--------------------------:|------------------------:|---------------------:|
| multi_recall_union_top10        |               0.445164 |         0.260861 |                  0.678314 |                 2.29694 |              6012.36 |
| probability_top20               |               0.383295 |         0.200017 |                  0.759813 |                 2.50689 |              4618.58 |
| hybrid_business_guardrail_top15 |               0.26147  |         0.150025 |                  0.694184 |                 2.01191 |              3464.22 |
| probability_top10               |               0.207605 |         0.100021 |                  0.817011 |                 2.37026 |              2309.58 |
| recency_top10                   |               0.203278 |         0.100021 |                  0.79944  |                 2.30888 |              2309.58 |
| hybrid_50_30_20_top10           |               0.18636  |         0.100021 |                  0.739688 |                 2.06589 |              2309.58 |
| hybrid_40_40_20_top10           |               0.182012 |         0.100021 |                  0.724218 |                 2.00588 |              2309.58 |
| hybrid_40_30_30_top10           |               0.181332 |         0.100021 |                  0.72189  |                 1.99652 |              2309.58 |
| interval_top10                  |               0.174204 |         0.100021 |                  0.690871 |                 1.90261 |              2309.58 |
| business_priority_top10         |               0.165479 |         0.100021 |                  0.658844 |                 1.78647 |              2309.58 |
| frequency_top10                 |               0.159113 |         0.100021 |                  0.637279 |                 1.70488 |              2309.58 |
