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
        ),
        Job(
            id="stub-2",
            title="Principal Platform Engineer",
            company="Monocle Inc",
            location="Onsite Only — Texas",
            url="https://example.com/jobs/2",
            source="stub",
        ),
    ]