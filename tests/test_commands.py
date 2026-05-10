import pytest
from goblin.commands import (
    handle_command,
    command_help,
    _cron_to_text,
    _parse_bool,
    _display_profile,
    _fmt_list,
    _format_salary_info,
    _get_profile_name,
    CommandResult,
)


class TestHandleCommandRouting:
    def test_empty_returns_help(self):
        result = handle_command("")
        assert result.status == 200
        assert "help" in result.text.lower()

    def test_help_command(self):
        result = handle_command("help")
        assert result.status == 200
        assert result.blocks is not None

    def test_help_aliases(self):
        for alias in ("h", "?", "Help", "HELP"):
            result = handle_command(alias)
            assert result.status == 200

    def test_unknown_command(self):
        result = handle_command("foobar")
        assert result.status == 400
        assert "Unknown command" in result.text

    def test_filters_unknown_subcommand(self):
        result = handle_command("filters unknown")
        assert result.status == 400

    def test_ranking_unknown_subcommand(self):
        result = handle_command("ranking unknown")
        assert result.status == 400

    def test_schedule_unknown_subcommand(self):
        result = handle_command("schedule unknown")
        assert result.status == 400

    def test_ranking_set_missing_args(self):
        result = handle_command("ranking set")
        assert result.status == 400
        assert "Usage" in result.text

    def test_ranking_set_non_numeric(self):
        result = handle_command("ranking set keyword_hit abc")
        assert result.status == 400

    def test_filters_set_salary_missing_args(self):
        result = handle_command("filters set salary")
        assert result.status == 400


class TestCronToText:
    def test_every_day_at_fixed_time(self):
        text = _cron_to_text("cron(0 14 * * ? *)")
        assert "ET" in text
        assert "every day" in text

    def test_every_minute(self):
        text = _cron_to_text("* * * * ?")
        assert "every minute" in text

    def test_step_minutes(self):
        text = _cron_to_text("*/15 * * * ?")
        assert "15 minutes" in text

    def test_hourly(self):
        text = _cron_to_text("0 * * * ?")
        assert "every hour" in text

    def test_step_hours(self):
        text = _cron_to_text("0 */2 * * ?")
        assert "2 hours" in text

    def test_specific_weekdays(self):
        text = _cron_to_text("0 14 ? * MON-FRI *")
        assert "Mon" in text
        assert "Fri" in text

    def test_invalid_field_count_returns_raw(self):
        text = _cron_to_text("bad")
        assert text == "bad"

    def test_strips_cron_wrapper(self):
        text = _cron_to_text("cron(0 14 * * ? *)")
        assert "cron(" not in text


class TestParseBool:
    @pytest.mark.parametrize("val", ["true", "True", "TRUE", "1", "yes", "y", "on"])
    def test_truthy_values(self, val):
        assert _parse_bool(val) is True

    @pytest.mark.parametrize("val", ["false", "False", "0", "no", "n", "off", ""])
    def test_falsy_values(self, val):
        assert _parse_bool(val) is False


class TestDisplayProfile:
    def test_capitalizes(self):
        assert _display_profile("nick") == "Nick"

    def test_already_capitalized(self):
        assert _display_profile("Nick") == "Nick"


class TestFmtList:
    def test_with_items(self):
        assert _fmt_list("Title", ["a", "b"]) == "*Title*: a, b"

    def test_empty(self):
        assert _fmt_list("Title", []) == "*Title*: (none)"


class TestFormatSalaryInfo:
    def test_no_salary(self):
        assert "not set" in _format_salary_info({})

    def test_with_salary(self):
        text = _format_salary_info({"salary": {"min": 150000, "allow_missing": False}})
        assert "$150,000" in text
        assert "allow_missing=False" in text


class TestGetProfileName:
    def test_explicit_flag(self):
        assert _get_profile_name(["--profile", "bob"]) == "bob"

    def test_default_when_no_flag(self):
        name = _get_profile_name([], default="nick")
        assert name == "nick"

    def test_flag_at_end(self):
        assert _get_profile_name(["--limit", "5", "--profile", "alice"]) == "alice"


class TestCommandResult:
    def test_defaults(self):
        r = CommandResult(text="hi")
        assert r.status == 200
        assert r.blocks is None

    def test_custom_status(self):
        r = CommandResult(text="err", status=400)
        assert r.status == 400
