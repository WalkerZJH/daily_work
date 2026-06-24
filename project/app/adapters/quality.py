from __future__ import annotations

import pandas as pd

from app.schemas.api import DataQualityIssue, DataQualityReport

REQUIRED_ORDER_FIELDS = [
    "order_id",
    "drug_code",
    "org_code",
    "order_time",
    "purchase_qty",
    "purchase_price",
]


class DataQualityChecker:
    def check_orders(self, orders: pd.DataFrame, dataset_name: str) -> DataQualityReport:
        issues: list[DataQualityIssue] = []
        missing_fields = [field for field in REQUIRED_ORDER_FIELDS if field not in orders.columns]
        if missing_fields:
            issues.append(
                DataQualityIssue(
                    check_name="required_fields",
                    severity="error",
                    message=f"Missing required order fields: {', '.join(missing_fields)}",
                    row_count=len(orders),
                    sample_refs=[],
                )
            )
            return self._build_report(dataset_name, len(orders), issues)

        invalid_time = pd.to_datetime(orders["order_time"], errors="coerce").isna()
        self._append_issue(
            issues,
            check_name="order_time_parseable",
            severity="error",
            message="order_time has unparseable values",
            mask=invalid_time,
            orders=orders,
        )

        qty = pd.to_numeric(orders["purchase_qty"], errors="coerce")
        invalid_qty = qty.isna() | (qty < 0)
        self._append_issue(
            issues,
            check_name="purchase_qty_non_negative",
            severity="error",
            message="purchase_qty must be numeric and non-negative",
            mask=invalid_qty,
            orders=orders,
        )

        price = pd.to_numeric(orders["purchase_price"], errors="coerce")
        invalid_price = price.isna() | (price < 0)
        self._append_issue(
            issues,
            check_name="purchase_price_non_negative",
            severity="error",
            message="purchase_price must be numeric and non-negative",
            mask=invalid_price,
            orders=orders,
        )

        if "conversion_factor" in orders.columns:
            factor = pd.to_numeric(orders["conversion_factor"], errors="coerce")
            invalid_factor = factor.isna() | (factor <= 0)
            self._append_issue(
                issues,
                check_name="conversion_factor_valid",
                severity="warning",
                message="conversion_factor is missing, zero, or negative; comparable_unit_price used purchase_price fallback",
                mask=invalid_factor,
                orders=orders,
            )

        if "delivery_qty" in orders.columns:
            delivery_qty = pd.to_numeric(orders["delivery_qty"], errors="coerce")
            delivery_gt_purchase = delivery_qty.notna() & qty.notna() & (delivery_qty > qty)
            self._append_issue(
                issues,
                check_name="delivery_qty_gt_purchase_qty",
                severity="warning",
                message="delivery_qty is greater than purchase_qty",
                mask=delivery_gt_purchase,
                orders=orders,
            )

        if "receipt_qty" in orders.columns and "delivery_qty" in orders.columns:
            receipt_qty = pd.to_numeric(orders["receipt_qty"], errors="coerce")
            delivery_qty = pd.to_numeric(orders["delivery_qty"], errors="coerce")
            receipt_gt_delivery = receipt_qty.notna() & delivery_qty.notna() & (receipt_qty > delivery_qty)
            self._append_issue(
                issues,
                check_name="receipt_qty_gt_delivery_qty",
                severity="warning",
                message="receipt_qty is greater than delivery_qty",
                mask=receipt_gt_delivery,
                orders=orders,
            )

        empty_org = orders["org_code"].isna() | (orders["org_code"].astype(str).str.strip() == "")
        self._append_issue(
            issues,
            check_name="org_code_not_empty",
            severity="error",
            message="org_code must not be empty",
            mask=empty_org,
            orders=orders,
        )

        empty_drug = orders["drug_code"].isna() | (
            orders["drug_code"].astype(str).str.strip() == ""
        )
        self._append_issue(
            issues,
            check_name="drug_code_not_empty",
            severity="error",
            message="drug_code must not be empty",
            mask=empty_drug,
            orders=orders,
        )

        if "order_id" in orders.columns:
            duplicate_ids = orders["order_id"].duplicated(keep=False)
            self._append_issue(
                issues,
                check_name="order_id_unique",
                severity="warning",
                message="order_id contains duplicates",
                mask=duplicate_ids,
                orders=orders,
            )

        return self._build_report(dataset_name, len(orders), issues)

    @staticmethod
    def _append_issue(
        issues: list[DataQualityIssue],
        check_name: str,
        severity: str,
        message: str,
        mask: pd.Series,
        orders: pd.DataFrame,
    ) -> None:
        row_count = int(mask.sum())
        if row_count == 0:
            return
        sample_refs = orders.loc[mask, "order_id"].astype(str).head(5).tolist()
        issues.append(
            DataQualityIssue(
                check_name=check_name,
                severity=severity,
                message=message,
                row_count=row_count,
                sample_refs=sample_refs,
            )
        )

    @staticmethod
    def _build_report(
        dataset_name: str,
        total_rows: int,
        issues: list[DataQualityIssue],
    ) -> DataQualityReport:
        error_count = sum(issue.row_count for issue in issues if issue.severity == "error")
        warning_count = sum(issue.row_count for issue in issues if issue.severity == "warning")
        return DataQualityReport(
            dataset_name=dataset_name,
            total_rows=total_rows,
            error_count=error_count,
            warning_count=warning_count,
            issues=issues,
        )
