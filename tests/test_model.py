from goblin.model import Job


class TestJobDataclass:
    def test_required_fields(self):
        j = Job(id="1", title="Eng", company="Co", location="NYC", url="http://x")
        assert j.id == "1"
        assert j.title == "Eng"
        assert j.company == "Co"
        assert j.location == "NYC"
        assert j.url == "http://x"

    def test_defaults(self):
        j = Job(id="1", title="Eng", company="Co", location="NYC", url="http://x")
        assert j.source == "stub"
        assert j.category is None
        assert j.description is None
        assert j.tags == []
        assert j.salary is None
        assert j.job_type is None
        assert j.published_at is None
        assert j.company_logo is None

    def test_optional_fields(self):
        j = Job(
            id="1",
            title="Eng",
            company="Co",
            location="Remote",
            url="http://x",
            source="remotive",
            category="Software Development",
            tags=["python", "aws"],
            salary="$100k – $150k",
            job_type="Full-time",
            published_at="2025-01-01",
            company_logo="https://logo.png",
        )
        assert j.source == "remotive"
        assert j.tags == ["python", "aws"]
        assert j.salary == "$100k – $150k"

    def test_equality(self):
        args = dict(id="1", title="Eng", company="Co", location="NYC", url="http://x")
        assert Job(**args) == Job(**args)

    def test_inequality_different_id(self):
        base = dict(title="Eng", company="Co", location="NYC", url="http://x")
        assert Job(id="1", **base) != Job(id="2", **base)
