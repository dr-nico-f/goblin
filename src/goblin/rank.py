from datetime import datetime, timezone
from typing import Dict

import yaml

from goblin.filter_store import load_profile_ranking
from goblin.model import Job


def load_weights(path="configs/ranking.yaml") -> Dict[str, float]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("weights") or {}


def load_profile_weights(profile: str, fallback_path="configs/ranking.yaml") -> Dict[str, float]:
    data = load_profile_ranking(profile, fallback_path) or {}
    return data.get("weights") or data or {}


REMOTE_SYNS = ("remote", "anywhere", "worldwide", "global")

RECENCY_THRESHOLD_DAYS = 7


def _parse_published_age_days(published_at: str | None) -> int | None:
    if not published_at:
        return None
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return max(delta.days, 0)
    except (ValueError, TypeError):
        return None


def _parse_salary_lower(salary: str | None) -> int | None:
    if not salary:
        return None
    import re
    parts = re.split(r"[–\-]|to", salary, flags=re.IGNORECASE)
    nums = []
    for part in parts:
        match = re.search(r"([\d][\d,\.]*)(k)?", part, flags=re.IGNORECASE)
        if not match:
            continue
        val = float(match.group(1).replace(",", ""))
        if match.group(2):
            val *= 1000
        nums.append(int(val))
    return min(nums) if nums else None


def score(job: Job, filters: dict, weights: Dict[str, float]) -> float:
    w = lambda k, d=0.0: float(weights.get(k, d))
    title = job.title.lower()
    loc = job.location.lower()
    text = f"{job.title} {job.company}".lower()
    desc = (getattr(job, "description", None) or "").lower()
    tags = [t.lower() for t in (getattr(job, "tags", None) or [])]

    s = 0.0

    ki = [k.lower() for k in (filters.get("keywords", {}).get("include") or [])]

    # Keyword hits in title + company
    for k in ki:
        if k in text:
            s += w("keyword_hit", 1.0)

    # Title include hits (per matching term, not binary)
    ti = [t.lower() for t in (filters.get("titles", {}).get("include") or [])]
    for t in ti:
        if t in title:
            s += w("title_hit", 0.3)

    # Keyword hits in job description (lower weight, avoids double-counting)
    seen_in_text = set()
    for k in ki:
        if k in desc and k not in text:
            seen_in_text.add(k)
            s += w("description_hit", 0.3)

    # Tag overlap with keyword includes
    for tag in tags:
        if tag in ki and tag not in text:
            s += w("tag_hit", 0.2)

    # Remote bonus
    if any(syn in loc for syn in REMOTE_SYNS):
        s += w("remote_bonus", 0.5)

    # Salary bonus: reward jobs well above the filter minimum
    salary_min = (filters.get("salary", {}) or {}).get("min")
    job_salary = _parse_salary_lower(getattr(job, "salary", None))
    if salary_min and job_salary and job_salary > float(salary_min):
        tiers = (job_salary - float(salary_min)) / 10_000
        s += w("salary_bonus", 0.1) * min(tiers, 5)

    # Recency bonus: published within the last N days
    age_days = _parse_published_age_days(getattr(job, "published_at", None))
    if age_days is not None and age_days <= RECENCY_THRESHOLD_DAYS:
        s += w("recency_bonus", 0.4)

    # Seniority penalties
    if "staff" in title or "principal" in title:
        s += w("senior_penalty", -0.6)
    if "intern" in title:
        s += w("intern_penalty", -1.0)

    return round(s, 3)
