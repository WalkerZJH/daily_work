from __future__ import annotations

import argparse

from app.core.config import load_config
from app.schemas.api import DatabaseSmokeTestRequest
from app.services.database_smoke_test_service import DatabaseSmokeTestService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--lookback-days", type=int, default=30)
    parser.add_argument("--baseline-days", type=int, default=180)
    parser.add_argument("--history-start-date", default=None)
    parser.add_argument("--row-limit", type=int, default=5000)
    parser.add_argument("--enterprise-code", default=None)
    parser.add_argument("--province", default=None)
    parser.add_argument("--province-code", default=None)
    parser.add_argument("--product-line-code", default=None)
    parser.add_argument("--include-debug-features", action="store_true")
    args = parser.parse_args()

    request = DatabaseSmokeTestRequest(
        as_of_date=args.as_of_date,
        days=args.days,
        lookback_days=args.lookback_days,
        baseline_days=args.baseline_days,
        history_start_date=args.history_start_date,
        row_limit=args.row_limit,
        enterprise_code=args.enterprise_code,
        province=args.province,
        province_code=args.province_code,
        product_line_code=args.product_line_code,
        include_debug_features=args.include_debug_features,
    )
    response = DatabaseSmokeTestService(load_config()).run(request)
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
