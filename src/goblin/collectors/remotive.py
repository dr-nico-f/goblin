import httpx
from typing import List, Dict, Any
from goblin.model import Job

REMOTIVE_API = "https://remotive.com/api/remote-jobs"  # docs: https://remotive.com/remote-jobs/api

def fetch_remotive(query: str = "", category: str = "software-dev", limit: int = 25) -> List[Job]:
    params: Dict[str, Any] = {}
    if category:
        params["category"] = category
    if query:
        params["search"] = query
    if limit:
        params["limit"] = limit

    with httpx.Client(timeout=15) as client:
        r = client.get(REMOTIVE_API, params=params)
        r.raise_for_status()
        data = r.json()
        jobs_raw = data.get("jobs") or []
        # debug:
        print(f"[remotive] url={r.url} job-count={data.get('job-count')} returned={len(jobs_raw)}")

        jobs: List[Job] = []
        for item in jobs_raw[:limit]:
            jobs.append(
                Job(
                    id=f"remotive-{item.get('id')}",
                    title=(item.get("title") or "").strip(),
                    company=(item.get("company_name") or "").strip(),
                    location=(item.get("candidate_required_location") or "Remote").strip(),
                    url=(item.get("url") or "").strip(),
                    source="remotive",
                )
            )
        return jobs