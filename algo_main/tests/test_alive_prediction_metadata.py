from __future__ import annotations

import pandas as pd

from alg.artifacts.hashing import hash_dataframe_schema, hash_dict
from alg.artifacts.manifest import read_manifest, update_manifest
from alg.artifacts.metadata import build_artifact_metadata, read_metadata, write_metadata


def test_metadata_write_and_read_roundtrip(tmp_path):
    path = tmp_path / "artifact.parquet"
    df = pd.DataFrame({"a": [1], "b": ["x"]})
    df.to_parquet(path, index=False)
    metadata = build_artifact_metadata(
        artifact_name="feature_table",
        artifact_type="features",
        df=df,
        source_hashes={"source": "abc"},
    )
    write_metadata(path, metadata)
    loaded = read_metadata(path)
    assert loaded["artifact_name"] == "feature_table"
    assert loaded["row_count"] == 1
    assert loaded["source_hashes"]["source"] == "abc"


def test_manifest_records_artifact_path_row_count_and_source_hash(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    update_manifest(
        manifest_path,
        {
            "artifact_name": "feature_table",
            "path": "data/05_features/x.parquet",
            "row_count": 3,
            "source_hash": "hash",
        },
    )
    manifest = read_manifest(manifest_path)
    assert manifest["artifacts"][0]["row_count"] == 3
    assert manifest["artifacts"][0]["source_hash"] == "hash"


def test_hash_helpers_are_stable_for_dict_and_schema():
    assert hash_dict({"b": 2, "a": 1}) == hash_dict({"a": 1, "b": 2})
    df = pd.DataFrame({"a": [1]})
    assert hash_dataframe_schema(df) == hash_dataframe_schema(df.copy())
