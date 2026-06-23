from __future__ import annotations

import pandas as pd

from app.schemas.api import DataQualityIssue, DataQualityReport

REQUIRED_ORDER_FIELDS = [
    "order_id",
    "drug_code",
    "org_code",
    "order_time",
    "purchase_qty",
    "purchase_amount",
    "purchase_price",
    "manufacturer",
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

        duplicate_ids = orders["order_id"].duplicated(keep=False)
        self._append_issue(
            issues,
            check_name="order_id_unique",
            severity="error",
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
