from __future__ import annotations

import csv
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from app.core.config import PROJECT_ROOT

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from risk_model_core import (
    InMemoryRiskResultRepository,
    ParquetRiskResultRepository,
    RiskResultRepository,
)  # noqa: E402
from risk_model_core.manifest import RiskResultManifest  # noqa: E402

USER_MANUFACTURER_SCOPE_PATH = PROJECT_ROOT / "config" / "user_manufacturer_scope.example.csv"

RankingStrategy = Literal["mixed_v2", "probability", "business_priority", "interval", "frequency"]
GroupBy = Literal["manufacturer", "user_scope"]
CandidateType = Literal["recurring", "one_shot", "observation", "all"]
FillPolicy = Literal["none", "observation_fill", "one_shot_fill"]

PROBABILITY_COLUMNS = ["risk_probability_value", "churn_probability_H"]
INTERVAL_COLUMNS = ["interval_rank_score", "overdue_ratio", "current_interval_over_median"]
FREQUENCY_COLUMNS = ["frequency_rank_score", "frequency_decay_baseline", "frequency_ratio"]
BUSINESS_COLUMNS = ["business_priority_score_H", "business_priority_score", "value_at_risk_H"]
MIXED_WEIGHTS = {
    "probability": 0.5,
    "interval": 0.2,
    "frequency": 0.2,
    "business_priority": 0.1,
}


@dataclass(frozen=True)
class ManufacturerScope:
    manufacturer_code: str
    manufacturer_display_name: str | None = None
    tenant_id: str | None = None
    enterprise_id: str | None = None


class UserManufacturerScopeService:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        scope_path: Path = USER_MANUFACTURER_SCOPE_PATH,
    ) -> None:
        self._rows = rows
        self.scope_path = scope_path

    @classmethod
    def from_rows(cls, rows: list[dict[str, Any]]) -> "UserManufacturerScopeService":
        return cls(rows=rows)

    def resolve_scope(
        self,
        *,
        user_id: str,
        requested_manufacturer_codes: list[str] | None,
        available_manufacturer_codes: list[str],
    ) -> tuple[list[ManufacturerScope], list[str]]:
        requested = _dedupe(
            [str(code) for code in requested_manufacturer_codes or [] if str(code).strip()]
        )
        available = _dedupe(
            [str(code) for code in available_manufacturer_codes if str(code).strip()]
        )
        warnings: list[str] = []
        if user_id == "admin":
            selected = requested or available
            return [
                ManufacturerScope(code, code) for code in selected if code in set(available)
            ], warnings

        scope_rows = [
            row
            for row in self._load_rows()
            if str(row.get("user_id")) == str(user_id) and _truthy(row.get("enabled", True))
        ]
        allowed_by_code: dict[str, ManufacturerScope] = {}
        for row in scope_rows:
            code = str(row.get("manufacturer_code") or "").strip()
            if not code:
                continue
            allowed_by_code[code] = ManufacturerScope(
                manufacturer_code=code,
                manufacturer_display_name=_none_or_str(row.get("manufacturer_display_name"))
                or code,
                tenant_id=_none_or_str(row.get("tenant_id")),
                enterprise_id=_none_or_str(row.get("enterprise_id")),
            )
        selected_codes = requested or list(allowed_by_code)
        visible = [
            allowed_by_code[code]
            for code in selected_codes
            if code in allowed_by_code and code in set(available)
        ]
        if requested and len(visible) < len(requested):
            warnings.append("REQUESTED_MANUFACTURER_CODES_INTERSECTED_WITH_USER_SCOPE")
        if not visible:
            warnings.append("USER_HAS_NO_VISIBLE_MANUFACTURER_SCOPE")
        return visible, warnings

    def _load_rows(self) -> list[dict[str, Any]]:
        if self._rows is not None:
            return self._rows
        if not self.scope_path.exists():
            return []
        with self.scope_path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file))


