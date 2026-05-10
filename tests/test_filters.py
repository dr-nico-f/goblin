import pytest
from goblin.filters import _parse_salary_to_int, matches
from goblin.model import Job


class TestParseSalaryToInt:
    def test_none_input(self):
        assert _parse_salary_to_int(None) is None

    def test_empty_string(self):
        assert _parse_salary_to_int("") is None

    def test_simple_number(self):
        assert _parse_salary_to_int("120000") == 120000

    def test_k_suffix(self):
        assert _parse_salary_to_int("$120k") == 120000

    def test_k_suffix_uppercase(self):
        assert _parse_salary_to_int("$120K") == 120000

    def test_range_with_k(self):
        assert _parse_salary_to_int("$140k – $170k") == 140000

    def test_range_with_dash(self):
        assert _parse_salary_to_int("$140k-$170k") == 140000

    def test_range_with_commas(self):
        assert _parse_salary_to_int("140,000-170,000") == 140000

    def test_range_with_to(self):
        assert _parse_salary_to_int("$140k to $170k") == 140000

    def test_single_value_commas(self):
        assert _parse_salary_to_int("$150,000") == 150000

    def test_no_parseable_value(self):
        assert _parse_salary_to_int("Competitive") is None

    def test_returns_lower_bound(self):
        assert _parse_salary_to_int("$100k – $200k") == 100000


class TestMatches:
    def test_basic_match(self, sample_job, basic_filters):
        assert matches(sample_job, basic_filters) is True

    def test_title_exclude_blocks(self, intern_job, basic_filters):
        assert matches(intern_job, basic_filters) is False

    def test_location_exclude_blocks(self, basic_filters):
        job = Job(
            id="x", title="Software Engineer",
            company="Co", location="Onsite Only — NYC",
            url="http://x",
        )
        assert matches(job, basic_filters) is False

    def test_keyword_exclude_blocks(self, basic_filters):
        job = Job(
            id="x", title="PHP Developer",
            company="Co", location="Remote",
            url="http://x",
        )
        assert matches(job, basic_filters) is False

    def test_empty_filters_matches_everything(self, sample_job):
        assert matches(sample_job, {}) is True

    def test_title_include_or_keyword_include(self, basic_filters):
        job = Job(
            id="x", title="Data Analyst",
            company="Python Corp", location="Remote",
            url="http://x",
        )
        assert matches(job, basic_filters) is True

    def test_neither_title_nor_keyword_match(self, basic_filters):
        job = Job(
            id="x", title="Marketing Manager",
            company="Ad Agency", location="Remote",
            url="http://x",
        )
        assert matches(job, basic_filters) is False

    def test_remote_synonym_accepted(self, basic_filters):
        job = Job(
            id="x", title="Software Engineer",
            company="Co", location="Anywhere",
            url="http://x",
        )
        assert matches(job, basic_filters) is True

    def test_salary_below_minimum_rejected(self, salary_filters):
        job = Job(
            id="x", title="Software Engineer",
            company="Co", location="Remote",
            url="http://x", salary="$80k – $100k",
        )
        assert matches(job, salary_filters) is False

    def test_salary_above_minimum_accepted(self, salary_filters):
        job = Job(
            id="x", title="Software Engineer",
            company="Co", location="Remote",
            url="http://x", salary="$140k – $170k",
        )
        assert matches(job, salary_filters) is True

    def test_missing_salary_rejected_when_not_allowed(self, salary_filters):
        job = Job(
            id="x", title="Software Engineer",
            company="Co", location="Remote",
            url="http://x",
        )
        assert matches(job, salary_filters) is False

    def test_missing_salary_accepted_when_allowed(self, basic_filters):
        filters = {
            **basic_filters,
            "salary": {"min": 120000, "allow_missing": True},
        }
        job = Job(
            id="x", title="Software Engineer",
            company="Co", location="Remote",
            url="http://x",
        )
        assert matches(job, filters) is True

    def test_case_insensitive_matching(self, basic_filters):
        job = Job(
            id="x", title="SOFTWARE ENGINEER",
            company="PYTHON CORP", location="REMOTE",
            url="http://x",
        )
        assert matches(job, basic_filters) is True

    def test_no_salary_config_skips_check(self, sample_job, basic_filters):
        assert matches(sample_job, basic_filters) is True

    def test_location_include_required(self):
        filters = {
            "locations": {"include": ["Europe"], "exclude": []},
        }
        job = Job(
            id="x", title="Engineer",
            company="Co", location="Remote — USA",
            url="http://x",
        )
        assert matches(job, filters) is False
