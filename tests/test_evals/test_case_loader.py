"""Tests for case loading and matrix parsing (REQ-EV-1, REQ-EV-2, design 9.3-9.4)."""

import json
from pathlib import Path

import pytest

from evals.harness.case_loader import load_cases, load_matrix, select_cases
from evals.models.eval_case import EvalCase
from mkcv.adapters.llm.builtin_providers import BUILTIN_PROVIDERS
from mkcv.core.models.model_catalog import ModelCatalog
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey
from tests.test_evals.conftest import JD_TEXT, PERSONA_TEXT

DEFAULT_MATRIX = (
    Path(__file__).resolve().parents[2] / "evals" / "config" / "matrix.toml"
)


def _write_matrix(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "matrix.toml"
    path.write_text(body, encoding="utf-8")
    return path


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

    def test_a_case_may_only_name_pipeline_stages(self, tmp_fixtures: Path) -> None:
        (tmp_fixtures / "cases.toml").write_text(
            '[[cases]]\nid = "a"\npersona = "personas/alpha.md"\n'
            'jd = "jds/alpha-match.md"\nstages = ["kb"]\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="not resume pipeline stages"):
            load_cases(tmp_fixtures)

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
        assert len(matrix.models) == 10

    def test_the_shipped_run_settings_match_the_design(self) -> None:
        run = load_matrix(DEFAULT_MATRIX).run
        assert (run.repeats, run.concurrency, run.preset, run.cases) == (
            1,
            2,
            "standard",
            ["*"],
        )

    def test_the_shipped_matrix_runs_every_pipeline_stage(self) -> None:
        assert tuple(load_matrix(DEFAULT_MATRIX).run.stages) == PIPELINE_STAGES

    def test_the_shipped_judge_and_reference_models(self) -> None:
        matrix = load_matrix(DEFAULT_MATRIX)
        assert (matrix.judge.provider, matrix.judge.model) == (
            "anthropic",
            "claude-opus-5-5",
        )
        assert (matrix.reference.provider, matrix.reference.model) == (
            "anthropic",
            "claude-opus-5-5",
        )

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
