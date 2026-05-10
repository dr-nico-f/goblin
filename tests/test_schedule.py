import pytest
from goblin.schedule import _normalize_cron, ScheduleError


class TestNormalizeCron:
    def test_already_wrapped(self):
        assert _normalize_cron("cron(0 14 * * ? *)") == "cron(0 14 * * ? *)"

    def test_wraps_six_field(self):
        assert _normalize_cron("0 14 * * ? *") == "cron(0 14 * * ? *)"

    def test_wraps_five_field(self):
        assert _normalize_cron("0 14 * * ?") == "cron(0 14 * * ?)"

    def test_strips_whitespace(self):
        assert _normalize_cron("  cron(0 14 * * ? *)  ") == "cron(0 14 * * ? *)"

    def test_invalid_field_count_raises(self):
        with pytest.raises(ScheduleError, match="5 or 6 fields"):
            _normalize_cron("0 14 *")

    def test_single_field_raises(self):
        with pytest.raises(ScheduleError):
            _normalize_cron("daily")
