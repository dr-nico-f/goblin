import yaml, os

def load_profiles(path="configs/profiles.yaml") -> dict:
    if not os.path.exists(path):
        return {"profiles": {}}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def get_profile(name: str, path="configs/profiles.yaml") -> dict:
    return (load_profiles(path).get("profiles") or {}).get(name, {})


def get_profile_for_slack(
    user_id: str | None = None,
    channel_id: str | None = None,
    default: str = "nick",
    path: str = "configs/profiles.yaml",
) -> str:
    data = load_profiles(path)
    user_map = data.get("user_map") or {}
    channel_map = data.get("channel_map") or {}
    if user_id and user_id in user_map:
        return user_map[user_id]
    if channel_id and channel_id in channel_map:
        return channel_map[channel_id]
    return default