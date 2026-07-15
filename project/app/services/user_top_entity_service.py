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
from app.services.result_batch_discovery import latest_monthly_batch

USER_MANUFACTURER_SCOPE_PATH = PROJECT_ROOT / "config" / "user_manufacturer_scope.example.csv"

RankingStrategy = Literal[
    "mixed_v2",
    "probability",
    "business_priority",
    "interval",
    "frequency",
    "involved_amount",
    "loss_value",
    "detector_score",
]
GroupBy = Literal["manufacturer", "user_scope"]
CandidateType = Literal["recurring", "one_shot", "observation", "all"]
FillPolicy = Literal["none", "observation_fill", "one_shot_fill"]

PROBABILITY_COLUMNS = ["_profile_risk_probability", "risk_probability", "risk_probability_value", "churn_probability_H"]
INVOLVED_AMOUNT_COLUMNS = ["_profile_involved_amount", "involved_amount", "average_consumption_in_window"]
DETECTOR_SCORE_COLUMNS = ["detector_score", "max_detector_score", "latest_detector_score"]
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


class SortMetricUnavailable(ValueError):
    def __init__(self, requested_sort_by: str) -> None:
        self.requested_sort_by = requested_sort_by
        super().__init__(f"SORT_METRIC_NOT_AVAILABLE:{requested_sort_by}")


