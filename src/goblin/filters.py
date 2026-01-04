import re
import yaml
from goblin.model import Job


def _parse_salary_to_int(raw: str) -> int | None:
    """
    Parse a salary string and return the lower bound as an int (USD-like).
    Examples handled: "$140k – $170k", "140,000-170,000", "$120k", "120000".
    Returns None if no numeric value can be parsed.
    """
    if not raw:
        return None

    # Split on common separators (dash, en dash, "to")
    parts = re.split(r"[–-]|to", raw, flags=re.IGNORECASE)
    nums = []
    for part in parts:
        match = re.search(r"([\d][\d,\.]*)(k)?", part, flags=re.IGNORECASE)
        if not match:
            continue
        val = float(match.group(1).replace(",", ""))
        if match.group(2):  # has 'k'
            val *= 1000
        nums.append(int(val))

    return min(nums) if nums else None

def load_filters(path="configs/filters.yaml") -> dict:
    """Load filter config from YAML."""
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def matches(job: Job, filters: dict) -> bool:
    titles_cfg = filters.get("titles", {}) or {}
    keywords_cfg = filters.get("keywords", {}) or {}
    locations_cfg = filters.get("locations", {}) or {}
    salary_cfg = filters.get("salary", {}) or {}

    ti = [t.lower() for t in titles_cfg.get("include", [])]
    te = [t.lower() for t in titles_cfg.get("exclude", [])]
    ki = [k.lower() for k in keywords_cfg.get("include", [])]
    ke = [k.lower() for k in keywords_cfg.get("exclude", [])]
    li = [l.lower() for l in locations_cfg.get("include", [])]
    le = [l.lower() for l in locations_cfg.get("exclude", [])]

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

    # Salary minimum (uses lower bound of range if provided)
    min_salary = salary_cfg.get("min")
    allow_missing_salary = bool(salary_cfg.get("allow_missing", False))
    if min_salary is not None:
        low = _parse_salary_to_int(getattr(job, "salary", None))
        if low is None and not allow_missing_salary:
            return False
        if low is not None and low < float(min_salary):
            return False

    return True