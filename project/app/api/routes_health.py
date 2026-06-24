from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "supply_chain_order_risk_algo_backend",
        "legacy_service_name": "terminal_guard_algo_backend",
    }
