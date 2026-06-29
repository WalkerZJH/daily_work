#!/usr/bin/env python
"""Guarded cleanup for alive prediction temporary cache.

Default is dry-run. Cleanup is restricted to data/cache/alive_prediction/tmp.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from alg.cache.cleanup import clean_cache


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run or clean alive prediction tmp cache.")
    parser.add_argument("--cache-root", default="data/cache/alive_prediction/tmp")
    parser.add_argument("--older-than-days", type=int, default=None)
    parser.add_argument("--keep-latest", action="store_true")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--confirm", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    cache_root = root / args.cache_root
    candidates = clean_cache(
        cache_root,
        older_than_days=args.older_than_days,
        keep_latest=args.keep_latest,
        dry_run=args.dry_run,
        confirm=args.confirm,
    )
    print("candidate_file_path,artifact_name,created_at,size,reason_for_cleanup")
    for candidate in candidates:
        print(
            f"{candidate.path},{candidate.artifact_name},{candidate.created_at},"
            f"{candidate.size},{candidate.reason_for_cleanup}"
        )
    if args.dry_run or not args.confirm:
        print("[cleanup] dry-run only; no files deleted", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