class TopEntityService:
    def __init__(
        self,
        repository: RiskResultRepository,
        scope_service: UserManufacturerScopeService | None = None,
    ) -> None:
        self.repository = repository
        self.scope_service = scope_service or UserManufacturerScopeService()

    def list_user_top_entities(
        self,
        *,
        user_id: str,
        report_month: str | None = None,
        horizon: str = "H6",
        top_n: int = 20,
        max_n: int = 50,
        group_by: GroupBy = "user_scope",
        ranking_strategy: RankingStrategy = "probability",
        candidate_type: CandidateType = "recurring",
        probability_threshold: float | None = None,
        include_threshold_overflow: bool = False,
        fill_policy: FillPolicy = "none",
        manufacturer_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        if group_by == "manufacturer":
            warnings.append("GROUP_BY_MANUFACTURER_DEPRECATED_INTERNAL_ONLY")
        if ranking_strategy == "mixed_v2":
            warnings.append("MIXED_V2_DEPRECATED_INTERNAL_ONLY")
        if probability_threshold is not None or include_threshold_overflow:
            warnings.append("THRESHOLD_OVERFLOW_DEPRECATED_INTERNAL_ONLY")
        if fill_policy != "none":
            warnings.append("FILL_POLICY_DEPRECATED_INTERNAL_ONLY")
        effective_top_n = top_n
        if top_n > max_n:
            effective_top_n = max_n
            warnings.append("TOP_N_CLAMPED_TO_MAX_N")
        entities = self.repository.list_risk_entities()
        if entities.empty:
            return self._empty_response(
                user_id,
                report_month or "latest",
                horizon,
                top_n,
                group_by,
                ranking_strategy,
                "probability" if ranking_strategy == "mixed_v2" else ranking_strategy,
                None,
                warnings + ["RISK_RESULT_BATCH_HAS_NO_RISK_ENTITIES"],
            )

        selected_month = _select_report_month(entities, report_month)
        batch = _filter_value(entities, "report_month", selected_month)
        batch = _filter_value(batch, "primary_horizon", horizon)
        available_codes = _dedupe(
            batch.get("manufacturer_code", pd.Series(dtype=object)).dropna().astype(str).tolist()
        )
        scope, scope_warnings = self.scope_service.resolve_scope(
            user_id=user_id,
            requested_manufacturer_codes=manufacturer_codes,
            available_manufacturer_codes=available_codes,
        )
        warnings.extend(scope_warnings)
        scoped = batch[
            batch["manufacturer_code"].astype(str).isin([item.manufacturer_code for item in scope])
        ].copy()
        effective_strategy, strategy_warnings = self._effective_strategy(scoped, ranking_strategy)
        warnings.extend(strategy_warnings)

        if group_by == "user_scope":
            groups = [
                self._build_group(
                    "user_scope",
                    "User scope",
                    scoped,
                    effective_top_n,
                    effective_strategy,
                    candidate_type,
                    probability_threshold,
                    include_threshold_overflow,
                    fill_policy,
                )
            ]
        else:
            groups = [
                self._build_group(
                    item.manufacturer_code,
                    item.manufacturer_display_name or item.manufacturer_code,
                    scoped[
                        scoped["manufacturer_code"].astype(str).eq(item.manufacturer_code)
                    ].copy(),
                    effective_top_n,
                    effective_strategy,
                    candidate_type,
                    probability_threshold,
                    include_threshold_overflow,
                    fill_policy,
                )
                for item in scope
            ]

        return {
            "user_id": user_id,
            "report_month": selected_month,
            "horizon": horizon,
            "ranking_strategy": ranking_strategy,
            "effective_ranking_strategy": effective_strategy,
            "ranking_strategy_effective": effective_strategy,
            "ranking_strategy_warning": "; ".join(strategy_warnings) if strategy_warnings else None,
            "top_n": effective_top_n,
            "requested_top_n": top_n,
            "group_by": group_by,
            "scope_mode": group_by,
            "candidate_type": candidate_type,
            "probability_threshold": probability_threshold,
            "include_threshold_overflow": include_threshold_overflow,
            "fill_policy": fill_policy,
            "scope": {
                "manufacturer_count": len(scope),
                "manufacturer_codes": [item.manufacturer_code for item in scope],
            },
            "groups": groups,
            "warnings": _dedupe(warnings),
        }

    def _build_group(
        self,
        manufacturer_code: str,
        manufacturer_display_name: str,
        frame: pd.DataFrame,
        top_n: int,
        ranking_strategy: str,
        candidate_type: CandidateType,
        probability_threshold: float | None,
        include_threshold_overflow: bool,
        fill_policy: FillPolicy,
    ) -> dict[str, Any]:
        primary = _filter_candidate_type(frame, candidate_type)
        ranked = self._rank(primary, ranking_strategy)
        threshold_hits = _threshold_hits(ranked, probability_threshold)
        if probability_threshold is not None:
            ranked = ranked.assign(_threshold_hit=threshold_hits).sort_values(
                ["_threshold_hit", "_ranking_score"], ascending=[False, False]
            )
        selected = ranked.head(top_n)
        if include_threshold_overflow and probability_threshold is not None:
            selected = pd.concat(
                [selected, ranked[threshold_hits]], ignore_index=True
            ).drop_duplicates("risk_entity_id")
        overflow_count = max(0, int(len(selected) - top_n)) if include_threshold_overflow else 0
        selected = self._fill_shortage(
            selected,
            frame,
            top_n,
            ranking_strategy,
            fill_policy,
        )
        return {
            "manufacturer_code": manufacturer_code,
            "manufacturer_display_name": manufacturer_display_name,
            "available_count": int(len(primary)),
            "returned_count": int(len(selected)),
            "threshold_hit_count": (
                int(threshold_hits.sum()) if probability_threshold is not None else 0
            ),
            "overflow_count": overflow_count,
            "shortage_count": max(0, top_n - int(len(selected))),
            "entities": [
                self._entity_payload(row, ranking_strategy) for _, row in selected.iterrows()
            ],
        }

    def _fill_shortage(
        self,
        selected: pd.DataFrame,
        frame: pd.DataFrame,
        top_n: int,
        ranking_strategy: str,
        fill_policy: FillPolicy,
    ) -> pd.DataFrame:
        shortage = top_n - len(selected)
        if shortage <= 0 or fill_policy == "none":
            return selected
        fill_type: CandidateType = (
            "observation" if fill_policy == "observation_fill" else "one_shot"
        )
        fill_pool = _filter_candidate_type(frame, fill_type)
        if not selected.empty and "risk_entity_id" in fill_pool:
            fill_pool = fill_pool[
                ~fill_pool["risk_entity_id"]
                .astype(str)
                .isin(selected["risk_entity_id"].astype(str))
            ]
        fill_ranked = self._rank(fill_pool, ranking_strategy).head(shortage)
        return pd.concat([selected, fill_ranked], ignore_index=True)

    def _rank(self, frame: pd.DataFrame, ranking_strategy: str) -> pd.DataFrame:
        if frame.empty:
            return frame.assign(
                _ranking_score=pd.Series(dtype=float), _ranking_score_source=pd.Series(dtype=object)
            )
        out = frame.copy()
        if ranking_strategy == "mixed_v2":
            components = {
                "probability": _first_existing(out, PROBABILITY_COLUMNS),
                "interval": _first_existing(out, INTERVAL_COLUMNS),
                "frequency": _first_existing(out, FREQUENCY_COLUMNS),
                "business_priority": _first_existing(out, BUSINESS_COLUMNS),
            }
            score = pd.Series(0.0, index=out.index)
            for name, column in components.items():
                values = (
                    pd.Series(0.0, index=out.index)
                    if column is None
                    else pd.to_numeric(out[column], errors="coerce").fillna(0)
                )
                score = score + MIXED_WEIGHTS[name] * values.rank(method="first", pct=True)
            out["_ranking_score"] = score
            out["_ranking_score_source"] = "mixed_v2"
        else:
            column = _score_column_for_strategy(out, ranking_strategy)
            if column is None:
                out["_ranking_score"] = 0.0
                out["_ranking_score_source"] = "missing_score_column"
            else:
                out["_ranking_score"] = pd.to_numeric(out[column], errors="coerce").fillna(-1)
                out["_ranking_score_source"] = column
        return out.sort_values("_ranking_score", ascending=False)

    @staticmethod
    def _effective_strategy(frame: pd.DataFrame, ranking_strategy: str) -> tuple[str, list[str]]:
        if ranking_strategy == "mixed_v2":
            missing = []
            for label, columns in {
                "interval": INTERVAL_COLUMNS,
                "frequency": FREQUENCY_COLUMNS,
                "business_priority": BUSINESS_COLUMNS,
            }.items():
                if _first_existing(frame, columns) is None:
                    missing.append(label)
            if missing:
                detail = "missing_mixed_fields: " + ",".join(missing)
                return "probability", ["MIXED_V2_DOWNGRADED_TO_PROBABILITY", detail]
        if (
            ranking_strategy in {"business_priority", "interval", "frequency"}
            and _score_column_for_strategy(frame, ranking_strategy) is None
        ):
            return "probability", [f"{ranking_strategy.upper()}_DOWNGRADED_TO_PROBABILITY"]
        return ranking_strategy, []

    @staticmethod
    def _entity_payload(row: pd.Series, ranking_strategy: str) -> dict[str, Any]:
        candidate_type = _candidate_type(row)
        risk_probability = _float_or_none(row.get("risk_probability_value"))
        if candidate_type in {"observation", "one_shot"}:
            risk_probability = None
        is_high_risk = bool(row.get("is_high_risk")) and candidate_type == "recurring"
        return {
            "risk_entity_id": _none_or_str(row.get("risk_entity_id")),
            "candidate_id": _none_or_str(row.get("candidate_id")),
            "manufacturer_code": _none_or_str(row.get("manufacturer_code")),
            "manufacturer_display_name": _none_or_str(row.get("manufacturer_display_name")),
            "hospital_code": _none_or_str(row.get("hospital_code")),
            "hospital_display_name": _none_or_str(row.get("hospital_display_name")),
            "drug_code": _none_or_str(row.get("drug_code")),
            "drug_display_name": _none_or_str(row.get("drug_display_name"))
            or _none_or_str(row.get("drug_group")),
            "region_display_name": _none_or_str(row.get("region_display_name"))
            or _none_or_str(row.get("region")),
            "report_month": _none_or_str(row.get("report_month")),
            "horizon": _none_or_str(row.get("primary_horizon")),
            "candidate_type": candidate_type,
            "risk_probability": risk_probability,
            "risk_level": _none_or_str(row.get("risk_level")),
            "risk_color": _none_or_str(row.get("risk_color")),
            "risk_score_display": _clean_value(row.get("risk_score_display")),
            "review_status": _none_or_str(row.get("review_status")),
            "final_candidate_status": _none_or_str(row.get("final_candidate_status")),
            "review_priority": _none_or_str(row.get("review_priority")),
            "risk_card_count": _int_or_zero(row.get("risk_card_count")),
            "is_high_risk": is_high_risk,
            "is_observation": candidate_type == "observation",
            "is_one_shot": candidate_type == "one_shot",
            "auto_dispatch_allowed": False,
            "main_reason_summary": _none_or_str(row.get("main_reason_summary")),
            "suggested_action_short": _none_or_str(row.get("suggested_action_short")),
            "ranking_score": _float_or_none(row.get("_ranking_score")),
            "ranking_score_source": _none_or_str(row.get("_ranking_score_source"))
            or ranking_strategy,
        }

    @staticmethod
    def _empty_response(
        user_id: str,
        report_month: str,
        horizon: str,
        top_n: int,
        group_by: str,
        ranking_strategy: str,
        effective_ranking_strategy: str,
        ranking_strategy_warning: str | None,
        warnings: list[str],
    ) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "report_month": report_month,
            "horizon": horizon,
            "ranking_strategy": ranking_strategy,
            "effective_ranking_strategy": effective_ranking_strategy,
            "ranking_strategy_effective": effective_ranking_strategy,
            "ranking_strategy_warning": ranking_strategy_warning,
            "top_n": top_n,
            "requested_top_n": top_n,
            "group_by": group_by,
            "scope_mode": group_by,
            "candidate_type": "recurring",
            "probability_threshold": None,
            "include_threshold_overflow": False,
            "fill_policy": "none",
            "scope": {"manufacturer_count": 0, "manufacturer_codes": []},
            "groups": [],
            "warnings": _dedupe(warnings),
        }


