import pytest
from goblin.rank import score, REMOTE_SYNS
from goblin.model import Job


class TestScore:
    def test_keyword_hits_accumulate(self, sample_job, basic_filters, default_weights):
        s = score(sample_job, basic_filters, default_weights)
        assert s > 0

    def test_remote_bonus_applied(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = Job(
            id="x", title="Engineer", company="Co",
            location="Remote", url="http://x",
        )
        s = score(job, filters, default_weights)
        assert s == default_weights["remote_bonus"]

    def test_no_remote_bonus_for_onsite(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = Job(
            id="x", title="Engineer", company="Co",
            location="Onsite — NYC", url="http://x",
        )
        s = score(job, filters, default_weights)
        assert s == 0.0

    def test_intern_penalty(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = Job(
            id="x", title="Engineering Intern", company="Co",
            location="Onsite", url="http://x",
        )
        s = score(job, filters, default_weights)
        assert s == default_weights["intern_penalty"]

    def test_staff_penalty(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = Job(
            id="x", title="Staff Engineer", company="Co",
            location="Onsite", url="http://x",
        )
        s = score(job, filters, default_weights)
        assert s == default_weights["senior_penalty"]

    def test_principal_penalty(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = Job(
            id="x", title="Principal Engineer", company="Co",
            location="Onsite", url="http://x",
        )
        s = score(job, filters, default_weights)
        assert s == default_weights["senior_penalty"]

    def test_title_match_bonus(self, default_weights):
        filters = {
            "titles": {"include": ["Engineer"]},
            "keywords": {"include": []},
        }
        job = Job(
            id="x", title="Software Engineer", company="Co",
            location="Onsite", url="http://x",
        )
        s = score(job, filters, default_weights)
        assert s == default_weights["title_match"]

    def test_empty_filters_and_weights_onsite(self):
        job = Job(
            id="x", title="Analyst", company="Co",
            location="Onsite — NYC", url="http://x",
        )
        s = score(job, {}, {})
        assert s == 0.0

    def test_score_is_rounded(self, default_weights):
        filters = {
            "keywords": {"include": ["python"]},
            "titles": {"include": ["Engineer"]},
        }
        job = Job(
            id="x", title="Software Engineer", company="Co",
            location="Remote — Anywhere", url="http://x",
        )
        s = score(job, filters, default_weights)
        assert s == round(s, 3)

    def test_multiple_keyword_hits_stack(self, default_weights):
        filters = {
            "keywords": {"include": ["python", "aws"]},
            "titles": {"include": []},
        }
        job = Job(
            id="x", title="Python Engineer", company="AWS Corp",
            location="Onsite", url="http://x",
        )
        s = score(job, filters, default_weights)
        expected = default_weights["keyword_hit"] * 2
        assert s == round(expected, 3)

    def test_remote_synonyms_all_trigger(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        for syn in REMOTE_SYNS:
            job = Job(
                id="x", title="Engineer", company="Co",
                location=syn, url="http://x",
            )
            assert score(job, filters, default_weights) == default_weights["remote_bonus"]
