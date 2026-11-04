"""Tests for the CLI's model warning output (design section 8.3)."""

from io import StringIO

from rich.console import Console

from mkcv.cli.model_warnings import print_model_warnings
from mkcv.core.models.model_report import ModelReport
from mkcv.core.models.model_warning import ModelWarning
from mkcv.core.models.model_warning_kind import ModelWarningKind
from mkcv.core.models.stage_key import StageKey

_TIER_MESSAGE = (
    "tailor: openai/gpt-6.1-terra is tier 'efficient'; mkcv recommends at least "
    "'strong' for this stage (recommended: openai/gpt-6-astra)."
)
_UNKNOWN_MESSAGE = (
    "analyze: no capability data for openai/gpt-7-nova; mkcv will use "
    "conservative defaults. Describe it with a [[default.model_catalog]] entry."
)
_KEY_MESSAGE = (
    "openai: no API key found (set OPENAI_API_KEY); mkcv will use the offline "
    "stub and produce empty output."
)


def _warning(
    kind: ModelWarningKind, message: str, stage: StageKey | None = None
) -> ModelWarning:
    return ModelWarning(
        kind=kind, stage=stage, provider="openai", model=None, message=message
    )


def _report(*warnings: ModelWarning) -> ModelReport:
    return ModelReport(
        profile_name="anthropic",
        profile_evidence="provisional",
        profile_source="default",
        preset_name="standard",
        stages=[],
        warnings=list(warnings),
        estimated_total_usd=None,
        estimate_is_partial=False,
    )


def _printed(report: ModelReport) -> str:
    buffer = StringIO()
    print_model_warnings(report, Console(file=buffer, width=300, force_terminal=False))
    return buffer.getvalue()


class TestPrintModelWarnings:
    def test_each_warning_is_printed_with_a_warning_label(self) -> None:
        out = _printed(
            _report(
                _warning(
                    ModelWarningKind.BELOW_RECOMMENDED_TIER,
                    _TIER_MESSAGE,
                    StageKey.TAILOR,
                )
            )
        )
        assert f"Warning: {_TIER_MESSAGE}" in out

    def test_warnings_are_printed_in_report_order(self) -> None:
        out = _printed(
            _report(
                _warning(ModelWarningKind.MISSING_API_KEY, _KEY_MESSAGE),
                _warning(
                    ModelWarningKind.BELOW_RECOMMENDED_TIER,
                    _TIER_MESSAGE,
                    StageKey.TAILOR,
                ),
            )
        )
        assert out.index(_KEY_MESSAGE) < out.index(_TIER_MESSAGE)

    def test_bracketed_config_paths_in_a_message_survive(self) -> None:
        out = _printed(
            _report(
                _warning(
                    ModelWarningKind.UNKNOWN_MODEL, _UNKNOWN_MESSAGE, StageKey.ANALYZE
                )
            )
        )
        assert "[[default.model_catalog]]" in out

    def test_a_pointer_to_the_models_command_follows_the_warnings(self) -> None:
        out = _printed(
            _report(_warning(ModelWarningKind.MISSING_API_KEY, _KEY_MESSAGE))
        )
        assert out.rstrip().endswith(
            "Run 'mkcv models' for recommended models per stage."
        )

    def test_the_pointer_is_printed_once_for_several_warnings(self) -> None:
        out = _printed(
            _report(
                _warning(ModelWarningKind.MISSING_API_KEY, _KEY_MESSAGE),
                _warning(
                    ModelWarningKind.BELOW_RECOMMENDED_TIER,
                    _TIER_MESSAGE,
                    StageKey.TAILOR,
                ),
            )
        )
        assert out.count("Run 'mkcv models'") == 1

    def test_a_report_without_warnings_prints_nothing(self) -> None:
        assert _printed(_report()) == ""
