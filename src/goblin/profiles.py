import yaml, os

def load_profiles(path="configs/profiles.yaml") -> dict:
    if not os.path.exists(path):
        return {"profiles": {}}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def get_profile(name: str, path="configs/profiles.yaml") -> dict:
    return (load_profiles(path).get("profiles") or {}).get(name, {})