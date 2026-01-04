from typing import Dict
from goblin.model import Job
import yaml
from goblin.filter_store import load_profile_ranking

def load_weights(path="configs/ranking.yaml") -> Dict[str, float]:
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    return (data.get("weights") or {})


def load_profile_weights(profile: str, fallback_path="configs/ranking.yaml") -> Dict[str, float]:
    data = load_profile_ranking(profile, fallback_path) or {}
    return data.get("weights") or data or {}

REMOTE_SYNS = ("remote", "anywhere", "worldwide", "global")

def score(job: Job, filters: dict, weights: Dict[str, float]) -> float:
    w = lambda k, d=0.0: float(weights.get(k, d))
    title = job.title.lower()
    company = job.company.lower()
    loc = job.location.lower()
    text = f"{job.title} {job.company}".lower()

    s = 0.0

    # keywords.include hits
    for k in (filters.get("keywords", {}).get("include") or []):
        if k.lower() in text:
            s += w("keyword_hit", 1.0)

    # title include hit
    ti = [t.lower() for t in (filters.get("titles", {}).get("include") or [])]
    if any(t in title for t in ti):
        s += w("title_match", 0.8)

    # remote-ish bonus
    if any(syn in loc for syn in REMOTE_SYNS):
        s += w("remote_bonus", 0.5)

    # seniority penalties
    if "staff" in title or "principal" in title:
        s += w("senior_penalty", -0.6)
    if "intern" in title:
        s += w("intern_penalty", -1.0)

    return round(s, 3)