
from alg.artifacts.manifest import REQUIRED_MANIFEST_FILES, missing_required_files


def test_manifest_required_files_are_declared():
    assert "model.skops" in REQUIRED_MANIFEST_FILES
    assert "feature_schema.json" in REQUIRED_MANIFEST_FILES
    assert "manifest.json" in REQUIRED_MANIFEST_FILES


def test_missing_required_files():
    missing = missing_required_files({"model.skops", "manifest.json"})
    assert "feature_schema.json" in missing
    assert "model.skops" not in missing
