import json, os, hashlib
from typing import Set

def _ensure_dirs(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)

def _read(path: str) -> Set[str]:
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r") as f:
            data = json.load(f) or []
            return set(data)
    except Exception:
        return set()

def _write(path: str, ids: Set[str]) -> None:
    _ensure_dirs(path)
    with open(path, "w") as f:
        json.dump(sorted(ids), f)

def fingerprint(title: str, company: str, url: str) -> str:
    key = f"{title.strip().lower()}|{company.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

def load_seen(cache_path: str) -> Set[str]:
    return _read(cache_path)

def save_seen(cache_path: str, seen: Set[str]) -> None:
    _write(cache_path, seen)

# NEW: build a writable cache file path based on env
def cache_file(profile: str) -> str:
    base = os.environ.get("GOBLIN_CACHE_DIR", "data")  # "data" locally, "/tmp/goblin" on Lambda
    return os.path.join(base, profile, "posted.json")