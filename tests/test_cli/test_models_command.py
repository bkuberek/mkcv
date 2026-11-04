"""Tests for the mkcv models command (REQ-MP-13 to MP-15, design section 8.4)."""

import json
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from dynaconf import Dynaconf
from rich.console import Console

import mkcv
from mkcv.adapters.factory import create_model_report
from mkcv.core.catalog.builtin_model_profiles import BUILTIN_MODEL_PROFILES
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.model_report import ModelReport
from mkcv.core.models.stage_key import StageKey

_CMD = "mkcv.cli.commands.models"
_BUNDLED_SETTINGS = Path(mkcv.__file__).resolve().parent / "config" / "settings.toml"
_KEY_VARIABLES = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
)
_STAGE_ORDER = [
    "analyze",
    "select",
    "tailor",
    "structure",
    "review",
    "cover_letter.generate",
    "cover_letter.review",
    "kb",
    "validate",
]
_COLUMNS = ["Stage", "Provider", "Model", "Source", "Recommended", "Tier", "Est. cost"]
_WEAK_TAILOR = """
[default.pipeline.stages.tailor]
provider = "openai"
model = "gpt-6.1-terra"
"""
_GROQ = """
[default.providers.groq]
type = "openai-compatible"
base_url = "https://api.groq.com/openai/v1"
api_key_env = "GROQ_API_KEY"
"""


def _settings(tmp_path: Path, user_toml: str = "") -> Dynaconf:
    layers = [str(_BUNDLED_SETTINGS)]
    if user_toml:
        user_file = tmp_path / "user.toml"
        user_file.write_text(user_toml)
        layers.append(str(user_file))
    config = Dynaconf(
        settings_files=layers,
        environments=True,
        default_env="default",
        merge_enabled=True,
    )
    config.set("in_workspace", False)
    config.set("workspace_root", None)
    return config


@pytest.fixture(autouse=True)
def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable in _KEY_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant")


@pytest.fixture
def run(tmp_path: Path) -> Callable[..., str]:
    """Run ``models_command`` on a wide console and return what it printed."""

    def _run(user_toml: str = "", *, width: int = 240, **options: object) -> str:
        from mkcv.cli.commands.models import models_command

        buffer = StringIO()
        wide = Console(file=buffer, width=width, force_terminal=False)
        with (
            patch(f"{_CMD}.settings", _settings(tmp_path, user_toml)),
            patch(f"{_CMD}.console", wide),
        ):
            models_command(**options)  # type: ignore[arg-type]
        return buffer.getvalue()

    return _run


def _table_rows(output: str) -> dict[str, list[str]]:
    """Map each stage name to the cells of its row in the default view."""
    rows: dict[str, list[str]] = {}
    for line in output.splitlines():
        cells = line.split()
        if cells and cells[0] in _STAGE_ORDER:
            rows[cells[0]] = cells
    return rows


class TestDefaultView:
    """REQ-MP-13."""

    def test_the_header_names_the_profile_and_that_it_is_provisional(
        self, run: Callable[..., str]
    ) -> None:
        assert (
            "Model profile: anthropic (provisional: not yet backed by an eval run)"
            in run()
        )

    def test_the_source_line_says_the_profile_is_the_default(
        self, run: Callable[..., str]
    ) -> None:
        assert (
            "Source: default (no --model-profile, no pipeline.model_profile)" in run()
        )

    def test_the_preset_is_named(self, run: Callable[..., str]) -> None:
        assert "Preset: standard" in run()

    def test_there_is_one_row_per_stage_in_order(self, run: Callable[..., str]) -> None:
        first_cells = [line.split()[0] for line in run().splitlines() if line.split()]
        assert [cell for cell in first_cells if cell in _STAGE_ORDER] == _STAGE_ORDER

    def test_the_column_headers_are_present_in_order(
        self, run: Callable[..., str]
    ) -> None:
        header = next(
            line for line in run().splitlines() if line.split()[:1] == ["Stage"]
        )
        assert header.replace("Est. cost", "Est.cost").split() == [
            "Stage",
            "Provider",
            "Model",
            "Source",
            "Recommended",
            "Tier",
            "Est.cost",
        ]

    def test_rows_show_the_providers_models_and_sources(
        self, run: Callable[..., str]
    ) -> None:
        analyze = _table_rows(run())["analyze"]
        assert analyze[:4] == ["analyze", "anthropic", "claude-haiku-5-5", "profile"]

    def test_rows_show_the_recommended_model_and_tier(
        self, run: Callable[..., str]
    ) -> None:
        select = _table_rows(run())["select"]
        assert select[4:6] == ["anthropic/claude-opus-5-5", "frontier"]

    def test_the_cost_cell_has_four_decimals(
        self, run: Callable[..., str], tmp_path: Path
    ) -> None:
        report = create_model_report(_settings(tmp_path), preset_name="standard")
        cost = report.stages[0].estimated_cost_usd
        assert cost is not None
        assert _table_rows(run())["analyze"][-1] == f"${cost:.4f}"

    def test_the_run_estimate_sums_the_five_pipeline_stages(
        self, run: Callable[..., str], tmp_path: Path
    ) -> None:
        report = create_model_report(
            _settings(tmp_path),
            preset_name="standard",
            include_cover_letter=True,
            extra_stages=(StageKey.KB, StageKey.VALIDATE),
        )
        total, _ = report.resume_run_estimate()
        assert total is not None
        assert report.estimated_total_usd is not None
        assert f"${report.estimated_total_usd:.2f}" != f"${total:.2f}"
        assert f"Estimated cost per resume run (5 stages): ${total:.2f}\n" in run()

    def test_the_estimate_note_points_at_the_docs(
        self, run: Callable[..., str]
    ) -> None:
        assert (
            "Estimates use rough per-stage token counts; see docs/models.md." in run()
        )

    def test_there_is_no_warnings_section_without_warnings(
        self, run: Callable[..., str]
    ) -> None:
        assert "Warnings:" not in run()

    def test_stage_requirements_drive_the_row_set(self) -> None:
        assert [stage.value for stage in STAGE_REQUIREMENTS] == _STAGE_ORDER