class HorizonNotAvailable(ValueError):
    def __init__(self, requested_horizon: str, available_horizons: list[str]) -> None:
        self.requested_horizon = requested_horizon
        self.available_horizons = available_horizons
        super().__init__(f"HORIZON_NOT_AVAILABLE:{requested_horizon}")


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
        max_n: int | None = None,
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
        if max_n is not None and top_n > max_n:
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
        batch, lookup_warnings = self._apply_display_lookup(batch, selected_month)
        warnings.extend(lookup_warnings)
        available_codes = _dedupe(
            batch.get("manufacturer_code", pd.Series(dtype=object)).dropna().astype(str).tolist()
        )
        scope, scope_warnings = self.scope_service.resolve_scope(
            user_id=user_id,
            requested_manufacturer_codes=manufacturer_codes,
            available_manufacturer_codes=available_codes,
        )
        if not scope:
            requested = _dedupe([str(code) for code in manufacturer_codes or [] if str(code).strip()])
            if requested:
                raise PermissionError("MANUFACTURER_SCOPE_FORBIDDEN")
            fallback_codes = [code for code in (requested or available_codes) if code in set(available_codes)]
            display_by_code = _manufacturer_display_names(batch)
            scope = [ManufacturerScope(code, display_by_code.get(code) or code) for code in fallback_codes]
            scope_warnings = [
                warning
                for warning in scope_warnings
                if warning != "USER_HAS_NO_VISIBLE_MANUFACTURER_SCOPE"
            ]
            scope_warnings.append("USER_SCOPE_FALLBACK_TO_BATCH_MANUFACTURERS")
        warnings.extend(scope_warnings)
        scoped = batch[
            batch["manufacturer_code"].astype(str).isin([item.manufacturer_code for item in scope])
        ].copy()
        scope_display_by_code = _manufacturer_display_names(scoped)
        scoped, horizon_warnings = self._apply_horizon_profile(scoped, selected_month, horizon)
        warnings.extend(horizon_warnings)
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
                    _scope_display_name(item, _manufacturer_display_names(scoped)),
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
            "sort_by": _sort_by_from_strategy(ranking_strategy),
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
                "scope_applied": True,
                "manufacturer_count": len(scope),
                "manufacturer_codes": [item.manufacturer_code for item in scope],
                "requested_manufacturer_code": manufacturer_codes[0] if manufacturer_codes and len(manufacturer_codes) == 1 else None,
                "effective_manufacturer_code": scope[0].manufacturer_code if len(scope) == 1 else None,
                "manufacturer_display_name": _scope_display_name(scope[0], scope_display_by_code) if len(scope) == 1 else None,
                "manufacturer_name": _scope_display_name(scope[0], scope_display_by_code) if len(scope) == 1 else None,
                "row_count": int(len(scoped)),
            },
            "groups": groups,
            "warnings": _dedupe(warnings),
        }

    def list_candidate_ranking(
        self,
        *,
        user_id: str,
        report_month: str | None = None,
        horizon: str = "H6",
        manufacturer_codes: list[str] | None = None,
        sort_by: str = "risk_probability",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Return a page from the complete recurring candidate ranking.

        This is the customer-facing path. The legacy top-entity method remains
        available for internal compatibility, but it is not used here and has
        no production max-N cap.
        """
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        if sort_order not in {"asc", "desc"}:
            raise ValueError("sort_order must be asc or desc")
        if sort_by == "detector_score":
            raise SortMetricUnavailable(sort_by)
        if sort_by not in {"risk_probability", "involved_amount", "loss_value"}:
            raise SortMetricUnavailable(sort_by)

        ranking_strategy = {
            "risk_probability": "probability",
            "involved_amount": "involved_amount",
            "loss_value": "loss_value",
        }[sort_by]
        full = self.list_user_top_entities(
            user_id=user_id,
            report_month=report_month,
            horizon=horizon,
            top_n=10**9,
            max_n=None,
            group_by="user_scope",
            ranking_strategy=ranking_strategy,
            candidate_type="recurring",
            fill_policy="none",
            manufacturer_codes=manufacturer_codes,
        )
        entities = [
            entity
            for group in full.get("groups", [])
            for entity in group.get("entities", [])
        ]
        if entities:
            frame = pd.DataFrame(entities)
            frame["_sort_value"] = pd.to_numeric(frame.get(sort_by), errors="coerce")
            frame["_sort_missing"] = frame["_sort_value"].isna()
            frame = frame.sort_values(
                ["_sort_missing", "_sort_value", "risk_entity_id"],
                ascending=[True, sort_order == "asc", True],
                na_position="last",
                kind="mergesort",
            )
            entities = frame.drop(columns=["_sort_value", "_sort_missing"]).to_dict("records")
        total = len(entities)
        start = (page - 1) * page_size
        page_items = entities[start : start + page_size]
        for index, entity in enumerate(entities, start=1):
            entity["rank"] = index
        page_items = entities[start : start + page_size]
        total_pages = math.ceil(total / page_size) if total else 0
        return {
            **full,
            "business_semantics": "candidate_ranking_result",
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
            "items": page_items,
            "entities": page_items,
            "total": total,
            "total_pages": total_pages,
            "top_n": len(page_items),
            "requested_top_n": page_size,
        }

    def list_visible_manufacturers(
        self,
        *,
        user_id: str,
        report_month: str | None = None,
        manufacturer_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        entities = self.repository.list_risk_entities()
        selected_month = _select_report_month(entities, report_month)
        batch = _filter_value(entities, "report_month", selected_month)
        batch, _ = self._apply_display_lookup(batch, selected_month)
        available_codes = _dedupe(
            batch.get("manufacturer_code", pd.Series(dtype=object)).dropna().astype(str).tolist()
        )
        scope, warnings = self.scope_service.resolve_scope(
            user_id=user_id,
            requested_manufacturer_codes=None,
            available_manufacturer_codes=available_codes,
        )
        display_by_code = _manufacturer_display_names(batch)
        scope_source = "user_manufacturer_scope"
        ready: bool | str = True
        if not scope:
            requested = _dedupe([str(code) for code in manufacturer_codes or [] if str(code).strip()])
            fallback_codes = [code for code in (requested or available_codes) if code in set(available_codes)]
            scope = [ManufacturerScope(code, display_by_code.get(code) or code) for code in fallback_codes]
            scope_source = "batch_manufacturer_fallback"
            ready = "conditional"
            warnings = [
                warning
                for warning in warnings
                if warning != "USER_HAS_NO_VISIBLE_MANUFACTURER_SCOPE"
            ]
            warnings.append("USER_SCOPE_FALLBACK_TO_BATCH_MANUFACTURERS")
        items = [
            {
                "manufacturer_code": item.manufacturer_code,
                "manufacturer_display_name": _scope_display_name(item, display_by_code),
                "manufacturer_name": _scope_display_name(item, display_by_code),
            }
            for item in scope
        ]
        return {
            "user_id": user_id,
            "current_user_id": user_id,
            "report_month": selected_month,
            "ready": ready,
            "scope_source": scope_source,
            "default_manufacturer_code": items[0]["manufacturer_code"] if items else None,
            "manufacturer_count": len(items),
            "manufacturers": items,
            "items": items,
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
            if ranking_strategy == "loss_value":
                out["_ranking_score"] = _loss_value_series(out)
                if out["_ranking_score"].notna().sum() == 0:
                    raise SortMetricUnavailable("loss_value")
                out["_ranking_score_source"] = "loss_value"
                out["_risk_probability_sort"] = _numeric_series(out, _first_existing(out, PROBABILITY_COLUMNS))
                out["_involved_amount_sort"] = _numeric_series(out, _first_existing(out, INVOLVED_AMOUNT_COLUMNS))
                out["_loss_sort_bucket"] = out["_ranking_score"].map(
                    lambda value: 2 if pd.isna(value) else (1 if float(value) == 0 else 0)
                )
                return out.sort_values(
                    ["_loss_sort_bucket", "_ranking_score", "_risk_probability_sort", "_involved_amount_sort", "risk_entity_id"],
                    ascending=[True, False, False, False, True],
                    na_position="last",
                    kind="mergesort",
                )
            elif ranking_strategy == "detector_score" and column is None:
                raise SortMetricUnavailable("detector_score")
            elif column is None:
                out["_ranking_score"] = 0.0
                out["_ranking_score_source"] = "missing_score_column"
            else:
                out["_ranking_score"] = pd.to_numeric(out[column], errors="coerce").fillna(-1)
                out["_ranking_score_source"] = column
        return out.sort_values("_ranking_score", ascending=False, kind="mergesort")

    def _apply_display_lookup(self, frame: pd.DataFrame, report_month: str) -> tuple[pd.DataFrame, list[str]]:
        if frame.empty:
            return frame.copy(), []
        try:
            lookup = self.repository.load_entity_display_lookup(report_month=report_month)
        except (FileNotFoundError, NotImplementedError, ValueError, AttributeError):
            return frame.copy(), ["DISPLAY_LOOKUP_MISSING"]
        if lookup.empty:
            return frame.copy(), ["DISPLAY_LOOKUP_MISSING"]
        join_cols = [
            "tenant_id",
            "report_month",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
        ]
        if not set(join_cols).issubset(frame.columns) or not set(join_cols).issubset(lookup.columns):
            return frame.copy(), ["DISPLAY_LOOKUP_KEY_COLUMNS_MISSING"]
        display_cols = [
            "manufacturer_display_name",
            "hospital_display_name",
            "drug_display_name",
            "region_code",
            "region_display_name",
            "product_line_code",
            "product_line_name",
            "display_name_source",
            "display_name_quality",
        ]
        available_cols = [col for col in display_cols if col in lookup.columns]
        joined = frame.merge(
            lookup[join_cols + available_cols].drop_duplicates(join_cols, keep="first"),
            on=join_cols,
            how="left",
            suffixes=("", "_lookup"),
        )
        for col in display_cols:
            lookup_col = f"{col}_lookup"
            if lookup_col not in joined.columns:
                continue
            if col in joined.columns:
                lookup_values = joined[lookup_col].map(_none_or_str)
                existing_values = joined[col].map(_none_or_str)
                joined[col] = lookup_values.where(lookup_values.notna(), existing_values)
                joined = joined.drop(columns=[lookup_col])
            else:
                joined = joined.rename(columns={lookup_col: col})
        warnings: list[str] = []
        if "display_name_quality" in joined and joined["display_name_quality"].astype(str).eq("code_fallback").any():
            warnings.append("DISPLAY_NAME_CODE_FALLBACK")
        if "hospital_display_name" in joined and joined["hospital_display_name"].isna().any():
            warnings.append("DISPLAY_LOOKUP_PARTIAL")
        return joined, warnings

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
        risk_probability = _float_or_none(
            row.get("_profile_risk_probability", row.get("risk_probability_value"))
        )
        if candidate_type in {"observation", "one_shot"}:
            risk_probability = None
        involved_amount = _int_or_none(
            row.get(
                "_profile_involved_amount",
                row.get("involved_amount", row.get("average_consumption_in_window")),
            )
        )
        loss_value = _loss_value(risk_probability, involved_amount)
        amount_available = involved_amount is not None
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
            "horizon": _none_or_str(row.get("_selected_horizon") or row.get("primary_horizon")),
            "candidate_type": candidate_type,
            "risk_probability": risk_probability,
            "average_consumption_in_window": involved_amount,
            "loss_value": loss_value,
            "loss_value_status": "ready" if amount_available else "amount_missing",
            "sort_policy": (
                "loss_value_desc"
                if amount_available
                else "risk_probability_desc_due_to_missing_amount_proxy"
            ),
            "involved_amount": involved_amount,
            "involved_amount_source": _none_or_str(row.get("involved_amount_source")),
            "risk_band": _none_or_str(row.get("risk_band")),
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
            "main_reason_summary": _none_or_str(row.get("reason") or row.get("main_reason_summary")),
            "suggested_action_short": _none_or_str(row.get("suggested_action_short")),
            "ranking_score": _float_or_none(row.get("_ranking_score")),
            "ranking_score_source": _none_or_str(row.get("_ranking_score_source"))
            or ranking_strategy,
        }

    def _apply_horizon_profile(
        self,
        frame: pd.DataFrame,
        report_month: str,
        horizon: str,
    ) -> tuple[pd.DataFrame, list[str]]:
        if frame.empty:
            return frame.copy(), []
        if "primary_horizon" in frame:
            primary_values = set(frame["primary_horizon"].dropna().astype(str))
            if horizon in primary_values:
                frame = _filter_value(frame, "primary_horizon", horizon)
        try:
            profiles = self.repository.list_risk_entity_horizon_profiles(
                report_month=report_month,
                horizon=horizon,
            )
        except (FileNotFoundError, NotImplementedError, ValueError, AttributeError):
            available_horizons = _available_horizons(self.repository)
            if available_horizons and horizon not in available_horizons:
                raise HorizonNotAvailable(horizon, available_horizons)
            return _filter_value(frame, "primary_horizon", horizon), ["HORIZON_PROFILE_NOT_AVAILABLE"]
        if profiles.empty:
            available_horizons = _available_horizons(self.repository)
            if available_horizons and horizon not in available_horizons:
                raise HorizonNotAvailable(horizon, available_horizons)
            return _filter_value(frame, "primary_horizon", horizon), ["HORIZON_PROFILE_NOT_AVAILABLE"]
        profile_cols = [
            "risk_entity_id",
            "report_month",
            "horizon",
            "risk_probability",
            "involved_amount",
            "involved_amount_source",
            "risk_level",
            "risk_band",
            "main_reason_summary",
            "reason",
            "detector_evidence_count",
            "updated_at",
        ]
        available = [col for col in profile_cols if col in profiles.columns]
        joined = frame.merge(
            profiles[available].drop_duplicates(["risk_entity_id", "report_month", "horizon"], keep="first"),
            on=["risk_entity_id", "report_month"],
            how="inner",
            suffixes=("", "_profile"),
        )
        if joined.empty:
            return joined, ["HORIZON_PROFILE_EMPTY_FOR_SELECTED_SCOPE"]
        joined["_selected_horizon"] = joined.get("horizon_profile", joined.get("horizon", horizon))
        probability_column = "risk_probability_profile" if "risk_probability_profile" in joined else "risk_probability"
        amount_column = "involved_amount_profile" if "involved_amount_profile" in joined else "involved_amount"
        if probability_column in joined:
            joined["_profile_risk_probability"] = pd.to_numeric(joined[probability_column], errors="coerce")
        if amount_column in joined:
            joined["_profile_involved_amount"] = pd.to_numeric(joined[amount_column], errors="coerce")
        if "involved_amount_source_profile" in joined:
            profile_source = joined["involved_amount_source_profile"].map(_none_or_str)
            existing_source = joined["involved_amount_source"].map(_none_or_str) if "involved_amount_source" in joined else pd.Series(None, index=joined.index)
            joined["involved_amount_source"] = profile_source.where(profile_source.notna(), existing_source)
        for column in ["risk_level", "risk_band", "main_reason_summary", "reason"]:
            profile_column = f"{column}_profile"
            if profile_column in joined:
                joined[column] = joined[profile_column].where(joined[profile_column].notna(), joined.get(column))
        return joined, []

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
            "sort_by": _sort_by_from_strategy(ranking_strategy),
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
    batch_dir = _default_batch_dir()
    if batch_dir:
        return TopEntityService(ParquetRiskResultRepository(batch_dir))
    return TopEntityService(_empty_repository(), scope_service=UserManufacturerScopeService())


def _default_batch_dir() -> str | Path | None:
    batch_root = os.getenv("RISK_RESULT_BATCH_ROOT")
    if batch_root:
        return latest_monthly_batch(batch_root)
    return os.getenv("RISK_RESULT_BATCH_DIR")


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
        return frame[_series_or_default(frame, "is_one_shot", False).map(_truthy)].copy()
    if candidate_type == "observation":
        return frame[_series_or_default(frame, "is_observation", False).map(_truthy)].copy()
    is_oneshot = _series_or_default(frame, "is_one_shot", False).map(_truthy)
    is_observation = _series_or_default(frame, "is_observation", False).map(_truthy)
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
    if strategy == "involved_amount":
        return _first_existing(frame, INVOLVED_AMOUNT_COLUMNS)
    if strategy == "loss_value":
        return None
    if strategy == "detector_score":
        return _first_existing(frame, DETECTOR_SCORE_COLUMNS)
    if strategy == "business_priority":
        return _first_existing(frame, BUSINESS_COLUMNS)
    if strategy == "interval":
        return _first_existing(frame, INTERVAL_COLUMNS)
    if strategy == "frequency":
        return _first_existing(frame, FREQUENCY_COLUMNS)
    return _first_existing(frame, PROBABILITY_COLUMNS)


def _first_existing(frame: pd.DataFrame, columns: list[str]) -> str | None:
    return next((column for column in columns if column in frame.columns), None)


def _sort_by_from_strategy(strategy: str) -> str:
    if strategy == "involved_amount":
        return "involved_amount"
    if strategy == "loss_value":
        return "loss_value"
    if strategy == "detector_score":
        return "detector_score"
    if strategy == "probability":
        return "risk_probability"
    return strategy


def _available_horizons(repository: RiskResultRepository) -> list[str]:
    try:
        horizons = getattr(repository.manifest(), "available_horizons", None)
    except (FileNotFoundError, NotImplementedError, ValueError, AttributeError):
        horizons = None
    if horizons:
        return [str(horizon) for horizon in horizons]
    return []


def _loss_value_series(frame: pd.DataFrame) -> pd.Series:
    probability_column = _first_existing(frame, PROBABILITY_COLUMNS)
    amount_column = _first_existing(frame, INVOLVED_AMOUNT_COLUMNS)
    probability = _numeric_series(frame, probability_column)
    amount = _numeric_series(frame, amount_column)
    return probability * amount


def _numeric_series(frame: pd.DataFrame, column: str | None) -> pd.Series:
    if column is None:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _loss_value(risk_probability: float | None, amount: int | None) -> int | None:
    if risk_probability is None or amount is None:
        return None
    return int(round(risk_probability * amount))


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


def _series_or_default(frame: pd.DataFrame, column: str, default: Any) -> pd.Series:
    if column in frame:
        return frame[column]
    return pd.Series(default, index=frame.index)


def _manufacturer_display_names(frame: pd.DataFrame) -> dict[str, str]:
    if frame.empty or "manufacturer_code" not in frame:
        return {}
    display: dict[str, str] = {}
    for _, row in frame.iterrows():
        code = _none_or_str(row.get("manufacturer_code"))
        name = _none_or_str(row.get("manufacturer_display_name"))
        if code and name and code not in display:
            display[code] = name
    return display


def _scope_display_name(item: ManufacturerScope, display_by_code: dict[str, str]) -> str:
    code = item.manufacturer_code
    lookup_name = display_by_code.get(code)
    if lookup_name and lookup_name != code:
        return lookup_name
    return item.manufacturer_display_name or code


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


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


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
