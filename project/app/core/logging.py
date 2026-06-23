from __future__ import annotations

import logging
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def log_inspection_summary(logger: logging.Logger, payload: dict[str, Any]) -> None:
    logger.info("inspection_summary", extra={"inspection_summary": payload})
