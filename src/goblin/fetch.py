from time import strftime
from typing import List
from goblin.model import Job

def fetch_stub() -> List[Job]:
    today = strftime("%Y-%m-%d")
    return [
        Job(
            id="stub-1",
            title="Backend Software Engineer (Python/AWS)",
            company="Orbital Co",
            location="Remote — United States",
            url="https://example.com/jobs/1",
            source="stub",
            description="Work with a small platform team shipping cloud-native tooling.",
            tags=["python", "aws", "serverless"],
            salary="$140k – $170k",
            job_type="Full-time",
            published_at=today,
        ),
        Job(
            id="stub-2",
            title="Principal Platform Engineer",
            company="Monocle Inc",
            location="Onsite Only — Texas",
            url="https://example.com/jobs/2",
            source="stub",
            description="Lead modernization of critical infrastructure and mentor engineers.",
            tags=["platform", "kubernetes"],
            salary="$180k – $210k",
            job_type="Full-time",
            published_at=today,
        ),
    ]