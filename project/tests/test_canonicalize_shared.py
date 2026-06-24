from __future__ import annotations

import pandas as pd

from app.adapters.base import DatasetBundle
from app.adapters.canonicalize import prepare_canonical_orders


def _bundle(mapping: pd.DataFrame) -> DatasetBundle:
    return DatasetBundle(
        dataset_name="unit",
        orders=pd.DataFrame(
            [
                {
                    "order_id": "O1",
                    "drug_code": "D001",
                    "org_code": "ORG_A",
                    "order_time": "2025-01-02",
                    "purchase_qty": "10",
                    "purchase_amount": "100",
                    "purchase_price": "10",
                }
            ]
        ),
        drugs=pd.DataFrame(
            [
                {
                    "drug_code": "D001",
                    "drug_name": "Drug A",
                    "spec": "10mg",
                    "dosage_form": "tablet",
                    "approval_no": "A001",
                }
            ]
        ),
        orgs=pd.DataFrame(),
        product_line_mapping=mapping,
    )


def test_prepare_canonical_orders_merges_product_line_mapping() -> None:
    prepared = prepare_canonical_orders(
        _bundle(
            pd.DataFrame(
                [
                    {
                        "drug_code": "D001",
                        "product_line_code": "PL_A",
                        "product_line_name": "Alpha Line",
                    }
                ]
            )
        )
    )

    assert prepared.loc[0, "product_line_code"] == "PL_A"
    assert prepared.loc[0, "product_line_name"] == "Alpha Line"
    assert prepared.loc[0, "drug_name"] == "Drug A"


def test_prepare_canonical_orders_falls_back_to_drug_code_without_mapping() -> None:
    prepared = prepare_canonical_orders(_bundle(pd.DataFrame()))

    assert prepared.loc[0, "product_line_code"] == "D001"
    assert prepared.loc[0, "product_line_name"] == "D001"


def test_prepare_canonical_orders_parses_order_time_and_numeric_fields() -> None:
    prepared = prepare_canonical_orders(_bundle(pd.DataFrame()))

    assert pd.api.types.is_datetime64_any_dtype(prepared["order_time"])
    assert prepared.loc[0, "order_time"] == pd.Timestamp("2025-01-02")
    assert prepared.loc[0, "purchase_qty"] == 10
