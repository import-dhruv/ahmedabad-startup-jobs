"""Tests for job normalisation."""
from app.services.normalizer import (
    canonical_employment_type,
    detect_categories,
    detect_employment_type,
    detect_experience,
    detect_salary,
    detect_work_arrangement,
    extract_skills,
    is_internship,
    normalize_job_fields,
    normalize_title,
    split_sections,
    strip_html,
    title_signature,
)


class TestStripHtml:
    def test_removes_tags_and_scripts(self):
        html = "<div>Hello<script>alert(1)</script><p>World</p></div>"
        text = strip_html(html)
        assert "alert" not in text
        assert "Hello" in text and "World" in text

    def test_keeps_line_breaks_for_lists(self):
        text = strip_html("<ul><li>One</li><li>Two</li></ul>")
        assert "One" in text and "Two" in text

    def test_none_is_empty(self):
        assert strip_html(None) == ""


class TestTitles:
    def test_strips_seniority_and_noise(self):
        assert normalize_title("Senior Software Engineer (Remote)") == "software engineer"

    def test_keeps_technology_tokens(self):
        assert "c++" in normalize_title("C++ Developer")
        assert "node.js" in normalize_title("Node.js Engineer")

    def test_signature_ignores_word_order(self):
        a = title_signature("Software Engineer Backend")
        b = title_signature("Backend Software Engineer")
        assert a == b


class TestExperience:
    def test_fresher_from_title(self):
        level, _, _ = detect_experience("Software Engineer Intern", "Great role")
        assert level == "Fresher"

    def test_range_in_description(self):
        level, low, high = detect_experience("Engineer", "You have 3-5 years of experience")
        assert low == 3 and high == 5
        assert level == "3-5 years"

    def test_seniority_from_title(self):
        level, _, _ = detect_experience("Senior Data Scientist", "")
        assert level == "5-8 years"

    def test_no_signal(self):
        level, low, high = detect_experience("Engineer", "Build great things")
        assert level is None


class TestEmployment:
    def test_intern_in_title_wins(self):
        assert detect_employment_type("Marketing Intern", "Full-time role") == "Internship"

    def test_contract_in_description(self):
        assert detect_employment_type("Engineer", "This is a contract position") == "Contract"

    def test_full_time(self):
        assert detect_employment_type("Engineer", "Full-time position") == "Full-time"

    def test_canonicalisation_of_source_labels(self):
        assert canonical_employment_type("full_time") == "Full-time"
        assert canonical_employment_type("FULL TIME") == "Full-time"
        assert canonical_employment_type("freelance") == "Freelance"
        assert canonical_employment_type("intern") == "Internship"
        assert canonical_employment_type("weird-value") is None


class TestWorkArrangement:
    def test_remote_from_location(self):
        assert detect_work_arrangement("Engineer", "", "Remote - India") == "Remote"

    def test_hybrid(self):
        assert detect_work_arrangement("Engineer", "Hybrid role, 3 days in office") == "Hybrid"

    def test_onsite(self):
        assert detect_work_arrangement("Engineer", "On-site role") == "On-site"


class TestSalary:
    def test_range_in_inr(self):
        low, high, currency, period = detect_salary("CTC is between ₹15,00,000 and ₹25,00,000 per annum")
        assert currency == "INR"
        assert period == "year"
        assert low == 1500000 and high == 2500000

    def test_lpa_range(self):
        low, high, currency, period = detect_salary("Compensation: 12 LPA - 18 LPA")
        assert currency == "INR"
        assert low == 1200000 and high == 1800000

    def test_no_salary_means_none(self):
        assert detect_salary("We care about impact, not numbers") == (None, None, None, None)

    def test_salary_is_never_invented(self):
        low, high, _, _ = detect_salary("Great team, nice salary.")
        assert low is None and high is None


class TestSkills:
    def test_extracts_known_skills(self):
        skills = dict(extract_skills("We use Python, FastAPI and PostgreSQL with Docker"))
        assert skills.get("Python") == 0.9
        assert "FastAPI" in skills
        assert "PostgreSQL" in skills

    def test_title_skills_rank_higher(self):
        skills = dict(extract_skills("Some Python needed", "Python Backend Engineer"))
        assert skills.get("Python") == 1.0

    def test_ai_skill_requires_supporting_context(self):
        skills = dict(extract_skills("You will build agents using LangChain and OpenAI models"))
        assert "LangChain" in skills
        assert "Agentic AI" not in skills  # no agent/tool-use signal

    def test_ai_skill_with_supporting_context(self):
        skills = dict(
            extract_skills("Design agentic AI pipelines with tool use, retrieval and vector search")
        )
        assert "Agentic AI" in skills

    def test_no_false_positive_on_internal(self):
        skills = dict(extract_skills("Internal comms team, great culture"))
        assert "Python" not in skills


class TestCategories:
    def test_ai_role(self):
        categories = dict(detect_categories("Machine Learning Engineer", "Build deep learning models"))
        assert "AI / Machine Learning" in categories

    def test_fallback(self):
        categories = dict(detect_categories("Widget Wrangler", "Nothing specific here"))
        assert categories.get("Software Engineering") is not None


class TestSections:
    def test_splits_responsibilities_and_requirements(self):
        description = (
            "About the role\n"
            "You will build things.\n"
            "Requirements\n"
            "Python experience\n"
            "Docker experience\n"
        )
        sections = split_sections(description)
        assert any("build things" in item.lower() for item in sections["responsibilities"])
        assert len(sections["qualifications"]) == 2

    def test_falls_back_to_bullets(self):
        description = "Responsibilities:\n- Build things\n- Ship things\n- Own things\n"
        sections = split_sections(description)
        assert sections["responsibilities"]


class TestNormalizeJobFields:
    def test_end_to_end(self):
        job = normalize_job_fields(
            title="Backend Engineer Intern",
            company_name="Example Startup",
            description=(
                "<h2>About the role</h2><p>Build APIs with Python and FastAPI.</p>"
                "<h3>Requirements</h3><ul><li>Python</li><li>Docker</li></ul>"
            ),
            location_raw="Ahmedabad, Gujarat",
        )
        assert job.location.scope == "ahmedabad"
        assert job.experience_level == "Fresher"
        assert is_internship(job.title, job.description, job.employment_type)
        assert any(name == "Python" for name, _ in job.skills)
        assert job.quality_score > 0.4
