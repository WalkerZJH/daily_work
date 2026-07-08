from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FrontendPageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BatchContext(FrontendPageModel):
    report_month: str
    score_as_of_date: str
    data_watermark_at: str
    score_batch_id: str
    result_batch_id: str
    primary_horizon: str
    primary_horizon_label: str
    score_formula: str


class OverviewMetric(FrontendPageModel):
    label: str
    value: str
    tone: str


class TopKRecallMetric(FrontendPageModel):
    label: str
    requested_k_percent: float = Field(gt=0, le=1)
    actual_k_percent: float = Field(gt=0, le=1)
    selected_count: int = Field(ge=0)
    evaluation_population: int = Field(gt=0)
    true_positive_count: int = Field(ge=0)
    recall: float = Field(ge=0, le=1)
    k_policy: str


class ModelEvaluationMetric(FrontendPageModel):
    model_id: str
    model_name: str
    model_role: str
    horizon: str | None = None
    evaluation_window: str
    auc: float = Field(ge=0, le=1)
    prauc: float = Field(ge=0, le=1)
    pr_auc_lift: float | None = None
    ece: float = Field(ge=0, le=1)
    brier: float = Field(ge=0, le=1)
    topk_recall: list[TopKRecallMetric]
    sample_count: int = Field(gt=0)
    positive_count: int = Field(ge=0)
    updated_at: str


class WorkbenchFillPolicy(FrontendPageModel):
    manufacturer_code: str
    workbench_target_count: int
    global_current_month_hospital_drug_count: int
    fill_reason: str


class WorkbenchRow(FrontendPageModel):
    row_id: str
    entity_id: str | None = None
    manufacturer_code: str
    hospital_name: str
    drug_name: str
    region: str
    risk_probability: float = Field(ge=0, le=1)
    average_consumption_in_window: int
    business_score: int
    source_type: str
    fill_source: str
    action: str


class WorkbenchPayload(FrontendPageModel):
    batch_context: BatchContext
    overview_metrics: list[OverviewMetric]
    model_metrics: list[ModelEvaluationMetric] = Field(default_factory=list)
    display_lookup_status: dict[str, Any] | None = None
    fill_policy: WorkbenchFillPolicy
    rows: list[WorkbenchRow]


class RiskEntityItem(FrontendPageModel):
    entity_id: str
    hospital_name: str
    drug_name: str
    manufacturer_code: str
    region: str
    horizon: str
    risk_probability: float = Field(ge=0, le=1)
    average_consumption_in_window: int
    business_score: int
    risk_band: str
    risk_color: str
    last_purchase_date: str
    days_since_last_purchase: int
    risk_card_count: int
    status: str
    monthly_status: str
    value_level: str
    primary_reason: str


class RiskEntitiesPayload(FrontendPageModel):
    batch_context: BatchContext
    entities: list[RiskEntityItem]
    pagination: dict[str, int]
    display_lookup_status: dict[str, Any] | None = None


class DetectorResultItem(FrontendPageModel):
    detector_id: str
    detector_name: str
    score: float = Field(ge=0, le=1)
    signal: str
    status: str
    evidence: str
    action: str


class ShapHighlight(FrontendPageModel):
    feature: str
    contribution: float
    explanation: str


class HorizonProfile(FrontendPageModel):
    horizon: str
    label: str
    risk_probability: float = Field(ge=0, le=1)
    average_consumption_in_window: int
    business_score: int
    reason: str
    detector_results: list[DetectorResultItem]
    xgboost_shap: list[ShapHighlight]
    detector_narrative: str


class RiskEntityDetailPayload(FrontendPageModel):
    entity: RiskEntityItem
    horizon_profiles: dict[str, HorizonProfile]


class OneshotSummary(FrontendPageModel):
    oneshot_count: int
    high_repurchase_propensity_count: int
    average_repurchase_propensity: float = Field(ge=0, le=1)
    expected_repurchase_amount: int


class OneshotTerminalItem(FrontendPageModel):
    oneshot_id: str
    hospital_name: str
    drug_name: str
    region: str
    first_purchase_date: str
    first_purchase_amount: int
    days_since_first_purchase: int
    repurchase_propensity: float = Field(ge=0, le=1)
    expected_repurchase_amount: int
    priority: str
    reason: str


class OneshotPayload(FrontendPageModel):
    report_month: str
    summary: OneshotSummary
    items: list[OneshotTerminalItem]


class DailyReportOption(FrontendPageModel):
    daily_report_id: str
    date: str
    label: str
    title: str
    report_month: str
    score_batch_id: str
    data_watermark_at: str
    high_risk_entities: int
    oneshot_count: int
    detector_alerts: int
    summary: str


class MonthlyReportItem(FrontendPageModel):
    monthly_report_id: str
    title: str
    report_month: str
    score_batch_id: str
    data_watermark_at: str
    summary: str


class MonthlyReportsPayload(FrontendPageModel):
    batch_context: BatchContext
    overview_metrics: list[OverviewMetric]
    model_metrics: list[ModelEvaluationMetric] = Field(default_factory=list)
    daily_report_options: list[DailyReportOption]
    monthly_reports: list[MonthlyReportItem]


class ProofCaseItem(FrontendPageModel):
    proof_case_id: str
    title: str
    visible: str
    outcome: str
    case_summary: str


class ProofCasesPayload(FrontendPageModel):
    display_lookup_status: dict[str, Any] | None = None
    items: list[ProofCaseItem]


FrontendPayload = dict[str, Any]
