from goblin.fetch import fetch_stub
from goblin.model import Job


class TestFetchStub:
    def test_returns_list_of_jobs(self):
        jobs = fetch_stub()
        assert isinstance(jobs, list)
        assert len(jobs) >= 1

    def test_jobs_are_job_instances(self):
        jobs = fetch_stub()
        for j in jobs:
            assert isinstance(j, Job)

    def test_all_required_fields_populated(self):
        for j in fetch_stub():
            assert j.id
            assert j.title
            assert j.company
            assert j.location
            assert j.url
            assert j.source == "stub"

    def test_stub_has_salary(self):
        jobs = fetch_stub()
        assert any(j.salary for j in jobs)

    def test_stub_has_tags(self):
        jobs = fetch_stub()
        assert any(j.tags for j in jobs)
