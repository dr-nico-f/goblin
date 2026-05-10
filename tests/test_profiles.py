import pytest
from goblin.profiles import load_profiles, get_profile, get_profile_for_slack


class TestLoadProfiles:
    def test_missing_file(self, tmp_path):
        result = load_profiles(str(tmp_path / "nope.yaml"))
        assert result == {"profiles": {}}

    def test_loads_profiles(self, profiles_yaml):
        result = load_profiles(profiles_yaml)
        assert "alice" in result["profiles"]
        assert "bob" in result["profiles"]

    def test_loads_user_map(self, profiles_yaml):
        result = load_profiles(profiles_yaml)
        assert result["user_map"]["U111"] == "alice"


class TestGetProfile:
    def test_existing_profile(self, profiles_yaml):
        prof = get_profile("alice", path=profiles_yaml)
        assert prof["channel"] == "C1234567890"

    def test_missing_profile_returns_empty(self, profiles_yaml):
        prof = get_profile("unknown", path=profiles_yaml)
        assert prof == {}

    def test_profile_has_config_paths(self, profiles_yaml):
        prof = get_profile("bob", path=profiles_yaml)
        assert "filters" in prof
        assert "ranking" in prof


class TestGetProfileForSlack:
    def test_user_map_lookup(self, profiles_yaml):
        result = get_profile_for_slack(
            user_id="U111", path=profiles_yaml,
        )
        assert result == "alice"

    def test_channel_map_lookup(self, profiles_yaml):
        result = get_profile_for_slack(
            channel_id="C999", path=profiles_yaml,
        )
        assert result == "alice"

    def test_user_map_takes_priority(self, profiles_yaml):
        result = get_profile_for_slack(
            user_id="U222", channel_id="C999", path=profiles_yaml,
        )
        assert result == "bob"

    def test_falls_back_to_default(self, profiles_yaml):
        result = get_profile_for_slack(
            user_id="UNKNOWN", default="fallback", path=profiles_yaml,
        )
        assert result == "fallback"

    def test_none_ids_use_default(self, profiles_yaml):
        result = get_profile_for_slack(
            user_id=None, channel_id=None, default="nick",
            path=profiles_yaml,
        )
        assert result == "nick"
