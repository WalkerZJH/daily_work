# Train / Valid / Test Split Audit

| horizon   | split   |   row_count |   positive_rate | cutoff_min   | cutoff_max   |   purge_gap_months | random_kfold_used_as_primary   | same_cutoff_in_train_test   | note                                                                                        |
|:----------|:--------|------------:|----------------:|:-------------|:-------------|-------------------:|:-------------------------------|:----------------------------|:--------------------------------------------------------------------------------------------|
| H12       | test    |      144292 |        0.270819 | 2025-01-31   | 2025-06-30   |                 12 | False                          | False                       | H12 uses an earlier train/valid split so closed labels do not overlap test feature cutoffs. |
| H12       | train   |      279488 |        0.271818 | 2020-01-31   | 2021-12-31   |                 12 | False                          | False                       | H12 uses an earlier train/valid split so closed labels do not overlap test feature cutoffs. |
| H12       | unused  |      507439 |        0.314556 | 2022-01-31   | 2024-12-31   |                 12 | False                          | False                       | H12 uses an earlier train/valid split so closed labels do not overlap test feature cutoffs. |
| H12       | valid   |       97198 |        0.352559 | 2023-01-31   | 2023-06-30   |                 12 | False                          | False                       | H12 uses an earlier train/valid split so closed labels do not overlap test feature cutoffs. |
| H3        | test    |      473040 |        0.476046 | 2024-04-30   | 2025-12-31   |                  3 | False                          | False                       | H3 train labels end before validation features; validation labels end before test features. |
| H3        | train   |      503351 |        0.515531 | 2020-01-31   | 2023-03-31   |                  3 | False                          | False                       | H3 train labels end before validation features; validation labels end before test features. |
| H3        | unused  |      102082 |        0.551615 | 2023-04-30   | 2024-03-31   |                  3 | False                          | False                       | H3 train labels end before validation features; validation labels end before test features. |
| H3        | valid   |      105429 |        0.554515 | 2023-07-31   | 2023-12-31   |                  3 | False                          | False                       | H3 train labels end before validation features; validation labels end before test features. |
| H6        | test    |      421760 |        0.360665 | 2024-07-31   | 2025-12-31   |                  6 | False                          | False                       | H6 train labels end before validation features; validation labels end before test features. |
| H6        | train   |      456325 |        0.386183 | 2020-01-31   | 2022-12-31   |                  6 | False                          | False                       | H6 train labels end before validation features; validation labels end before test features. |
| H6        | unused  |      200388 |        0.421837 | 2023-01-31   | 2024-06-30   |                  6 | False                          | False                       | H6 train labels end before validation features; validation labels end before test features. |
| H6        | valid   |      105429 |        0.441368 | 2023-07-31   | 2023-12-31   |                  6 | False                          | False                       | H6 train labels end before validation features; validation labels end before test features. |

## Closed Labels

| horizon   |   closed_rows |   positive_rate |
|:----------|--------------:|----------------:|
| H12       |       1028417 |        0.300397 |
| H3        |       1183902 |        0.506338 |
| H6        |       1183902 |        0.388041 |