import json, os, hashlib
from typing import Set

CACHE_PATH = os.path.join("data", "posted.json")

def _ensure_dirs():
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

def _read() -> Set[str]:
    if not os.path.exists(CACHE_PATH):
        return set()
    try:
        with open(CACHE_PATH, "r") as f:
            data = json.load(f) or []
            return set(data)
    except Exception:
        return set()

def _write(ids: Set[str]) -> None:
    _ensure_dirs()
    with open(CACHE_PATH, "w") as f:
        json.dump(sorted(ids), f)

def fingerprint(title: str, company: str, url: str) -> str:
    """Stable ID across runs (source-agnostic)."""
    key = f"{title.strip().lower()}|{company.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

def load_seen() -> Set[str]:
    return _read()

def save_seen(seen: Set[str]) -> None:
    _write(seen)