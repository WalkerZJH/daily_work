# Calibration Decision

- selected method: raw
- rule: retain raw if ECE is already low or calibrator does not materially improve ECE/Brier/LogLoss.

| calibration_method   |       ece |    brier |   logloss |      auc |
|:---------------------|----------:|---------:|----------:|---------:|
| isotonic             | 0.0703936 | 0.17213  |  0.51286  | 0.808067 |
| platt                | 0.0699935 | 0.172731 |  0.51786  | 0.808163 |
| raw                  | 0.0321886 | 0.167133 |  0.499768 | 0.808163 |
