import yaml, os

def load_sources(path="configs/sources.yaml") -> dict:
    if not os.path.exists(path):
        return {"sources": {}}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}