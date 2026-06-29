from __future__ import annotations

from alg.artifacts.hashing import hash_dict


def test_fact_cache_key_excludes_cutoff_horizon_status():
    key_a = hash_dict(
        {
            "artifact": "fact_purchase_event",
            "drug_group_source": "drug_code",
            "model_base_hash": "same",
            "builder_version": "v1",
        }
    )
    key_b = hash_dict(
        {
            "artifact": "fact_purchase_event",
            "drug_group_source": "drug_code",
            "model_base_hash": "same",
            "builder_version": "v1",
        }
    )
    assert key_a == key_b


def test_feature_cache_key_can_include_cutoff_and_status():
    key_a = hash_dict({"artifact": "feature_table", "cutoff_start": "2024-01", "include_status_history": False})
    key_b = hash_dict({"artifact": "feature_table", "cutoff_start": "2024-10", "include_status_history": False})
    key_c = hash_dict({"artifact": "feature_table", "cutoff_start": "2024-01", "include_status_history": True})
    assert key_a != key_b
    assert key_a != key_c
