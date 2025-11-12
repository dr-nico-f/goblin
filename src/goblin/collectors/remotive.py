import httpx, time
from typing import List, Dict, Any
from goblin.model import Job

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
USER_AGENT = "GoblinJobBot/0.1 (+https://github.com/you/goblin)"

def _get_with_retries(url: str, params: Dict[str, Any], timeout=15, retries=3, backoff=0.75):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                return r
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < retries:
                time.sleep(backoff * attempt)  # simple backoff: 0.75s, 1.5s, 2.25s…
            else:
                raise
    raise last_exc  # should never reach

def fetch_remotive(query: str = "", category: str = "software-dev", limit: int = 25) -> List[Job]:
    params: Dict[str, Any] = {}
    if category: params["category"] = category
    if query:    params["search"] = query
    if limit:    params["limit"] = limit

    r = _get_with_retries(REMOTIVE_API, params=params)
    data = r.json()
    jobs_raw = data.get("jobs") or []
    print(f"[remotive] url={r.url} job-count={data.get('job-count')} returned={len(jobs_raw)}")

    jobs: List[Job] = []
    for item in jobs_raw[:limit]:
        description = (item.get("description") or "").strip()
        tags_raw = item.get("tags") or []
        tags = [t.strip() for t in tags_raw if isinstance(t, str) and t.strip()]

        jobs.append(
            Job(
                id=f"remotive-{item.get('id')}",
                title=(item.get("title") or "").strip(),
                company=(item.get("company_name") or "").strip(),
                location=(item.get("candidate_required_location") or "Remote").strip(),
                url=(item.get("url") or "").strip(),
                source="remotive",
                category=((item.get("category") or "").strip() or None),
                description=description or None,
                tags=tags,
                salary=((item.get("salary") or "").strip() or None),
                job_type=((item.get("job_type") or "").strip() or None),
                published_at=((item.get("publication_date") or "").strip() or None),
                company_logo=((item.get("company_logo_url") or "").strip() or None),
            )
        )
    return jobs