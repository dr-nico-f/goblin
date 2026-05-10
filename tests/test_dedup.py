import json
import os

import pytest
from goblin.dedup import fingerprint, load_seen, save_seen, cache_file


class TestFingerprint:
    def test_deterministic(self):
        fp1 = fingerprint("Eng", "Co", "http://x")
        fp2 = fingerprint("Eng", "Co", "http://x")
        assert fp1 == fp2

    def test_different_inputs_differ(self):
        fp1 = fingerprint("Eng A", "Co", "http://x")
        fp2 = fingerprint("Eng B", "Co", "http://x")
        assert fp1 != fp2

    def test_case_insensitive(self):
        fp1 = fingerprint("Engineer", "ACME", "http://X")
        fp2 = fingerprint("engineer", "acme", "http://x")
        assert fp1 == fp2

    def test_strips_whitespace(self):
        fp1 = fingerprint("  Eng  ", " Co ", " http://x ")
        fp2 = fingerprint("Eng", "Co", "http://x")
        assert fp1 == fp2

    def test_length(self):
        fp = fingerprint("Eng", "Co", "http://x")
        assert len(fp) == 16

    def test_hex_characters(self):
        fp = fingerprint("Eng", "Co", "http://x")
        assert all(c in "0123456789abcdef" for c in fp)


class TestLoadSaveSeen:
    def test_load_missing_file(self, tmp_cache):
        seen = load_seen(tmp_cache)
        assert seen == set()

    def test_save_and_load_roundtrip(self, tmp_cache):
        ids = {"abc123", "def456", "ghi789"}
        save_seen(tmp_cache, ids)
        loaded = load_seen(tmp_cache)
        assert loaded == ids

    def test_save_creates_directories(self, tmp_path):
        path = str(tmp_path / "deep" / "nested" / "cache.json")
        save_seen(path, {"test"})
        assert os.path.exists(path)

    def test_load_corrupt_json_returns_empty(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("{not valid json")
        assert load_seen(path) == set()

    def test_empty_save_and_load(self, tmp_cache):
        save_seen(tmp_cache, set())
        loaded = load_seen(tmp_cache)
        assert loaded == set()

    def test_saved_json_is_sorted(self, tmp_cache):
        save_seen(tmp_cache, {"c", "a", "b"})
        with open(tmp_cache) as f:
            data = json.load(f)
        assert data == ["a", "b", "c"]


class TestCacheFile:
    def test_default_base(self, monkeypatch):
        monkeypatch.delenv("GOBLIN_CACHE_DIR", raising=False)
        path = cache_file("alice")
        assert path == os.path.join("data", "alice", "posted.json")

    def test_custom_base(self, monkeypatch):
        monkeypatch.setenv("GOBLIN_CACHE_DIR", "/tmp/goblin")
        path = cache_file("bob")
        assert path == "/tmp/goblin/bob/posted.json"

    def test_profile_isolation(self, monkeypatch):
        monkeypatch.delenv("GOBLIN_CACHE_DIR", raising=False)
        assert cache_file("alice") != cache_file("bob")
