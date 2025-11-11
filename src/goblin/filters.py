import yaml
from goblin.model import Job

def load_filters(path="configs/filters.yaml") -> dict:
    """Load filter config from YAML."""
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def matches(job: Job, filters: dict) -> bool:
    ti = [t.lower() for t in filters["titles"]["include"]]
    te = [t.lower() for t in filters["titles"]["exclude"]]
    ki = [k.lower() for k in filters["keywords"]["include"]]
    ke = [k.lower() for k in filters["keywords"]["exclude"]]
    li = [l.lower() for l in filters["locations"]["include"]]
    le = [l.lower() for l in filters["locations"]["exclude"]]

    title = job.title.lower()
    loc   = job.location.lower()
    text  = f"{job.title} {job.company}".lower()

    # Title must NOT hit excluded terms
    if any(t in title for t in te):
        return False

    # Title include OR keyword include (not both required)
    title_ok = (not ti) or any(t in title for t in ti)
    keyword_ok = (not ki) or any(k in text for k in ki)
    if not (title_ok or keyword_ok):
        return False

    # Keywords must NOT hit excluded
    if any(k in text for k in ke):
        return False

    # Location: support common remote synonyms if "remote" is allowed
    remote_syns = ["remote", "anywhere", "global", "worldwide"]
    if any(l in loc for l in le):
        return False
    if li:
        if "remote" in li and any(s in loc for s in remote_syns):
            pass  # accept
        elif not any(l in loc for l in li):
            return False

    return True