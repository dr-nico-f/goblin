import os
import yaml
import pytest
from goblin.filter_store import (
    load_profile_filters,
    save_profile_filters,
    load_profile_ranking,
    save_profile_ranking,
    _load_local,
    _save_local,
)


class TestLocalFallback:
    def test_load_missing_file(self, tmp_path):
        result = _load_local(str(tmp_path / "nope.yaml"))
        assert result == {}

    def test_load_none_path(self):
        assert _load_local(None) == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "filters.yaml")
        data = {"titles": {"include": ["Engineer"]}}
        _save_local(path, data)
        loaded = _load_local(path)
        assert loaded == data

    def test_save_creates_directories(self, tmp_path):
        path = str(tmp_path / "nested" / "dir" / "filters.yaml")
        _save_local(path, {"test": True})
        assert os.path.exists(path)

    def test_save_none_path_raises(self):
        with pytest.raises(RuntimeError, match="No local path"):
            _save_local(None, {})


class TestLoadProfileFilters:
    def test_falls_back_to_local(self, tmp_path):
        path = tmp_path / "filters.yaml"
        data = {"titles": {"include": ["Developer"]}}
        path.write_text(yaml.dump(data))
        result = load_profile_filters("testuser", str(path))
        assert result == data

    def test_fallback_missing_returns_empty(self, tmp_path):
        result = load_profile_filters("testuser", str(tmp_path / "nope.yaml"))
        assert result == {}


class TestSaveProfileFilters:
    def test_saves_locally_without_dynamo(self, tmp_path):
        path = str(tmp_path / "filters.yaml")
        data = {"salary": {"min": 100000}}
        save_profile_filters("testuser", data, path)
        loaded = _load_local(path)
        assert loaded == data


class TestLoadProfileRanking:
    def test_falls_back_to_local(self, tmp_path):
        path = tmp_path / "ranking.yaml"
        data = {"weights": {"keyword_hit": 1.5}}
        path.write_text(yaml.dump(data))
        result = load_profile_ranking("testuser", str(path))
        assert result == data


class TestSaveProfileRanking:
    def test_saves_locally_without_dynamo(self, tmp_path):
        path = str(tmp_path / "ranking.yaml")
        data = {"weights": {"keyword_hit": 2.0}}
        save_profile_ranking("testuser", data, path)
        loaded = _load_local(path)
        assert loaded == data
