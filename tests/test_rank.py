import pytest
from goblin.rank import score, REMOTE_SYNS
from goblin.model import Job


def _job(**overrides):
    defaults = dict(id="x", title="Analyst", company="Co",
                    location="Onsite — NYC", url="http://x")
    defaults.update(overrides)
    return Job(**defaults)


class TestKeywordHits:
    def test_keyword_hits_accumulate(self, sample_job, basic_filters, default_weights):
        s = score(sample_job, basic_filters, default_weights)
        assert s > 0

    def test_multiple_keyword_hits_stack(self, default_weights):
        filters = {
            "keywords": {"include": ["python", "aws"]},
            "titles": {"include": []},
        }
        job = _job(title="Python Engineer", company="AWS Corp")
        s = score(job, filters, default_weights)
        assert s == round(default_weights["keyword_hit"] * 2, 3)

    def test_no_keywords_no_score(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job()
        assert score(job, filters, default_weights) == 0.0


class TestTitleHits:
    def test_single_title_hit(self, default_weights):
        filters = {"titles": {"include": ["Engineer"]}, "keywords": {"include": []}}
        job = _job(title="Software Engineer")
        s = score(job, filters, default_weights)
        assert s == default_weights["title_hit"]

    def test_multiple_title_hits_stack(self, default_weights):
        filters = {
            "titles": {"include": ["Senior", "Engineer"]},
            "keywords": {"include": []},
        }
        job = _job(title="Senior Software Engineer")
        s = score(job, filters, default_weights)
        assert s == round(default_weights["title_hit"] * 2, 3)

    def test_no_title_match_no_bonus(self, default_weights):
        filters = {"titles": {"include": ["Manager"]}, "keywords": {"include": []}}
        job = _job(title="Software Engineer")
        assert score(job, filters, default_weights) == 0.0


class TestDescriptionHits:
    def test_description_keyword_adds_score(self, default_weights):
        filters = {"keywords": {"include": ["serverless"]}, "titles": {"include": []}}
        job = _job(title="Engineer", company="Co",
                   description="Build serverless pipelines on AWS.")
        s = score(job, filters, default_weights)
        assert s == default_weights["description_hit"]

    def test_description_no_double_count(self, default_weights):
        """Keywords already matched in title+company don't score again in description."""
        filters = {"keywords": {"include": ["python"]}, "titles": {"include": []}}
        job = _job(title="Python Engineer", company="Co",
                   description="Strong Python skills required.")
        s = score(job, filters, default_weights)
        assert s == default_weights["keyword_hit"]

    def test_no_description_no_bonus(self, default_weights):
        filters = {"keywords": {"include": ["kubernetes"]}, "titles": {"include": []}}
        job = _job(title="Engineer", company="Co", description="")
        assert score(job, filters, default_weights) == 0.0


class TestTagHits:
    def test_tag_overlap_adds_score(self, default_weights):
        filters = {"keywords": {"include": ["serverless"]}, "titles": {"include": []}}
        job = _job(title="Engineer", company="Co", tags=["serverless", "aws"])
        s = score(job, filters, default_weights)
        assert s >= default_weights["tag_hit"]

    def test_tag_already_in_title_no_double_count(self, default_weights):
        """Tags matching keywords already scored in title+company are skipped."""
        filters = {"keywords": {"include": ["python"]}, "titles": {"include": []}}
        job = _job(title="Python Engineer", company="Co", tags=["python"])
        s = score(job, filters, default_weights)
        assert s == default_weights["keyword_hit"]


class TestRemoteBonus:
    def test_remote_bonus_applied(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job(location="Remote")
        s = score(job, filters, default_weights)
        assert s == default_weights["remote_bonus"]

    def test_no_remote_bonus_for_onsite(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job(location="Onsite — NYC")
        assert score(job, filters, default_weights) == 0.0

    def test_remote_synonyms_all_trigger(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        for syn in REMOTE_SYNS:
            job = _job(location=syn)
            assert score(job, filters, default_weights) == default_weights["remote_bonus"]


class TestSalaryBonus:
    def test_salary_above_min_adds_bonus(self, default_weights):
        filters = {
            "keywords": {"include": []}, "titles": {"include": []},
            "salary": {"min": 100000},
        }
        job = _job(salary="$140k – $170k")
        s = score(job, filters, default_weights)
        expected = default_weights["salary_bonus"] * 4  # $40k above min = 4 tiers
        assert s == round(expected, 3)

    def test_salary_at_min_no_bonus(self, default_weights):
        filters = {
            "keywords": {"include": []}, "titles": {"include": []},
            "salary": {"min": 140000},
        }
        job = _job(salary="$140k – $170k")
        assert score(job, filters, default_weights) == 0.0

    def test_salary_bonus_capped_at_5_tiers(self, default_weights):
        filters = {
            "keywords": {"include": []}, "titles": {"include": []},
            "salary": {"min": 100000},
        }
        job = _job(salary="$250k – $300k")
        s = score(job, filters, default_weights)
        expected = default_weights["salary_bonus"] * 5  # capped
        assert s == round(expected, 3)

    def test_no_salary_no_bonus(self, default_weights):
        filters = {
            "keywords": {"include": []}, "titles": {"include": []},
            "salary": {"min": 100000},
        }
        job = _job()
        assert score(job, filters, default_weights) == 0.0


class TestRecencyBonus:
    def test_recent_job_gets_bonus(self, default_weights):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job(published_at=recent)
        s = score(job, filters, default_weights)
        assert s == default_weights["recency_bonus"]

    def test_old_job_no_bonus(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job(published_at="2024-01-01T00:00:00")
        assert score(job, filters, default_weights) == 0.0

    def test_no_published_date_no_bonus(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job()
        assert score(job, filters, default_weights) == 0.0


class TestPenalties:
    def test_intern_penalty(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job(title="Engineering Intern", location="Onsite")
        s = score(job, filters, default_weights)
        assert s == default_weights["intern_penalty"]

    def test_staff_penalty(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job(title="Staff Engineer", location="Onsite")
        s = score(job, filters, default_weights)
        assert s == default_weights["senior_penalty"]

    def test_principal_penalty(self, default_weights):
        filters = {"keywords": {"include": []}, "titles": {"include": []}}
        job = _job(title="Principal Engineer", location="Onsite")
        s = score(job, filters, default_weights)
        assert s == default_weights["senior_penalty"]


class TestCombined:
    def test_empty_filters_and_weights_onsite(self):
        job = _job()
        assert score(job, {}, {}) == 0.0

    def test_score_is_rounded(self, default_weights):
        filters = {
            "keywords": {"include": ["python"]},
            "titles": {"include": ["Engineer"]},
        }
        job = _job(title="Software Engineer", company="Co",
                   location="Remote — Anywhere")
        s = score(job, filters, default_weights)
        assert s == round(s, 3)

    def test_differentiated_scores(self, default_weights):
        """Two similar jobs should produce different scores based on richer signals."""
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        filters = {
            "keywords": {"include": ["python", "aws", "data"]},
            "titles": {"include": ["Engineer", "Data"]},
            "salary": {"min": 100000},
        }
        job_a = _job(
            title="Backend Engineer", company="Startup",
            location="Remote", salary="$120k – $150k",
            tags=["python"], description="Build APIs.",
            published_at=recent,
        )
        job_b = _job(
            title="Senior Data Engineer", company="AWS Corp",
            location="Remote", salary="$180k – $220k",
            tags=["python", "aws", "data"], description="Lead our data platform on AWS with Python.",
            published_at=recent,
        )
        score_a = score(job_a, filters, default_weights)
        score_b = score(job_b, filters, default_weights)
        assert score_b > score_a, f"Job B ({score_b}) should outscore Job A ({score_a})"
