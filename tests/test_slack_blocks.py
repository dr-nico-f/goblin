from goblin.model import Job
from goblin.slack import job_to_blocks


class TestJobToBlocks:
    def test_returns_list_of_blocks(self, sample_job):
        blocks = job_to_blocks(sample_job)
        assert isinstance(blocks, list)
        assert len(blocks) >= 1

    def test_block_is_section_type(self, sample_job):
        blocks = job_to_blocks(sample_job)
        assert blocks[0]["type"] == "section"

    def test_contains_title_and_company(self, sample_job):
        blocks = job_to_blocks(sample_job)
        text = blocks[0]["text"]["text"]
        assert sample_job.title in text
        assert sample_job.company in text

    def test_contains_url_link(self, sample_job):
        blocks = job_to_blocks(sample_job)
        text = blocks[0]["text"]["text"]
        assert sample_job.url in text

    def test_score_included_when_provided(self, sample_job):
        blocks = job_to_blocks(sample_job, score=8.5)
        text = blocks[0]["text"]["text"]
        assert "8.5" in text
        assert "Score:" in text

    def test_score_omitted_when_none(self, sample_job):
        blocks = job_to_blocks(sample_job, score=None)
        text = blocks[0]["text"]["text"]
        assert "Score:" not in text

    def test_metadata_included(self):
        job = Job(
            id="x", title="Eng", company="Co",
            location="Remote", url="http://x",
            source="remotive",
            category="Software Dev",
            job_type="Full-time",
            salary="$100k",
            published_at="2025-06-01T12:00:00",
            tags=["python", "aws", "docker"],
        )
        blocks = job_to_blocks(job)
        text = blocks[0]["text"]["text"]
        assert "Software Dev" in text
        assert "Full-time" in text
        assert "$100k" in text
        assert "2025-06-01" in text
        assert "python" in text

    def test_minimal_job(self):
        job = Job(
            id="x", title="Eng", company="Co",
            location="NYC", url="http://x",
        )
        blocks = job_to_blocks(job)
        assert len(blocks) == 1
        text = blocks[0]["text"]["text"]
        assert "Eng" in text
        assert "Co" in text

    def test_tags_limited_to_three(self):
        job = Job(
            id="x", title="Eng", company="Co",
            location="Remote", url="http://x",
            tags=["a", "b", "c", "d", "e"],
        )
        blocks = job_to_blocks(job)
        text = blocks[0]["text"]["text"]
        assert "a" in text
        assert "c" in text
        assert "d" not in text

    def test_uses_mrkdwn_format(self, sample_job):
        blocks = job_to_blocks(sample_job)
        assert blocks[0]["text"]["type"] == "mrkdwn"
