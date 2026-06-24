from __future__ import annotations

import argparse

from app.core.config import load_config
from app.schemas.api import DatabaseSmokeTestRequest
from app.services.database_smoke_test_service import DatabaseSmokeTestService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--row-limit", type=int, default=5000)
    parser.add_argument("--enterprise-code", default=None)
    parser.add_argument("--province", default=None)
    parser.add_argument("--province-code", default=None)
    parser.add_argument("--no-debug-features", action="store_true")
    args = parser.parse_args()

    request = DatabaseSmokeTestRequest(
        as_of_date=args.as_of_date,
        days=args.days,
        row_limit=args.row_limit,
        enterprise_code=args.enterprise_code,
        province=args.province,
        province_code=args.province_code,
        include_debug_features=not args.no_debug_features,
    )
    response = DatabaseSmokeTestService(load_config()).run(request)
    print(response.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