def build_default_top_entity_service() -> TopEntityService:
    batch_dir = os.getenv("RISK_RESULT_BATCH_DIR")
    if batch_dir:
        return TopEntityService(ParquetRiskResultRepository(batch_dir))
    return TopEntityService(_empty_repository(), scope_service=UserManufacturerScopeService())


def _filter_value(frame: pd.DataFrame, column: str, value: str | None) -> pd.DataFrame:
    if value is None or column not in frame:
        return frame.copy()
    return frame[frame[column].astype(str).eq(str(value))].copy()


def _select_report_month(frame: pd.DataFrame, report_month: str | None) -> str:
    if report_month and report_month != "latest":
        return report_month
    if "report_month" not in frame or frame.empty:
        return report_month or "latest"
    values = sorted(frame["report_month"].dropna().astype(str).unique())
    return values[-1] if values else "latest"


def _filter_candidate_type(frame: pd.DataFrame, candidate_type: CandidateType) -> pd.DataFrame:
    if frame.empty or candidate_type == "all":
        return frame.copy()
    if candidate_type == "one_shot":
        return frame[frame.get("is_one_shot", False).map(_truthy)].copy()
    if candidate_type == "observation":
        return frame[frame.get("is_observation", False).map(_truthy)].copy()
    is_oneshot = frame.get("is_one_shot", pd.Series(False, index=frame.index)).map(_truthy)
    is_observation = frame.get("is_observation", pd.Series(False, index=frame.index)).map(_truthy)
    return frame[~is_oneshot & ~is_observation].copy()


