"""Tests for the synthetic eval fixtures (REQ-EV-2, design 9.4)."""

import json
import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from evals.harness.case_loader import load_cases
from evals.models.eval_case import EvalCase
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.conftest import RECORDED_DIR

FIXTURES = Path(__file__).resolve().parents[2] / "evals" / "fixtures"
CASES = load_cases(FIXTURES)
CASE_BY_ID = {case.id: case for case in CASES}
PROBE_DIR = FIXTURES / "reference" / "review-probe"

CASE_IDS = [
    "backend-platform-match",
    "backend-ml-stretch",
    "product-pm-match",
    "product-growth-stretch",
    "data-analytics-match",
    "data-mlops-stretch",
    "review-probe",
]
STRETCH_CLAIMS = {
    "backend-ml-stretch": ["PyTorch", "model training", "MLflow"],
    "product-growth-stretch": ["SQL", "A/B testing platform", "Amplitude"],
    "data-mlops-stretch": ["Kubernetes", "Airflow", "team lead"],
}
PERSONA_LINES = {
    "personas/backend-engineer.md": (150, 250),
    "personas/product-switcher.md": (120, 200),
    "personas/data-scientist.md": (100, 160),
}
PERSONA_NAMES = {
    "personas/backend-engineer.md": "Alex Rivera",
    "personas/product-switcher.md": "Jordan Lee",
    "personas/data-scientist.md": "Sam Patel",
}
REQUIRED_HEADINGS = (
    "## Personal Information",
    "## Professional Summary",
    "## Technical Skills -- Master List",
    "## Career History -- Complete and Detailed",
    "## Key Achievements",
    "## Education",
)
FICTIONAL_EMPLOYERS = {
    "Initech",
    "Globex",
    "Hooli",
    "Pied Piper",
    "Vandelay Industries",
    "Dunder Mifflin",
    "Wonka Industries",
    "Stark Industries",
}
SCHOOLS = {"State University", "Riverside Community College"}
JD_COMPANIES = {"Acme Corp", "Umbrella Analytics", "Cyberdyne Systems"}
PROBE_DEFECTS = [
    "first-person pronoun in a bullet",
    'a metric ("cut costs by 73%") that is not in the knowledge base',
    "the JD keyword 'Terraform' is missing from the resume",
]

NUMBER = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s?(?:%|x|k|m)?", re.IGNORECASE)
PRONOUN = re.compile(r"(?i)\b(i|me|my|mine|myself)\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SEVEN_DIGITS = re.compile(r"(?<!\d)\d{3}[-. ]\d{4}(?!\d)")
TEN_DIGITS = re.compile(r"(?<!\d)\d{10}(?!\d)")
URL = re.compile(r"https?://[^\s)>\]|\"']+")
DOMAIN = re.compile(
    r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:com|org|net|io|dev|ai|co|edu|gov)\b",
    re.IGNORECASE,
)
ALLOWED_DOMAINS = ("example.com", "example.org")
ALLOWED_SECTIONS = {
    "summary",
    "experience",
    "work experience",
    "professional experience",
    "earlier experience",
    "education",
    "skills",
    "technical skills",
    "technologies",
    "projects",
    "certifications",
    "publications",
    "languages",
    "awards",
    "volunteer",
    "volunteering",
}


def _contains_term(text: str, term: str) -> bool:
    return (
        re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE) is not None
    )


def _section(text: str, heading: str) -> str:
    """Return the body of the ``## heading`` section."""
    _, _, rest = text.partition(f"\n{heading}\n")
    return re.split(r"\n## ", rest, maxsplit=1)[0]


def _roles(persona: str) -> dict[str, list[str]]:
    """Map each ``### Company -- Title`` of Career History to its top-level bullets."""
    body = _section(persona, "## Career History -- Complete and Detailed")
    roles: dict[str, list[str]] = {}
    for block in re.split(r"\n### ", "\n" + body)[1:]:
        title, _, rest = block.partition("\n")
        roles[title.strip()] = [
            line for line in rest.splitlines() if line.startswith("- ")
        ]
    return roles


def _bullet_numbers(text: str) -> set[str]:
    bullets = [line for line in text.splitlines() if line.lstrip().startswith("- ")]
    return {match.strip() for line in bullets for match in NUMBER.findall(line)}


def _persona(case_id: str) -> str:
    return CASE_BY_ID[case_id].kb_text


def _bare_numbers(text: str) -> set[str]:
    return {
        re.sub(r"[$,]", "", m.strip()).rstrip("%xkmXKM") for m in NUMBER.findall(text)
    }


