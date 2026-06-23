from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CanonicalModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class DrugRecord(CanonicalModel):
    drug_code: str
    drug_name: str
    spec: str
    dosage_form: str
    approval_no: str
    manufacturer: str
    insurance_type: str
    product_line_code: str | None = None
    product_line_name: str | None = None


class OrgRecord(CanonicalModel):
    org_code: str
    org_name: str
    org_level: str
    region_code: str
    region_name: str


class OrderRecord(CanonicalModel):
    order_id: str
    drug_code: str
    org_code: str
    order_time: datetime
    purchase_qty: float = Field(ge=0)
    purchase_amount: float
    purchase_price: float
    manufacturer: str
    delivery_qty: float | None = None
    delivery_time: datetime | None = None
    receipt_qty: float | None = None
    receipt_time: datetime | None = None


class ProductLineMapping(CanonicalModel):
    drug_code: str
    product_line_code: str
    product_line_name: str
    mapping_rule: str
    confidence: float = Field(ge=0, le=1)


class AnalysisUnit(CanonicalModel):
    org_code: str
    product_line_code: str
