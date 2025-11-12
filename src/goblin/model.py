from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    source: str = "stub"
    category: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    salary: Optional[str] = None
    job_type: Optional[str] = None
    published_at: Optional[str] = None
    company_logo: Optional[str] = None