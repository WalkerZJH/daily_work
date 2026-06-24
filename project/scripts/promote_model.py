from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from app.core.config import PROJECT_ROOT


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default="palive_lgbm")
    parser.add_argument("--version", required=True)
    parser.add_argument("--registry", default="configs/model_registry.yaml")
    args = parser.parse_args()
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = PROJECT_ROOT / registry_path
    with registry_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    raw.setdefault("models", {}).setdefault(args.model_name, {})["active_version"] = args.version
    raw["active_backbone"] = args.model_name
    with registry_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(raw, file, allow_unicode=True, sort_keys=False)
    print(f"{args.model_name} active_version={args.version}")


if __name__ == "__main__":
    main()
