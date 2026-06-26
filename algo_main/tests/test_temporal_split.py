
from datetime import date

from alg.validation.temporal_split import make_holdout_window


def test_holdout_window_prevents_time_leakage():
    window = make_holdout_window(date(2026, 6, 30), horizon_months=3)
    assert window.feature_end_date == date(2026, 6, 30)
    assert window.label_start_date > window.feature_end_date
    assert window.label_end_date > window.label_start_date
