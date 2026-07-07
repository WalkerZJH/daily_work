"""Visibility markers for MVC risk result packages."""

from __future__ import annotations


INTERNAL_ONLY = "internal_only"
ANALYST_VISIBLE = "analyst_visible"
CUSTOMER_VISIBLE = "customer_visible"


def internal_full_dump_manifest() -> dict[str, object]:
    return {
        "package_scope": "internal_full_status_package",
        "visibility": INTERNAL_ONLY,
        "not_for_frontend_default": True,
        "frontend_default_allowed": False,
        "customer_visible_allowed": False,
        "auto_dispatch_allowed": False,
        "caveat": "Broad row-level status dump retained only for audit/debug; frontend must use bounded worklist package.",
    }