class TestWarningsSection:
    def test_weak_choices_are_listed_under_warnings(
        self, run: Callable[..., str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        output = run(_WEAK_TAILOR)
        assert (
            "  tailor: openai/gpt-6.1-terra is tier 'efficient'; mkcv "
            "recommends at least 'strong' for this stage "
            "(recommended: openai/gpt-6-astra).\n" in output
        )

    def test_a_missing_key_is_listed(self, run: Callable[..., str]) -> None:
        output = run(_WEAK_TAILOR)
        assert (
            "  openai: no API key found (set OPENAI_API_KEY); a run that uses "
            "it stops with a configuration error.\n" in output
        )

    def test_bracketed_config_paths_in_warnings_survive(
        self, run: Callable[..., str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        output = run(
            """
[default.pipeline.stages.analyze]
provider = "openai"
model = "gpt-7-nova"
"""
        )
        assert "[[default.model_catalog]]" in output

    def test_a_recommendation_for_the_weak_row_is_shown(
        self, run: Callable[..., str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        tailor = _table_rows(run(_WEAK_TAILOR))["tailor"]
        assert tailor[1:6] == [
            "openai",
            "gpt-6.1-terra",
            "config",
            "openai/gpt-6-astra",
            "efficient",
        ]


class TestUnknownPrices:
    _UNKNOWN_ANALYZE = """
[default.pipeline.stages.analyze]
provider = "openai"
model = "gpt-7-nova"
"""

    def test_an_unpriced_stage_shows_not_available(
        self, run: Callable[..., str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        assert _table_rows(run(self._UNKNOWN_ANALYZE))["analyze"][-1] == "n/a"

    def test_an_unknown_model_shows_an_unknown_tier(
        self, run: Callable[..., str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        assert _table_rows(run(self._UNKNOWN_ANALYZE))["analyze"][5] == "unknown"

    def test_a_partial_estimate_says_so(
        self, run: Callable[..., str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        output = run(self._UNKNOWN_ANALYZE)
        assert "(partial: some prices unknown)" in output

    def test_a_complete_estimate_does_not_say_partial(
        self, run: Callable[..., str]
    ) -> None:
        assert "partial" not in run()

    def test_with_no_known_price_the_estimate_is_not_available(
        self, run: Callable[..., str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        every_stage = "".join(
            f'[default.{requirement.config_path}]\nprovider = "openai"\n'
            'model = "gpt-7-nova"\n'
            for requirement in STAGE_REQUIREMENTS.values()
            if requirement.config_path.startswith("pipeline.stages.")
        )
        assert "Estimated cost per resume run (5 stages): n/a\n" in run(every_stage)


class TestProfileHeader:
    def test_without_a_profile_the_header_says_all_stages_are_explicit(
        self, run: Callable[..., str]
    ) -> None:
        every_stage = "".join(
            f'[default.{requirement.config_path}]\nprovider = "groq"\nmodel = "m"\n'
            for requirement in STAGE_REQUIREMENTS.values()
        )
        output = run(_GROQ + '[default.pipeline]\nprovider = "groq"\n' + every_stage)
        assert "Model profile: none (all stages set explicitly)" in output

    def test_an_eval_backed_profile_names_its_run(self) -> None:
        from mkcv.cli.commands.models import _profile_headline

        evidenced = BUILTIN_MODEL_PROFILES["openai"].model_copy(
            update={"evidence": "eval", "eval_run": "2026-12-01-run"}
        )
        report = ModelReport(
            profile_name="openai",
            profile_evidence="eval",
            profile_source="cli",
            preset_name="standard",
            stages=[],
            warnings=[],
            estimated_total_usd=None,
            estimate_is_partial=False,
        )
        with patch(f"{_CMD}.get_profile", return_value=evidenced):
            assert (
                _profile_headline(report)
                == "Model profile: openai (eval-backed: 2026-12-01-run)"
            )


class TestFlags:
    """REQ-MP-14."""

    def test_a_model_profile_flag_switches_every_row(
        self, run: Callable[..., str]
    ) -> None:
        output = run(model_profile="openai")
        assert "Model profile: openai (provisional" in output
        assert {row[1] for row in _table_rows(output).values()} == {"openai"}

    def test_rows_under_a_profile_flag_have_source_cli(
        self, run: Callable[..., str]
    ) -> None:
        sources = {row[3] for row in _table_rows(run(model_profile="openai")).values()}
        assert sources == {"cli"}

    def test_the_source_line_names_the_flag(self, run: Callable[..., str]) -> None:
        assert "Source: cli (--model-profile)" in run(model_profile="openai")

    def test_a_provider_flag_switches_every_row(self, run: Callable[..., str]) -> None:
        output = run(provider="google")
        assert {row[1] for row in _table_rows(output).values()} == {"google"}
        assert "Source: cli (--provider)" in output

    def test_the_concise_preset_selects_the_economy_profile(
        self, run: Callable[..., str]
    ) -> None:
        output = run(preset="concise")
        assert "Model profile: anthropic-economy (provisional" in output
        assert "Preset: concise" in output

    def test_the_legacy_budget_preset_is_named_as_the_source(
        self, run: Callable[..., str]
    ) -> None:
        output = run(preset="budget")
        assert "Source: preset (budget)" in output
        assert {row[1] for row in _table_rows(output).values()} == {"ollama"}

    def test_a_configured_profile_is_named_as_config(
        self, run: Callable[..., str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "g")
        output = run('[default.pipeline]\nmodel_profile = "google"\n')
        assert "Source: config (pipeline.model_profile or pipeline.provider)" in output

    def test_local_models_cost_nothing(self, run: Callable[..., str]) -> None:
        output = run(model_profile="local")
        assert _table_rows(output)["analyze"][-1] == "$0.0000"


class TestProfilesView:
    def test_all_seven_profiles_are_listed(self, run: Callable[..., str]) -> None:
        output = run(profiles=True)
        for name in BUILTIN_MODEL_PROFILES:
            assert any(line.split()[:1] == [name] for line in output.splitlines())

    def test_each_profile_shows_its_provider_economy_flag_and_evidence(
        self, run: Callable[..., str]
    ) -> None:
        lines = run(profiles=True).splitlines()
        row = next(line for line in lines if line.split()[:1] == ["openai-economy"])
        assert row.split()[1:4] == ["openai", "yes", "provisional"]

    def test_each_profile_shows_its_description(self, run: Callable[..., str]) -> None:
        output = run(profiles=True)
        assert "Low-cost OpenAI mix: Luna and Terra." in output

    def test_each_profile_lists_every_one_of_its_stage_models(
        self, run: Callable[..., str]
    ) -> None:
        listed = [line.split() for line in run(profiles=True).splitlines()]
        missing = [
            (profile.name, stage.value, model)
            for profile in BUILTIN_MODEL_PROFILES.values()
            for stage, model in profile.stages.items()
            if [stage.value, model] not in listed
        ]
        assert missing == []

    def test_an_economy_profile_points_at_the_profile_it_extends(
        self, run: Callable[..., str]
    ) -> None:
        assert "Other stages: as anthropic" in run(profiles=True)

    def test_json_is_a_list_of_the_seven_profiles(
        self, run: Callable[..., str]
    ) -> None:
        data = json.loads(run(profiles=True, as_json=True))
        assert [profile["name"] for profile in data] == list(BUILTIN_MODEL_PROFILES)

    def test_json_profiles_carry_their_stage_models(
        self, run: Callable[..., str]
    ) -> None:
        data = json.loads(run(profiles=True, as_json=True))
        anthropic = next(profile for profile in data if profile["name"] == "anthropic")
        assert anthropic["stages"]["tailor"] == "claude-opus-5-5"


class TestCatalogView:
    def test_a_provider_filter_lists_only_that_providers_entries(
        self, run: Callable[..., str]
    ) -> None:
        output = run(catalog=True, provider="google")
        assert "gemini-4-argon" in output
        assert "claude-opus-5-5" not in output

    def test_prices_are_shown_per_million_tokens(self, run: Callable[..., str]) -> None:
        output = run(catalog=True, provider="google")
        row = next(line for line in output.splitlines() if "gemini-4-argon" in line)
        assert "4.00" in row
        assert "20.00" in row

    def test_every_provider_is_listed_without_a_filter(
        self, run: Callable[..., str]
    ) -> None:
        output = run(catalog=True)
        assert "claude-opus-5-5" in output
        assert "gemini-4-argon" in output
        assert "gpt-6.1-terra" in output

    def test_user_overrides_are_included(self, run: Callable[..., str]) -> None:
        output = run(
            _GROQ
            + """
[[default.model_catalog]]
provider = "groq"
match = "llama-3.3-70b-versatile"
tier = "strong"
""",
            catalog=True,
            provider="groq",
        )
        assert "llama-3.3-70b-versatile" in output

    def test_the_columns_describe_each_entry(self, run: Callable[..., str]) -> None:
        header = next(
            line
            for line in run(catalog=True).splitlines()
            if line.split()[:1] == ["Provider"]
        )
        for column in ("Match", "Type", "Tier", "Structured output", "Sampling"):
            assert column in header

    def test_effective_sampling_support_is_shown(self, run: Callable[..., str]) -> None:
        output = run(catalog=True, provider="anthropic")
        row = next(line for line in output.splitlines() if "claude-opus-5-5" in line)
        assert "no" in row.split()

    def test_prefix_entries_say_so(self, run: Callable[..., str]) -> None:
        output = run(catalog=True, provider="ollama")
        row = next(line for line in output.splitlines() if "llama3.1" in line)
        assert "prefix" in row.split()

    def test_notes_are_shown(self, run: Callable[..., str]) -> None:
        output = run(catalog=True, provider="google")
        assert "Promotional" in output

    def test_notes_with_brackets_are_not_swallowed(
        self, run: Callable[..., str]
    ) -> None:
        output = run(
            _GROQ
            + """
[[default.model_catalog]]
provider = "groq"
match = "m"
notes = "see [default.providers.groq]"
""",
            catalog=True,
            provider="groq",
        )
        assert "[default.providers.groq]" in output

    def test_an_entry_for_an_undefined_provider_is_still_listed(
        self, run: Callable[..., str]
    ) -> None:
        output = run(
            """
[[default.model_catalog]]
provider = "mystery"
match = "m-1"
""",
            catalog=True,
            provider=None,
        )
        assert "mystery" in output

    def test_a_deprecated_entry_without_notes_says_deprecated(
        self, run: Callable[..., str]
    ) -> None:
        output = run(
            _GROQ
            + """
[[default.model_catalog]]
provider = "groq"
match = "old-model"
deprecated = true
""",
            catalog=True,
            provider="groq",
        )
        row = next(line for line in output.splitlines() if "old-model" in line)
        assert "deprecated" in row.split()

    def test_a_provider_without_entries_says_so(self, run: Callable[..., str]) -> None:
        assert "No catalog entries for provider 'stub'" in run(
            catalog=True, provider="stub"
        )

    def test_an_unknown_provider_is_a_configuration_error(
        self, run: Callable[..., str]
    ) -> None:
        with pytest.raises(ConfigurationError, match="Unknown LLM provider 'nope'"):
            run(catalog=True, provider="nope")

    def test_json_is_a_filtered_list_of_entries(self, run: Callable[..., str]) -> None:
        data = json.loads(run(catalog=True, provider="google", as_json=True))
        assert {entry["provider"] for entry in data} == {"google"}
        argon = next(entry for entry in data if entry["match"] == "gemini-4-argon")
        assert (argon["input_price_per_mtok"], argon["output_price_per_mtok"]) == (
            4.0,
            20.0,
        )


class TestJsonView:
    def test_the_default_view_validates_as_a_model_report(
        self, run: Callable[..., str]
    ) -> None:
        report = ModelReport.model_validate_json(run(as_json=True))
        assert report.profile_name == "anthropic"

    def test_the_json_report_has_a_row_per_stage(self, run: Callable[..., str]) -> None:
        report = ModelReport.model_validate_json(run(as_json=True))
        assert [a.assignment.stage.value for a in report.stages] == _STAGE_ORDER

    def test_json_output_is_only_json(self, run: Callable[..., str]) -> None:
        output = run(as_json=True)
        assert json.loads(output)["preset_name"] == "standard"

    def test_json_follows_the_flags(self, run: Callable[..., str]) -> None:
        report = ModelReport.model_validate_json(
            run(as_json=True, model_profile="local")
        )
        assert report.profile_name == "local"


class TestJsonIsPrintedVerbatim:
    _NOTES = """
[[default.model_catalog]]
provider = "groq"
match = "m"
notes = "see [default.providers.groq] :rocket: for details, and a long note"
"""

    def test_json_is_not_wrapped_on_a_narrow_console(
        self, run: Callable[..., str]
    ) -> None:
        output = run(_GROQ + self._NOTES, width=40, catalog=True, as_json=True)
        assert json.loads(output)

    def test_json_keeps_brackets_and_emoji_codes(self, run: Callable[..., str]) -> None:
        output = run(
            _GROQ + self._NOTES, width=40, catalog=True, provider="groq", as_json=True
        )
        assert json.loads(output)[0]["notes"].startswith(
            "see [default.providers.groq] :rocket: for details"
        )


class TestRunsWithoutProviders:
    def test_no_adapter_is_created(self, run: Callable[..., str]) -> None:
        with patch(
            "mkcv.adapters.llm.provider_registry.ProviderRegistry.create_adapter"
        ) as create_adapter:
            run()
        create_adapter.assert_not_called()


class TestExitCodes:
    """REQ-MP-15, through the real entry point."""

    @pytest.fixture(autouse=True)
    def _in_an_empty_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

    @pytest.fixture
    def invoke(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> Callable[..., tuple[int, str, str]]:
        from mkcv.cli.app import app

        def _invoke(user_toml: str, *tokens: str) -> tuple[int, str, str]:
            with (
                patch(f"{_CMD}.settings", _settings(tmp_path, user_toml)),
                patch("mkcv.cli.app.logging.basicConfig"),
            ):
                try:
                    app.meta(["models", *tokens])
                except SystemExit as exit_info:
                    code = int(exit_info.code or 0)
                else:
                    code = 0
            captured = capsys.readouterr()
            return code, captured.out, captured.err

        return _invoke

    def test_a_successful_run_exits_zero(
        self, invoke: Callable[..., tuple[int, str, str]]
    ) -> None:
        code, out, _ = invoke("", "--profiles")
        assert code == 0
        assert "anthropic-economy" in out

    def test_an_unknown_configured_profile_exits_3(
        self, invoke: Callable[..., tuple[int, str, str]]
    ) -> None:
        code, _, err = invoke('[default.pipeline]\nmodel_profile = "nope"\n')
        assert code == 3
        assert "Unknown model profile 'nope'" in err

    def test_a_provider_without_a_profile_or_models_exits_3(
        self, invoke: Callable[..., tuple[int, str, str]]
    ) -> None:
        code, _, err = invoke('[default.pipeline]\nprovider = "openrouter"\n')
        assert code == 3
        assert "Cannot resolve models:" in err

    def test_the_unresolved_stages_keep_their_bracketed_config_paths(
        self, invoke: Callable[..., tuple[int, str, str]]
    ) -> None:
        _, _, err = invoke('[default.pipeline]\nprovider = "openrouter"\n')
        assert "[default.pipeline.stages.analyze]" in err

    def test_profile_and_provider_flags_exit_3(
        self, invoke: Callable[..., tuple[int, str, str]]
    ) -> None:
        code, _, err = invoke("", "--model-profile", "google", "--provider", "openai")
        assert code == 3
        assert "cannot be used together" in err

    def test_an_unknown_catalog_provider_exits_3(
        self, invoke: Callable[..., tuple[int, str, str]]
    ) -> None:
        code, _, err = invoke("", "--catalog", "--provider", "nope")
        assert code == 3
        assert "Unknown LLM provider 'nope'" in err

    def test_profiles_and_catalog_together_exit_2(
        self, invoke: Callable[..., tuple[int, str, str]]
    ) -> None:
        code, _, err = invoke("", "--profiles", "--catalog")
        assert code == 2
        assert "--profiles" in err
