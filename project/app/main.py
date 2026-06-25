from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_backbone import router as backbone_router
from app.api.routes_backtest import router as backtest_router
from app.api.routes_config import router as config_router
from app.api.routes_detectors import router as detectors_router
from app.api.routes_debug import router as debug_router
from app.api.routes_health import router as health_router
from app.api.routes_inspection import router as inspection_router
from app.api.routes_options import router as options_router
from app.api.routes_smoke_test import router as smoke_test_router
from app.api.routes_training import router as training_router
from app.api.routes_users import router as users_router
from app.core.errors import TerminalGuardError
from app.core.logging import configure_logging

configure_logging(os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="supply_chain_order_risk_algo_backend",
    version="0.1.0",
    description="Supply chain order risk algorithm validation backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, object]:
    return {
        "service": "supply_chain_order_risk_algo_backend",
        "legacy_service_name": "terminal_guard_algo_backend",
        "status": "ok",
        "message": "Backend API is running. Use /docs for Swagger UI or /health for health check.",
        "links": {
            "health": "/health",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "dry_run": "/api/v0/inspection/dry-run",
            "debug_detectors": "/api/v0/debug/detectors",
            "debug_preprocess": "/api/v0/debug/preprocess/run",
            "debug_feature_example": "/api/v0/debug/features/ORG_A/product_line/PL_A?as_of_date=2025-12-31&dataset_name=sample",
        },
    }


@app.exception_handler(TerminalGuardError)
async def terminal_guard_error_handler(_: Request, exc: TerminalGuardError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.include_router(health_router)
app.include_router(detectors_router)
app.include_router(users_router)
app.include_router(debug_router)
app.include_router(inspection_router)
app.include_router(backbone_router)
app.include_router(training_router)
app.include_router(smoke_test_router)
app.include_router(backtest_router)
app.include_router(config_router)
app.include_router(options_router)
