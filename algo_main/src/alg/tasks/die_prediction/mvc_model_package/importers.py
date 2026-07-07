"""Import M-closure outputs into the MVC model package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(slots=True)
class MClosurePaths:
    data_dir: Path
    gate_path: Path
    report_dir: Path


class MClosureResultImporter:
    """Read M1/M3/M4/M5/M7/probability-gate outputs without importing algorithm modules."""

    def __init__(self, paths: MClosurePaths):
        self.paths = paths

    def load(self) -> dict[str, pd.DataFrame]:
        return {
            "m1": self.load_m1(),
            "worklist": self.load_worklist(),
            "m3": self.load_optional("m3_survival_refinement_results.csv"),
            "m4": self.load_m4(),
            "m5": pd.read_csv(self.paths.data_dir / "m5_candidate_status_decision.csv", low_memory=False),
            "gate": pd.read_csv(self.paths.gate_path, low_memory=False),
        }

    def load_frontend_worklist(self) -> dict[str, pd.DataFrame]:
        """Load only the bounded M1 worklist and matching row-level evidence.

        The previous MVC package intentionally created a broad internal dump from
        full M5/M4 outputs. Frontend payloads must not do that. They start from
        M1 manufacturer worklist candidate ids and chunk-filter the large
        row-level tables.
        """
        worklist = self.load_worklist()
        candidate_ids = set(worklist["candidate_id"].dropna().astype(str))
        return {
            "m1": worklist.copy(),
            "worklist": worklist,
            "m3": self.load_selected_optional("m3_survival_refinement_results.csv", candidate_ids),
            "m4": self.load_m4(candidate_ids=candidate_ids),
            "m5": self.load_selected_required("m5_candidate_status_decision.csv", candidate_ids),
            "gate": self.load_selected_path(self.paths.gate_path, candidate_ids),
        }

    def load_worklist(self) -> pd.DataFrame:
        path = self.paths.data_dir / "m1_manufacturer_worklist_candidates.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path, low_memory=False)

    def load_m1(self) -> pd.DataFrame:
        usecols = [
            "candidate_id",
            "candidate_type",
            "selection_reason",
            "display_section",
            "is_high_risk",
            "user_visible_caveat",
            "probability_score",
            "churn_probability_H",
            "demand_shape_label",
            "history_sufficiency_flag",
            "probability_display_level",
            "display_mode",
        ]
        files = [
            "m1_recurring_business_priority_candidates_by_horizon.csv",
            "m1_one_shot_attention_candidates.csv",
            "m1_demand_shape_observation_candidates.csv",
        ]
        return pd.concat([pd.read_csv(self.paths.data_dir / file, usecols=usecols, low_memory=False) for file in files], ignore_index=True)

    def load_m4(self, candidate_ids: set[str] | None = None) -> pd.DataFrame:
        usecols = [
            "candidate_id",
            "detector_family",
            "detector_name",
            "hit_flag",
            "severity",
            "confidence",
            "evidence_fields",
            "evidence_values",
            "reason_code",
            "business_interpretation",
            "data_quality_status",
            "data_quality_note",
        ]
        path = self.paths.data_dir / "m4_detector_evidence_results.csv"
        if candidate_ids is None:
            return pd.read_csv(path, usecols=usecols, low_memory=False)
        return self.load_selected_path(path, candidate_ids, usecols=usecols)

    def load_optional(self, filename: str) -> pd.DataFrame:
        path = self.paths.data_dir / filename
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path, low_memory=False)

    def load_selected_optional(self, filename: str, candidate_ids: set[str]) -> pd.DataFrame:
        path = self.paths.data_dir / filename
        if not path.exists():
            return pd.DataFrame()
        return self.load_selected_path(path, candidate_ids)

    def load_selected_required(self, filename: str, candidate_ids: set[str]) -> pd.DataFrame:
        return self.load_selected_path(self.paths.data_dir / filename, candidate_ids)

    def load_selected_path(self, path: Path, candidate_ids: set[str], usecols: list[str] | None = None) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(path)
        chunks: list[pd.DataFrame] = []
        for chunk in pd.read_csv(path, usecols=usecols, chunksize=200_000, low_memory=False):
            if "candidate_id" not in chunk:
                continue
            mask = chunk["candidate_id"].astype(str).isin(candidate_ids)
            if mask.any():
                chunks.append(chunk.loc[mask].copy())
        if not chunks:
            return pd.DataFrame(columns=usecols)
        return pd.concat(chunks, ignore_index=True)