def _threshold_hits(frame: pd.DataFrame, threshold: float | None) -> pd.Series:
    if threshold is None or frame.empty:
        return pd.Series(False, index=frame.index)
    column = _first_existing(frame, PROBABILITY_COLUMNS)
    if column is None:
        return pd.Series(False, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce").fillna(-1) >= threshold


def _score_column_for_strategy(frame: pd.DataFrame, strategy: str) -> str | None:
    if strategy == "probability":
        return _first_existing(frame, PROBABILITY_COLUMNS)
    if strategy == "business_priority":
        return _first_existing(frame, BUSINESS_COLUMNS)
    if strategy == "interval":
        return _first_existing(frame, INTERVAL_COLUMNS)
    if strategy == "frequency":
        return _first_existing(frame, FREQUENCY_COLUMNS)
    return _first_existing(frame, PROBABILITY_COLUMNS)


def _first_existing(frame: pd.DataFrame, columns: list[str]) -> str | None:
    return next((column for column in columns if column in frame.columns), None)


def _candidate_type(row: pd.Series) -> str:
    if _truthy(row.get("is_one_shot")):
        return "one_shot"
    if _truthy(row.get("is_observation")):
        return "observation"
    status = str(row.get("final_candidate_status") or row.get("review_status") or "").lower()
    if "one_shot" in status:
        return "one_shot"
    if "observation" in status:
        return "observation"
    return "recurring"


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _none_or_str(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        output = float(value)
        if math.isnan(output):
            return None
        return output
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        if value is None or pd.isna(value):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _empty_repository() -> InMemoryRiskResultRepository:
    manifest = RiskResultManifest(
        batch_id="empty",
        report_type="monthly",
        report_month="latest",
        report_date="",
        score_cutoff_month="",
        primary_horizon="H6",
        available_horizons=["H6"],
        schema_version="empty",
        data_backend="memory",
        allowed_usage=[],
        forbidden_usage=[],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={},
    )
    return InMemoryRiskResultRepository(manifest, {"risk_entities": pd.DataFrame()})
