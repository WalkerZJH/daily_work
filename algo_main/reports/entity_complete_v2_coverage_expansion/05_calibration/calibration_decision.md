# Calibration Decision

- selected method: raw
- rule: retain raw if ECE is already low or calibrator does not materially improve ECE/Brier/LogLoss.

| calibration_method   |       ece |    brier |   logloss |      auc |
|:---------------------|----------:|---------:|----------:|---------:|
| isotonic             | 0.0546902 | 0.174977 |  0.521199 | 0.808086 |
| platt                | 0.0566313 | 0.176097 |  0.527449 | 0.80824  |
| raw                  | 0.0275209 | 0.172637 |  0.514651 | 0.80824  |