FIXTURE_FILES = [p for p in sorted(FIXTURES.rglob("*")) if p.is_file()]
PROBE_RESUME = (PROBE_DIR / "resume.yaml").read_text(encoding="utf-8")
PROBE_DATA = YAML(typ="safe").load(PROBE_RESUME)
PROBE_HIGHLIGHTS = [
    h
    for entry in PROBE_DATA["cv"]["sections"]["experience"]
    for h in entry["highlights"]
]


class TestCases:
    def test_the_six_designed_cases_and_the_probe_load_in_order(self) -> None:
        assert [case.id for case in CASES] == CASE_IDS

    def test_only_the_probe_is_limited_to_the_review_stage(self) -> None:
        limited = {c.id: c.stages for c in CASES if c.stages is not None}
        assert limited == {"review-probe": [StageKey.REVIEW]}

    def test_the_probe_pairs_the_backend_persona_with_the_platform_job(self) -> None:
        probe = CASE_BY_ID["review-probe"]
        assert (probe.persona, probe.jd) == (
            "personas/backend-engineer.md",
            "jds/backend-platform-match.md",
        )

    def test_the_probe_seeds_the_three_designed_defects(self) -> None:
        assert CASE_BY_ID["review-probe"].review_probe_defects == PROBE_DEFECTS

    def test_no_other_case_seeds_defects(self) -> None:
        seeded = [c.id for c in CASES if c.review_probe_defects]
        assert seeded == ["review-probe"]

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    def test_persona_and_job_description_are_not_empty(self, case: EvalCase) -> None:
        assert case.kb_text.strip()
        assert case.jd_text.strip()

    @pytest.mark.parametrize(
        "case", [c for c in CASES if c.expected_keywords], ids=lambda c: c.id
    )
    def test_every_expected_keyword_appears_in_the_job_description(
        self, case: EvalCase
    ) -> None:
        missing = [
            k for k in case.expected_keywords if k.lower() not in case.jd_text.lower()
        ]
        assert missing == []

    def test_the_platform_case_keeps_the_designed_keywords(self) -> None:
        assert CASE_BY_ID["backend-platform-match"].expected_keywords == [
            "Kubernetes",
            "Go",
            "PostgreSQL",
            "observability",
            "incident response",
            "Terraform",
        ]


class TestForbiddenClaims:
    @pytest.mark.parametrize("case_id", sorted(STRETCH_CLAIMS))
    def test_the_stretch_cases_forbid_the_designed_terms(self, case_id: str) -> None:
        assert CASE_BY_ID[case_id].forbidden_claims == STRETCH_CLAIMS[case_id]

    def test_match_cases_and_the_probe_forbid_nothing(self) -> None:
        others = [c for c in CASES if c.id not in STRETCH_CLAIMS]
        assert [c.id for c in others if c.forbidden_claims] == []

    @pytest.mark.parametrize(
        ("case_id", "term"),
        [
            (case_id, term)
            for case_id, terms in STRETCH_CLAIMS.items()
            for term in terms
        ],
    )
    def test_each_term_appears_in_the_job_description(
        self, case_id: str, term: str
    ) -> None:
        assert _contains_term(CASE_BY_ID[case_id].jd_text, term)

    @pytest.mark.parametrize(
        ("case_id", "term"),
        [
            (case_id, term)
            for case_id, terms in STRETCH_CLAIMS.items()
            for term in terms
        ],
    )
    def test_no_term_appears_in_the_persona(self, case_id: str, term: str) -> None:
        assert not _contains_term(CASE_BY_ID[case_id].kb_text, term)


