from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.adapters.base import BaseSourceAdapter
from app.core.config import PROJECT_ROOT
from app.core.errors import DatasetLoadError

DATA_ROOT = PROJECT_ROOT / "data"


class CSVSourceAdapter(BaseSourceAdapter):
    def __init__(self, dataset_name: str | None = "sample", csv_path: str | None = None) -> None:
        self._dataset_name = dataset_name or "sample"
        self._csv_path = csv_path
        self._source_path = self._resolve_source_path()

    @property
    def dataset_name(self) -> str:
        if self._csv_path:
            return f"csv:{self._source_path.name}"
        return self._dataset_name

    def _resolve_source_path(self) -> Path:
        if self._csv_path:
            path = Path(self._csv_path)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            path = path.resolve()
            if not path.exists():
                raise DatasetLoadError(f"CSV path does not exist: {path}")
            return path

        dataset_path = DATA_ROOT / self._dataset_name
        if not dataset_path.exists():
            raise DatasetLoadError(f"Dataset does not exist: {dataset_path}")
        return dataset_path

    def _read_csv(self, file_name: str, columns: list[str] | None = None) -> pd.DataFrame:
        if self._source_path.is_file():
            if file_name == "orders.csv":
                return pd.read_csv(self._source_path)
            sibling = self._source_path.parent / file_name
            if sibling.exists():
                return pd.read_csv(sibling)
            return pd.DataFrame(columns=columns or [])

        file_path = self._source_path / file_name
        if not file_path.exists():
            if file_name == "orders.csv":
                raise DatasetLoadError(f"Required orders CSV missing: {file_path}")
            return pd.DataFrame(columns=columns or [])
        return pd.read_csv(file_path)

    def load_orders(self) -> pd.DataFrame:
        return self._read_csv("orders.csv")

    def load_drugs(self) -> pd.DataFrame:
        return self._read_csv(
            "drugs.csv",
            [
                "drug_code",
                "drug_name",
                "spec",
                "dosage_form",
                "approval_no",
                "manufacturer",
                "insurance_type",
                "product_line_code",
                "product_line_name",
            ],
        )

    def load_orgs(self) -> pd.DataFrame:
        return self._read_csv(
            "orgs.csv",
            ["org_code", "org_name", "org_level", "region_code", "region_name"],
        )

    def load_product_line_mapping(self) -> pd.DataFrame:
        return self._read_csv(
            "product_line_mapping.csv",
            ["drug_code", "product_line_code", "product_line_name", "mapping_rule", "confidence"],
        )
