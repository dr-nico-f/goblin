import os
import pytest
from goblin.model import Job


@pytest.fixture
def sample_job():
    """A typical remote Python job for testing."""
    return Job(
        id="test-1",
        title="Senior Backend Engineer (Python/AWS)",
        company="Acme Corp",
        location="Remote — United States",
        url="https://example.com/jobs/1",
        source="remotive",
        category="Software Development",
        tags=["python", "aws", "serverless"],
        salary="$140k – $170k",
        job_type="Full-time",
        published_at="2025-06-01T00:00:00",
    )


@pytest.fixture
def intern_job():
    return Job(
        id="test-2",
        title="Software Engineering Intern",
        company="BigCo",
        location="Onsite Only — New York",
        url="https://example.com/jobs/2",
        source="remotive",
    )


@pytest.fixture
def staff_job():
    return Job(
        id="test-3",
        title="Staff Platform Engineer",
        company="Cloud Nine",
        location="Remote — Anywhere",
        url="https://example.com/jobs/3",
        source="remotive",
        salary="$200k – $250k",
    )


@pytest.fixture
def no_salary_job():
    return Job(
        id="test-4",
        title="Backend Developer",
        company="Startup Inc",
        location="Remote",
        url="https://example.com/jobs/4",
        source="remotive",
    )


@pytest.fixture
def basic_filters():
    """A minimal but realistic filter config."""
    return {
        "titles": {
            "include": ["Engineer", "Developer"],
            "exclude": ["Intern", "Junior"],
        },
        "keywords": {
            "include": ["python", "aws"],
            "exclude": ["php"],
        },
        "locations": {
            "include": ["Remote", "USA", "United States"],
            "exclude": ["Onsite Only"],
        },
    }


@pytest.fixture
def salary_filters(basic_filters):
    """Filters with salary gating enabled."""
    return {**basic_filters, "salary": {"min": 120000, "allow_missing": False}}


@pytest.fixture
def default_weights():
    return {
        "keyword_hit": 1.0,
        "title_match": 0.8,
        "remote_bonus": 0.5,
        "senior_penalty": -0.6,
        "intern_penalty": -1.0,
    }


@pytest.fixture
def tmp_cache(tmp_path):
    """Return a path inside a temp dir for dedup cache testing."""
    return str(tmp_path / "profile" / "posted.json")


@pytest.fixture
def profiles_yaml(tmp_path):
    """Write a temporary profiles.yaml and return its path."""
    content = """
profiles:
  alice:
    channel: "C1234567890"
    filters: "configs/filters.yaml"
    ranking: "configs/ranking.yaml"
  bob:
    channel: "C0987654321"
    filters: "configs/filters_bob.yaml"
    ranking: "configs/ranking_bob.yaml"

user_map:
  U111: alice
  U222: bob

channel_map:
  C999: alice
"""
    path = tmp_path / "profiles.yaml"
    path.write_text(content)
    return str(path)


@pytest.fixture(autouse=True)
def _clear_dynamo_env(monkeypatch):
    """Ensure DynamoDB env vars are unset so tests use local fallback."""
    monkeypatch.delenv("GOBLIN_FILTERS_TABLE", raising=False)
    monkeypatch.delenv("GOBLIN_FILTERS_PK", raising=False)