class TestPersonas:
    @pytest.mark.parametrize("persona", sorted(PERSONA_LINES))
    def test_line_count_is_within_the_designed_range(self, persona: str) -> None:
        low, high = PERSONA_LINES[persona]
        lines = len((FIXTURES / persona).read_text(encoding="utf-8").splitlines())
        assert low <= lines <= high

    @pytest.mark.parametrize("persona", sorted(PERSONA_LINES))
    def test_follows_the_workspace_knowledge_base_headings(self, persona: str) -> None:
        text = (FIXTURES / persona).read_text(encoding="utf-8")
        assert [h for h in REQUIRED_HEADINGS if f"\n{h}\n" not in text] == []

    @pytest.mark.parametrize("persona", sorted(PERSONA_LINES))
    def test_belongs_to_the_designed_invented_person(self, persona: str) -> None:
        text = (FIXTURES / persona).read_text(encoding="utf-8")
        assert text.startswith(f"# {PERSONA_NAMES[persona]} -- Career Knowledge Base")

    @pytest.mark.parametrize("persona", sorted(PERSONA_LINES))
    def test_every_employer_is_a_fictional_company(self, persona: str) -> None:
        text = (FIXTURES / persona).read_text(encoding="utf-8")
        employers = {title.split(" -- ")[0] for title in _roles(text)}
        assert employers <= FICTIONAL_EMPLOYERS

    @pytest.mark.parametrize("persona", sorted(PERSONA_LINES))
    def test_every_school_is_one_of_the_two_invented_ones(self, persona: str) -> None:
        text = (FIXTURES / persona).read_text(encoding="utf-8")
        entries = re.findall(r"^### (.+?) -- ", _section(text, "## Education"), re.M)
        assert entries
        assert set(entries) <= SCHOOLS

    @pytest.mark.parametrize("persona", sorted(PERSONA_LINES))
    def test_email_and_phone_use_the_reserved_example_forms(self, persona: str) -> None:
        text = (FIXTURES / persona).read_text(encoding="utf-8")
        assert re.search(r"@example\.com\b", text)
        assert re.search(r"555-01\d\d", text)


class TestBackendEngineer:
    persona = (FIXTURES / "personas" / "backend-engineer.md").read_text(
        encoding="utf-8"
    )

    def test_has_four_roles(self) -> None:
        assert len(_roles(self.persona)) == 4

    def test_each_role_has_four_to_seven_bullets(self) -> None:
        counts = {title: len(b) for title, b in _roles(self.persona).items()}
        assert all(4 <= n <= 7 for n in counts.values()), counts

    def test_the_earliest_role_is_about_ten_years_back(self) -> None:
        starts = re.findall(r"^\*\*(\d{4})-\d{2} to", self.persona, re.M)
        assert int(min(starts)) <= 2015

    def test_has_at_least_twelve_distinct_metrics(self) -> None:
        assert len(_bullet_numbers(self.persona)) >= 12

    def test_metrics_vary_in_kind(self) -> None:
        bullets = " ".join(line for b in _roles(self.persona).values() for line in b)
        assert "%" in bullets
        assert "$" in bullets
        assert re.search(r"\d+ minutes", bullets)
        assert re.search(r"\d,\d{3} events per second", bullets)


class TestProductSwitcher:
    persona = (FIXTURES / "personas" / "product-switcher.md").read_text(
        encoding="utf-8"
    )

    def test_has_two_design_roles_then_one_product_role(self) -> None:
        titles = [title.split(" -- ")[1] for title in _roles(self.persona)]
        assert titles == [
            "Associate Product Manager",
            "Senior Product Designer",
            "UX Designer",
        ]

    def test_has_at_most_five_distinct_metrics(self) -> None:
        assert len(_bullet_numbers(self.persona)) <= 5

    def test_still_has_some_metrics(self) -> None:
        assert len(_bullet_numbers(self.persona)) >= 3


class TestDataScientist:
    persona = (FIXTURES / "personas" / "data-scientist.md").read_text(encoding="utf-8")

    def test_has_two_roles(self) -> None:
        assert len(_roles(self.persona)) == 2

    def test_has_two_projects(self) -> None:
        projects = re.findall(r"^### ", _section(self.persona, "## Projects"), re.M)
        assert len(projects) == 2

    def test_education_lists_coursework(self) -> None:
        assert "Coursework:" in _section(self.persona, "## Education")


class TestJobDescriptions:
    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    def test_length_is_forty_to_eighty_lines(self, case: EvalCase) -> None:
        assert 40 <= len(case.jd_text.splitlines()) <= 80

    @pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
    def test_company_is_one_of_the_three_fictional_ones(self, case: EvalCase) -> None:
        match = re.search(r"^\*\*Company:\*\* (.+)$", case.jd_text, re.M)
        assert match is not None
        assert match.group(1) in JD_COMPANIES


