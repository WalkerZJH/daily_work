# CODEX Notes

- Every API change must update `docs/API.md`.
- Never print, copy, document, or commit `.env` secrets.
- Detectors must consume canonical schema fields, not raw Chinese database column names.
- Current scope does not implement a formal work-order system; output `RiskCardCandidate` only.
- Uncalibrated scores must not be described as probabilities. `rule_score` is sorting/debug context only.
- User config must keep permission separate from preference. Preference cannot exceed permission.
