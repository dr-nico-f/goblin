import os
import pytest
import yaml
from goblin.config import load_sources


class TestLoadSources:
    def test_missing_file_returns_empty(self, tmp_path):
        result = load_sources(str(tmp_path / "nonexistent.yaml"))
        assert result == {"sources": {}}

    def test_loads_valid_yaml(self, tmp_path):
        path = tmp_path / "sources.yaml"
        data = {
            "sources": {
                "remotive": {"enabled": True, "limit": 25},
                "stub": {"enabled": False, "limit": 3},
            }
        }
        path.write_text(yaml.dump(data))
        result = load_sources(str(path))
        assert result["sources"]["remotive"]["limit"] == 25
        assert result["sources"]["stub"]["enabled"] is False

    def test_empty_file_returns_empty(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("")
        result = load_sources(str(path))
        assert result == {}
