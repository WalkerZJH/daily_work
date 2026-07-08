from __future__ import annotations

import importlib.util


def test_project_backend_no_longer_exposes_legacy_algorithms_package() -> None:
    assert importlib.util.find_spec("app.algorithms") is None
