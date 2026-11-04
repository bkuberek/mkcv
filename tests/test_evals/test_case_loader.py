"""Tests for case loading and matrix parsing (REQ-EV-1, REQ-EV-2, design 9.3-9.4)."""

import json
from pathlib import Path

import pytest

from evals.harness.case_loader import load_cases, load_matrix, select_cases
from evals.models.eval_case import EvalCase
from evals.stages import EVALUATED_STAGES
from mkcv.adapters.llm.builtin_providers import BUILTIN_PROVIDERS
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.model_tier import ModelTier
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey
from tests.test_evals.conftest import JD_TEXT, PERSONA_TEXT

DEFAULT_MATRIX = (
    Path(__file__).resolve().parents[2] / "evals" / "config" / "matrix.toml"
)


def _write_matrix(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "matrix.toml"
    path.write_text(body, encoding="utf-8")
    return path


_PANEL = """
[[judges]]
provider = "anthropic"
model = "claude-opus-5-5"

[[judges]]
provider = "google"
model = "gemini-4-argon"
"""

_MINIMAL_MATRIX = """
[judge]
provider = "anthropic"
model = "claude-opus-5-5"

[reference]
provider = "anthropic"
model = "claude-opus-5-5"

[[models]]
provider = "anthropic"
model = "claude-haiku-5-5"
"""


class TestLoadCases:
    def test_returns_the_cases_in_file_order(self, tmp_fixtures: Path) -> None:
        cases = load_cases(tmp_fixtures)
        assert [case.id for case in cases] == ["alpha-match", "alpha-probe"]

    def test_reads_the_persona_and_job_description_text(
        self, tmp_fixtures: Path
    ) -> None:
        case = load_cases(tmp_fixtures)[0]
        assert (case.kb_text, case.jd_text) == (PERSONA_TEXT, JD_TEXT)

    def test_resolves_file_paths_against_the_fixtures_directory(
        self, tmp_fixtures: Path
    ) -> None:
        case = load_cases(tmp_fixtures)[0]
        assert case.persona_path == tmp_fixtures / "personas" / "alpha.md"
        assert case.jd_path == tmp_fixtures / "jds" / "alpha-match.md"

    def test_case_text_is_not_serialized(self, tmp_fixtures: Path) -> None:
        dumped = load_cases(tmp_fixtures)[0].model_dump()
        assert set(dumped) == {
            "id",
            "persona",
            "jd",
            "expected_keywords",
            "forbidden_claims",
            "review_probe_defects",
            "stages",
            "cover_letter",
        }

    def test_case_round_trips_through_json(self, tmp_fixtures: Path) -> None:
        case = load_cases(tmp_fixtures)[1]
        restored = EvalCase.model_validate(json.loads(case.model_dump_json()))
        assert restored.review_probe_defects == case.review_probe_defects

    def test_optional_fields_default_to_empty(self, tmp_fixtures: Path) -> None:
        case = load_cases(tmp_fixtures)[0]
        assert (case.forbidden_claims, case.review_probe_defects, case.stages) == (
            [],
            [],
            None,
        )

    def test_stage_names_become_stage_keys(self, tmp_fixtures: Path) -> None:
        assert load_cases(tmp_fixtures)[1].stages == [StageKey.REVIEW]

    def test_missing_cases_file_names_the_path(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match=r"cases\.toml"):
            load_cases(tmp_path)

    def test_missing_persona_file_names_the_case_and_the_file(
        self, tmp_fixtures: Path
    ) -> None:
        (tmp_fixtures / "personas" / "alpha.md").unlink()
        with pytest.raises(FileNotFoundError, match=r"alpha-match.*alpha\.md"):
            load_cases(tmp_fixtures)

    def test_empty_job_description_is_rejected(self, tmp_fixtures: Path) -> None:
        (tmp_fixtures / "jds" / "alpha-match.md").write_text("  \n", encoding="utf-8")
        with pytest.raises(ValueError, match=r"alpha-match.*empty"):
            load_cases(tmp_fixtures)

    def test_duplicate_case_ids_are_rejected(self, tmp_fixtures: Path) -> None:
        (tmp_fixtures / "cases.toml").write_text(
            '[[cases]]\nid = "a"\npersona = "personas/alpha.md"\n'
            'jd = "jds/alpha-match.md"\n'
            '[[cases]]\nid = "a"\npersona = "personas/alpha.md"\n'
            'jd = "jds/alpha-match.md"\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="Duplicate case id 'a'"):
            load_cases(tmp_fixtures)

    def test_unknown_stage_in_a_case_is_rejected(self, tmp_fixtures: Path) -> None:
        (tmp_fixtures / "cases.toml").write_text(
            '[[cases]]\nid = "a"\npersona = "personas/alpha.md"\n'
            'jd = "jds/alpha-match.md"\nstages = ["polish"]\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="polish"):
            load_cases(tmp_fixtures)

    def test_empty_case_list_is_rejected(self, tmp_fixtures: Path) -> None:
        (tmp_fixtures / "cases.toml").write_text("cases = []\n", encoding="utf-8")
        with pytest.raises(ValueError, match=r"\[\[cases\]\]"):
            load_cases(tmp_fixtures)

    def test_a_case_may_only_name_evaluated_stages(self, tmp_fixtures: Path) -> None:
        (tmp_fixtures / "cases.toml").write_text(
            '[[cases]]\nid = "a"\npersona = "personas/alpha.md"\n'
            'jd = "jds/alpha-match.md"\nstages = ["kb"]\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="not stages the harness evaluates"):
            load_cases(tmp_fixtures)

    def test_a_case_may_name_the_cover_letter_stages(self, tmp_fixtures: Path) -> None:
        (tmp_fixtures / "cases.toml").write_text(
            '[[cases]]\nid = "a"\npersona = "personas/alpha.md"\n'
            'jd = "jds/alpha-match.md"\n'
            'stages = ["cover_letter.generate", "cover_letter.review"]\n',
            encoding="utf-8",
        )
        assert load_cases(tmp_fixtures)[0].stages == [
            StageKey.COVER_LETTER_GENERATE,
            StageKey.COVER_LETTER_REVIEW,
        ]

    def test_file_without_cases_is_rejected(self, tmp_fixtures: Path) -> None:
        (tmp_fixtures / "cases.toml").write_text("title = 'x'\n", encoding="utf-8")
        with pytest.raises(ValueError, match=r"\[\[cases\]\]"):
            load_cases(tmp_fixtures)


class TestSelectCases:
    def test_star_selects_every_case(self, tmp_fixtures: Path) -> None:
        cases = load_cases(tmp_fixtures)
        assert select_cases(cases, ["*"]) == cases

    def test_ids_select_in_the_order_given(self, tmp_fixtures: Path) -> None:
        cases = load_cases(tmp_fixtures)
        picked = select_cases(cases, ["alpha-probe", "alpha-match"])
        assert [case.id for case in picked] == ["alpha-probe", "alpha-match"]

    def test_unknown_id_is_rejected_with_the_known_ones(
        self, tmp_fixtures: Path
    ) -> None:
        cases = load_cases(tmp_fixtures)
        with pytest.raises(ValueError, match=r"nope.*alpha-match, alpha-probe"):
            select_cases(cases, ["nope"])


class TestEvalCase:
    def test_a_case_without_stages_applies_to_every_stage(
        self, tmp_fixtures: Path
    ) -> None:
        case = load_cases(tmp_fixtures)[0]
        assert all(case.applies_to(stage) for stage in PIPELINE_STAGES)

    def test_a_case_with_stages_applies_only_to_them(self, tmp_fixtures: Path) -> None:
        case = load_cases(tmp_fixtures)[1]
        applies = [stage for stage in PIPELINE_STAGES if case.applies_to(stage)]
        assert applies == [StageKey.REVIEW]

    def test_no_reference_artifacts_by_default(self, tmp_fixtures: Path) -> None:
        assert load_cases(tmp_fixtures)[0].reference_stages() == []

    def test_reference_stages_lists_the_stages_with_every_file(
        self, tmp_fixtures: Path
    ) -> None:
        case = load_cases(tmp_fixtures)[0]
        reference = tmp_fixtures / "reference" / "alpha-match"
        reference.mkdir(parents=True)
        (reference / "stage1_analysis.json").write_text("{}", encoding="utf-8")
        (reference / "stage2_selection.json").write_text("{}", encoding="utf-8")
        (reference / "stage4_structure.json").write_text("{}", encoding="utf-8")
        assert case.reference_stages() == [StageKey.ANALYZE, StageKey.SELECT]

    def test_existing_reference_files_lists_every_file_present(
        self, tmp_fixtures: Path
    ) -> None:
        case = load_cases(tmp_fixtures)[0]
        reference = tmp_fixtures / "reference" / "alpha-match"
        reference.mkdir(parents=True)
        (reference / "stage4_structure.json").write_text("{}", encoding="utf-8")
        assert case.existing_reference_files() == [reference / "stage4_structure.json"]

    def test_existing_reference_files_is_empty_without_a_reference(
        self, tmp_fixtures: Path
    ) -> None:
        assert load_cases(tmp_fixtures)[0].existing_reference_files() == []

    def test_structure_reference_needs_the_yaml_too(self, tmp_fixtures: Path) -> None:
        case = load_cases(tmp_fixtures)[0]
        reference = tmp_fixtures / "reference" / "alpha-match"
        reference.mkdir(parents=True)
        (reference / "stage4_structure.json").write_text("{}", encoding="utf-8")
        (reference / "resume.yaml").write_text("cv: {}\n", encoding="utf-8")
        assert case.reference_stages() == [StageKey.STRUCTURE]


class TestLoadMatrix:
    def test_the_shipped_matrix_loads(self) -> None:
        matrix = load_matrix(DEFAULT_MATRIX)
        assert len(matrix.models) == 11

    def test_the_shipped_run_settings_match_the_design(self) -> None:
        run = load_matrix(DEFAULT_MATRIX).run
        assert (run.repeats, run.concurrency, run.preset, run.cases) == (
            2,
            2,
            "standard",
            ["*"],
        )

    def test_the_shipped_matrix_runs_every_evaluated_stage(self) -> None:
        assert tuple(load_matrix(DEFAULT_MATRIX).run.stages) == EVALUATED_STAGES

    def test_run_settings_default_to_every_evaluated_stage(
        self, tmp_path: Path
    ) -> None:
        matrix = load_matrix(_write_matrix(tmp_path, _MINIMAL_MATRIX))
        assert tuple(matrix.run.stages) == EVALUATED_STAGES

    def test_the_shipped_reference_model(self) -> None:
        matrix = load_matrix(DEFAULT_MATRIX)
        assert (matrix.reference.provider, matrix.reference.model) == (
            "anthropic",
            "claude-opus-5-5",
        )

    def test_the_shipped_judge_panel_has_one_judge_per_provider(self) -> None:
        panel = load_matrix(DEFAULT_MATRIX).panel
        assert [j.label for j in panel] == [
            "anthropic/claude-opus-5-5",
            "openai/gpt-6-astra",
            "google/gemini-4-argon",
        ]

    def test_every_shipped_judge_is_its_providers_top_tier(self) -> None:
        catalog = ModelCatalog.builtin()
        tiers = {
            j.label: resolved.tier
            if (resolved := catalog.lookup(j.provider, j.model))
            else None
            for j in load_matrix(DEFAULT_MATRIX).panel
        }
        assert set(tiers.values()) == {ModelTier.FRONTIER}

    def test_every_shipped_judge_is_priced(self) -> None:
        catalog = ModelCatalog.builtin()
        assert all(
            catalog.price_for(j.model, provider=j.provider) is not None
            for j in load_matrix(DEFAULT_MATRIX).panel
        )

    def test_a_single_judge_table_is_a_panel_of_one(self, tmp_path: Path) -> None:
        matrix = load_matrix(_write_matrix(tmp_path, _MINIMAL_MATRIX))
        assert [j.label for j in matrix.panel] == ["anthropic/claude-opus-5-5"]

    def test_a_judges_array_is_the_panel(self, tmp_path: Path) -> None:
        body = _MINIMAL_MATRIX.replace(
            '[judge]\nprovider = "anthropic"\nmodel = "claude-opus-5-5"\n',
            _PANEL,
        )
        matrix = load_matrix(_write_matrix(tmp_path, body))
        assert [j.label for j in matrix.panel] == [
            "anthropic/claude-opus-5-5",
            "google/gemini-4-argon",
        ]

    def test_a_judge_table_and_a_judges_array_together_are_rejected(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(ValueError, match=r"\[judge\] or \[\[judges\]\]"):
            load_matrix(_write_matrix(tmp_path, _MINIMAL_MATRIX + _PANEL))

    def test_a_matrix_without_any_judge_is_rejected(self, tmp_path: Path) -> None:
        body = _MINIMAL_MATRIX.replace(
            '[judge]\nprovider = "anthropic"\nmodel = "claude-opus-5-5"\n', ""
        )
        with pytest.raises(ValueError, match="judge"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_the_same_judge_twice_is_rejected(self, tmp_path: Path) -> None:
        body = _MINIMAL_MATRIX.replace(
            '[judge]\nprovider = "anthropic"\nmodel = "claude-opus-5-5"\n',
            _PANEL + _PANEL,
        )
        with pytest.raises(ValueError, match="judges listed more than once"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_every_shipped_model_is_priced_in_the_builtin_catalog(self) -> None:
        catalog = ModelCatalog.builtin()
        unpriced = [
            f"{m.provider}/{m.model}"
            for m in load_matrix(DEFAULT_MATRIX).models
            if catalog.price_for(m.model, provider=m.provider) is None
        ]
        assert unpriced == []

    def test_every_shipped_provider_is_a_builtin_provider(self) -> None:
        providers = {m.provider for m in load_matrix(DEFAULT_MATRIX).models}
        assert providers <= set(BUILTIN_PROVIDERS)

    def test_the_shipped_recommendation_rule_is_quality_first(self) -> None:
        settings = load_matrix(DEFAULT_MATRIX).recommendation
        assert (settings.tie_epsilon, settings.max_fabrication_rate) == (0.01, 0.0)

    def test_recommendation_defaults_apply_when_omitted(self, tmp_path: Path) -> None:
        settings = load_matrix(_write_matrix(tmp_path, _MINIMAL_MATRIX)).recommendation
        assert (settings.tie_epsilon, settings.max_fabrication_rate) == (0.01, 0.0)

    def test_the_shipped_matrix_judges_only_where_it_adds_signal(self) -> None:
        judged = load_matrix(DEFAULT_MATRIX).run.judged_stages
        assert StageKey.ANALYZE not in judged
        assert StageKey.STRUCTURE not in judged
        assert StageKey.TAILOR in judged

    def test_judges_can_be_turned_on_for_structure(self, tmp_path: Path) -> None:
        body = '[run]\njudged_stages = ["structure"]\n' + _MINIMAL_MATRIX
        matrix = load_matrix(_write_matrix(tmp_path, body))
        assert matrix.run.judged_stages == [StageKey.STRUCTURE]

    def test_the_shipped_matrix_batches_with_the_vertex_bucket(self) -> None:
        batch = load_matrix(DEFAULT_MATRIX).batch
        assert batch.enabled is True
        assert batch.google_gcs_bucket == "gs://destinyventures-mkcv-evals"

    def test_the_shipped_batch_discount_is_half_for_the_three_providers(
        self,
    ) -> None:
        pricing = load_matrix(DEFAULT_MATRIX).pricing
        assert pricing.batch_discount == {
            "anthropic": 0.5,
            "openai": 0.5,
            "google": 0.5,
        }

    def test_a_matrix_without_a_batch_table_calls_online(self, tmp_path: Path) -> None:
        assert (
            load_matrix(_write_matrix(tmp_path, _MINIMAL_MATRIX)).batch.enabled is False
        )

    def test_the_tie_epsilon_can_be_set(self, tmp_path: Path) -> None:
        body = "[recommendation]\ntie_epsilon = 0.02\n" + _MINIMAL_MATRIX
        settings = load_matrix(_write_matrix(tmp_path, body)).recommendation
        assert settings.tie_epsilon == 0.02

    def test_an_unknown_recommendation_setting_is_rejected(
        self, tmp_path: Path
    ) -> None:
        body = "[recommendation]\nmargin = 0.05\n" + _MINIMAL_MATRIX
        with pytest.raises(ValueError, match="margin"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_defaults_apply_when_run_settings_are_omitted(self, tmp_path: Path) -> None:
        matrix = load_matrix(_write_matrix(tmp_path, _MINIMAL_MATRIX))
        assert (matrix.run.repeats, matrix.run.concurrency) == (1, 2)

    def test_model_temperature_is_optional(self, tmp_path: Path) -> None:
        body = _MINIMAL_MATRIX + "temperature = 0.4\n"
        matrix = load_matrix(_write_matrix(tmp_path, body))
        assert matrix.models[0].temperature == 0.4

    def test_model_temperature_defaults_to_none(self, tmp_path: Path) -> None:
        matrix = load_matrix(_write_matrix(tmp_path, _MINIMAL_MATRIX))
        assert matrix.models[0].temperature is None

    def test_missing_file_is_reported(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match=r"nope\.toml"):
            load_matrix(tmp_path / "nope.toml")

    def test_unknown_top_level_key_is_rejected(self, tmp_path: Path) -> None:
        body = _MINIMAL_MATRIX + "\n[extras]\nx = 1\n"
        with pytest.raises(ValueError, match="extras"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_a_matrix_needs_at_least_one_model(self, tmp_path: Path) -> None:
        body = _MINIMAL_MATRIX.split("[[models]]")[0]
        with pytest.raises(ValueError, match="models"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_an_empty_model_list_is_rejected(self, tmp_path: Path) -> None:
        body = "models = []\n" + _MINIMAL_MATRIX.split("[[models]]")[0]
        with pytest.raises(ValueError, match=r"at least one \[\[models\]\]"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_only_pipeline_stages_can_be_run(self, tmp_path: Path) -> None:
        body = '[run]\nstages = ["kb"]\n' + _MINIMAL_MATRIX
        with pytest.raises(ValueError, match="kb"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_repeats_must_be_positive(self, tmp_path: Path) -> None:
        body = "[run]\nrepeats = 0\n" + _MINIMAL_MATRIX
        with pytest.raises(ValueError, match="repeats"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_the_same_model_twice_is_rejected(self, tmp_path: Path) -> None:
        body = _MINIMAL_MATRIX + '\n[[models]]\nprovider = "anthropic"\n'
        body += 'model = "claude-haiku-5-5"\n'
        with pytest.raises(ValueError, match="anthropic/claude-haiku-5-5"):
            load_matrix(_write_matrix(tmp_path, body))

    def test_invalid_toml_is_a_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match=r"matrix\.toml"):
            load_matrix(_write_matrix(tmp_path, "[run\n"))


_LETTER_CASE = """
[[cases]]
id = "a"
persona = "personas/alpha.md"
jd = "jds/alpha-match.md"
forbidden_claims = ["PyTorch", "MLflow"]

[cases.cover_letter]
company = "Acme Corp"
role = "Platform Engineer"
must_not_claim = ["MLflow", "led a team of 20"]
should_connect = ["Kubernetes migration at Initech -> cluster operations"]
must = ["lead with the Kubernetes migration"]
must_not = ["describe a departure as voluntary"]
min_words = 200
max_words = 350
"""


class TestCoverLetterExpectations:
    def _case(self, fixtures: Path, body: str = _LETTER_CASE) -> EvalCase:
        (fixtures / "cases.toml").write_text(body, encoding="utf-8")
        return load_cases(fixtures)[0]

    def test_a_case_without_a_cover_letter_table_writes_no_letter(
        self, tmp_fixtures: Path
    ) -> None:
        probe = load_cases(tmp_fixtures)[1].model_copy(update={"stages": None})
        assert probe.cover_letter is None
        assert not probe.applies_to(StageKey.COVER_LETTER_GENERATE)
        assert not probe.applies_to(StageKey.COVER_LETTER_REVIEW)
        assert probe.applies_to(StageKey.TAILOR)

    def test_a_cover_letter_table_turns_the_letter_stages_on(
        self, tmp_fixtures: Path
    ) -> None:
        case = load_cases(tmp_fixtures)[0]
        assert case.applies_to(StageKey.COVER_LETTER_GENERATE)
        assert case.applies_to(StageKey.COVER_LETTER_REVIEW)

    def test_stages_that_name_a_letter_stage_need_no_table(
        self, tmp_fixtures: Path
    ) -> None:
        probe = load_cases(tmp_fixtures)[1].model_copy(
            update={"stages": [StageKey.COVER_LETTER_REVIEW]}
        )
        assert probe.applies_to(StageKey.COVER_LETTER_REVIEW)

    def test_an_empty_table_gets_the_defaults(self, tmp_fixtures: Path) -> None:
        letter = load_cases(tmp_fixtures)[0].letter
        assert (letter.company, letter.role, letter.must_not_claim) == (None, None, [])
        assert (letter.min_words, letter.max_words) == (250, 400)
        assert (letter.should_connect, letter.review_defects) == ([], [])

    def test_the_cover_letter_table_is_read(self, tmp_fixtures: Path) -> None:
        letter = self._case(tmp_fixtures).letter
        assert (letter.company, letter.role) == ("Acme Corp", "Platform Engineer")
        assert letter.should_connect == [
            "Kubernetes migration at Initech -> cluster operations"
        ]
        assert (letter.min_words, letter.max_words) == (200, 350)
        assert letter.must == ["lead with the Kubernetes migration"]
        assert letter.must_not == ["describe a departure as voluntary"]

    def test_the_letter_must_not_claim_the_forbidden_claims_either(
        self, tmp_fixtures: Path
    ) -> None:
        assert self._case(tmp_fixtures).cover_letter_forbidden == [
            "PyTorch",
            "MLflow",
            "led a team of 20",
        ]

    def test_an_unknown_cover_letter_key_is_rejected(self, tmp_fixtures: Path) -> None:
        with pytest.raises(ValueError, match="tone"):
            self._case(tmp_fixtures, _LETTER_CASE + 'tone = "warm"\n')

    def test_the_word_bounds_must_be_in_order(self, tmp_fixtures: Path) -> None:
        body = _LETTER_CASE.replace("min_words = 200", "min_words = 500")
        with pytest.raises(ValueError, match="min_words"):
            self._case(tmp_fixtures, body)

    def test_seeded_review_defects_make_a_cover_letter_probe(
        self, tmp_fixtures: Path
    ) -> None:
        body = _LETTER_CASE + 'review_defects = ["placeholder [Company] left in"]\n'
        case = self._case(tmp_fixtures, body)
        assert case.is_cover_letter_probe is True

    def test_a_case_without_seeded_defects_is_not_a_probe(
        self, tmp_fixtures: Path
    ) -> None:
        assert self._case(tmp_fixtures).is_cover_letter_probe is False


class TestNeededReferences:
    def test_a_full_case_needs_stages_one_to_four_and_a_cover_letter(
        self, tmp_fixtures: Path
    ) -> None:
        assert load_cases(tmp_fixtures)[0].needed_reference_stages() == [
            StageKey.ANALYZE,
            StageKey.SELECT,
            StageKey.TAILOR,
            StageKey.STRUCTURE,
            StageKey.COVER_LETTER_GENERATE,
        ]

    def test_a_review_probe_needs_only_stages_one_to_four(
        self, tmp_fixtures: Path
    ) -> None:
        assert load_cases(tmp_fixtures)[1].needed_reference_stages() == [
            StageKey.ANALYZE,
            StageKey.SELECT,
            StageKey.TAILOR,
            StageKey.STRUCTURE,
        ]

    def test_a_cover_letter_review_case_needs_only_a_letter(
        self, tmp_fixtures: Path
    ) -> None:
        (tmp_fixtures / "cases.toml").write_text(
            '[[cases]]\nid = "a"\npersona = "personas/alpha.md"\n'
            'jd = "jds/alpha-match.md"\nstages = ["cover_letter.review"]\n',
            encoding="utf-8",
        )
        assert load_cases(tmp_fixtures)[0].needed_reference_stages() == [
            StageKey.COVER_LETTER_GENERATE
        ]

    def test_the_cover_letter_reference_is_its_own_stage(
        self, tmp_fixtures: Path
    ) -> None:
        case = load_cases(tmp_fixtures)[0]
        case.reference_dir.mkdir(parents=True)
        (case.reference_dir / "cover_letter_content.json").write_text("{}")
        assert case.reference_stages() == [StageKey.COVER_LETTER_GENERATE]


def test_the_shipped_matrix_caches_the_judges_prefix() -> None:
    assert load_matrix(DEFAULT_MATRIX).caching.enabled is True
