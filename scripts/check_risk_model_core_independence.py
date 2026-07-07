#!/usr/bin/env python
"""Check that risk_model_core runs independently from algorithm internals."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from risk_model_core import BusinessCopyRenderer, ParquetRiskResultRepository, RiskCardService, RiskQueryService  # noqa: E402
from risk_model_core.page_payload_builder import PagePayloadBuilder  # noqa: E402
from risk_model_core.validation import validate_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", required=True)
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir)
    validate_batch(batch_dir)
    repo = ParquetRiskResultRepository(batch_dir)
    manifest = repo.manifest()
    entities = repo.list_risk_entities().head(5)
    if entities.empty:
        raise RuntimeError("No risk entities found.")

    first_id = str(entities.iloc[0]["risk_entity_id"])
    detail = RiskQueryService(repo).get_detail(first_id)
    cards = RiskCardService(repo).list_cards_with_copy(first_id)
    payload_builder = PagePayloadBuilder(repo)
    index_payload = payload_builder.build_index_payload()
    clues_payload = payload_builder.build_clues_payload()
    watchlist_payload = payload_builder.build_watchlist_payload()

    renderer = BusinessCopyRenderer()
    renderer.render_entity_summary(detail["entity"])

    print("batch_id:", manifest.batch_id)
    print("report_month:", manifest.report_month)
    print("risk_entities_head:", entities[["risk_entity_id", "candidate_id"]].to_dict("records"))
    print("first_detail_cards:", len(cards))
    print("index_payload_keys:", sorted(index_payload.keys()))
    print("clues_items:", len(clues_payload.get("items", [])))
    print("watchlist_items:", len(watchlist_payload.get("items", [])))
    print("independence_check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
