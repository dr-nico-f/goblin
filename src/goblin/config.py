import os

import yaml


def load_sources(path="configs/sources.yaml") -> dict:
    if not os.path.exists(path):
        return {"sources": {}}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
