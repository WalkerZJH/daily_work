from __future__ import annotations

import pandas as pd


class DisabledDetectorNoteBuilder:
    def build(self, gate_decisions: pd.DataFrame) -> pd.DataFrame:
        if gate_decisions.empty:
            return pd.DataFrame(columns=["detector_name", "gate_status", "disabled_reason_text"])
        disabled = gate_decisions[~gate_decisions["enable_frontend_display"].fillna(False)].copy()
        disabled["disabled_reason_text"] = disabled["semantic_caveat"].fillna(disabled["reason_code"])
        return disabled[["detector_name", "gate_status", "disabled_reason_text", "reason_code"]].reset_index(drop=True)