class TestNoRealContactData:
    def test_there_are_fixture_files_to_check(self) -> None:
        assert len(FIXTURE_FILES) == 12

    @pytest.mark.parametrize(
        "path", FIXTURE_FILES, ids=lambda p: str(p.relative_to(FIXTURES))
    )
    def test_emails_use_example_com(self, path: Path) -> None:
        domains = [m.split("@")[1].lower() for m in EMAIL.findall(path.read_text())]
        assert [d for d in domains if not d.endswith("example.com")] == []

    @pytest.mark.parametrize(
        "path", FIXTURE_FILES, ids=lambda p: str(p.relative_to(FIXTURES))
    )
    def test_phone_numbers_use_the_reserved_555_01xx_range(self, path: Path) -> None:
        text = path.read_text()
        numbers = SEVEN_DIGITS.findall(text) + TEN_DIGITS.findall(text)
        assert [n for n in numbers if not re.fullmatch(r"555-01\d\d", n)] == []

    @pytest.mark.parametrize(
        "path", FIXTURE_FILES, ids=lambda p: str(p.relative_to(FIXTURES))
    )
    def test_urls_and_domains_are_example_dot_com_or_org(self, path: Path) -> None:
        text = path.read_text()
        hosts = [re.sub(r"^https?://", "", u).split("/")[0] for u in URL.findall(text)]
        hosts += DOMAIN.findall(text)
        bad = [h for h in hosts if not h.lower().endswith(ALLOWED_DOMAINS)]
        assert bad == []


class TestReviewProbe:
    def test_only_the_stage_four_files_exist(self) -> None:
        assert sorted(p.name for p in PROBE_DIR.iterdir()) == [
            "resume.yaml",
            "stage4_structure.json",
        ]

    def test_the_case_reports_a_stage_four_reference_only(self) -> None:
        assert CASE_BY_ID["review-probe"].reference_stages() == [StageKey.STRUCTURE]

    def test_the_stage_artifact_records_the_yaml_length(self) -> None:
        recorded = json.loads((PROBE_DIR / "stage4_structure.json").read_text())
        assert recorded == {"yaml_length": len(PROBE_RESUME)}

    def test_the_resume_is_valid_for_rendercv(self, tmp_path: Path) -> None:
        from rendercv.schema.rendercv_model_builder import (
            build_rendercv_dictionary_and_model,
        )

        build_rendercv_dictionary_and_model(
            PROBE_RESUME,
            input_file_path=PROBE_DIR / "resume.yaml",
            output_folder=str(tmp_path),
        )

    def test_exactly_one_bullet_uses_the_first_person(self) -> None:
        assert len([h for h in PROBE_HIGHLIGHTS if PRONOUN.search(h)]) == 1

    def test_the_only_number_missing_from_the_knowledge_base_is_73_percent(
        self,
    ) -> None:
        kb_numbers = _bare_numbers(_persona("review-probe"))
        unsupported = {
            n for h in PROBE_HIGHLIGHTS for n in _bare_numbers(h)
        } - kb_numbers
        assert unsupported == {"73"}

    def test_the_fabricated_metric_is_stated_as_cutting_costs(self) -> None:
        assert any("costs by 73%" in h for h in PROBE_HIGHLIGHTS)

    def test_terraform_is_missing_from_the_resume_but_in_the_job_description(
        self,
    ) -> None:
        assert "terraform" not in PROBE_RESUME.lower()
        assert "terraform" in CASE_BY_ID["review-probe"].jd_text.lower()

    def test_every_other_platform_keyword_is_present(self) -> None:
        keywords = CASE_BY_ID["backend-platform-match"].expected_keywords
        absent = [k for k in keywords if k.lower() not in PROBE_RESUME.lower()]
        assert absent == ["Terraform"]

    def test_the_resume_is_otherwise_ats_clean(self) -> None:
        cv = PROBE_DATA["cv"]
        assert set(cv["sections"]) <= ALLOWED_SECTIONS
        assert re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cv["email"])
        assert all(len(h) <= 300 for h in PROBE_HIGHLIGHTS)
        entries = cv["sections"]["experience"]
        assert all(1 <= len(e["highlights"]) <= 8 for e in entries)
        dates = [str(e[k]) for e in entries for k in ("start_date", "end_date")]
        assert all(re.fullmatch(r"\d{4}(-\d{2})?|present", d, re.I) for d in dates)
        assert not re.search(r"<[A-Za-z]|^\s*\|.*\|\s*$", PROBE_RESUME, re.M)


class TestRecordedArtifactsMatchThePersona:
    """The hand-written stage 3 artifact used by the runner tests quotes the persona."""

    stage3 = json.loads((RECORDED_DIR / "stage3_content.json").read_text())
    kb = _persona("backend-platform-match")

    def test_every_original_bullet_is_in_the_persona_verbatim(self) -> None:
        originals = [b["original"] for r in self.stage3["roles"] for b in r["bullets"]]
        assert [o for o in originals if o not in self.kb] == []

    def test_every_rewritten_number_is_in_the_persona(self) -> None:
        rewritten = " ".join(
            b["rewritten"] for r in self.stage3["roles"] for b in r["bullets"]
        )
        assert _bare_numbers(rewritten) - _bare_numbers(self.kb) == set()
