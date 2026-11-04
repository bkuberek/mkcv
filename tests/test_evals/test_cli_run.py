"""Tests for the ``run`` and ``bootstrap-reference`` commands (REQ-EV-20)."""

import builtins
import io
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from dynaconf import Dynaconf

from evals.cli import default_out_dir, main
from evals.harness.case_loader import load_cases
from evals.models.eval_record import EvalRecord
from evals.models.run_manifest import RunManifest
from mkcv.adapters.llm.stub import StubLLMAdapter
from mkcv.core.models.experience_selection import ExperienceSelection
from mkcv.core.models.jd_analysis import JDAnalysis
from mkcv.core.models.stage_key import StageKey
from mkcv.core.ports.llm import LLMPort
from tests.test_evals.conftest import recorded
from tests.test_evals.grading_support import judging_stub

STUB_MATRIX = """
[run]
stages = ["analyze", "select"]
cases = ["alpha-match"]
concurrency = 1

[judge]
provider = "anthropic"
model = "claude-opus-5-5"

[reference]
provider = "stub"
model = "stub-model"

[[models]]
provider = "stub"
model = "stub-model"
"""
MIXED_MATRIX = (
    STUB_MATRIX + '\n[[models]]\nprovider = "openai"\nmodel = "gpt-6.1-sol"\n'
)


class Terminal(io.StringIO):
    """A stdin that reports being an interactive terminal."""

    def isatty(self) -> bool:
        return True


@pytest.fixture
def fixtures(tmp_fixtures: Path, add_reference: Callable[..., None]) -> Path:
    add_reference(load_cases(tmp_fixtures)[0])
    return tmp_fixtures


@pytest.fixture
def matrix_file(tmp_path: Path) -> Path:
    path = tmp_path / "matrix.toml"
    path.write_text(STUB_MATRIX, encoding="utf-8")
    return path


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    return tmp_path / "results"


@pytest.fixture
def run(
    fixtures: Path,
    matrix_file: Path,
    out_dir: Path,
    make_settings: Callable[..., Dynaconf],
    canned_stub: StubLLMAdapter,
    install_adapter: Callable[[LLMPort], LLMPort],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[..., int]:
    """Run ``evals run`` against the canned stub with sensible test defaults."""
    install_adapter(canned_stub)
    monkeypatch.setattr("sys.stdin", io.StringIO())

    def _run(*extra: str, matrix: Path | None = None, yes: bool = True) -> int:
        argv = [
            "run",
            "--matrix",
            str(matrix or matrix_file),
            "--fixtures",
            str(fixtures),
            "--out",
            str(out_dir),
            *(["--yes"] if yes else []),
            *extra,
        ]
        return main(argv, config=make_settings())

    return _run


def _records(out_dir: Path) -> list[EvalRecord]:
    lines = (out_dir / "results.jsonl").read_text().splitlines()
    return [EvalRecord.model_validate_json(line) for line in lines]


def _manifest(out_dir: Path) -> RunManifest:
    return RunManifest.model_validate_json((out_dir / "run.json").read_text())


class TestRun:
    def test_a_run_with_yes_exits_zero(self, run: Callable[..., int]) -> None:
        assert run() == 0

    def test_it_writes_the_results_the_manifest_the_summary_and_the_report(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run()
        assert sorted(p.name for p in out_dir.iterdir() if p.is_file()) == [
            "report.md",
            "results.jsonl",
            "run.json",
            "summary.json",
        ]

    def test_it_records_every_planned_stage_run(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run()
        assert [(r.case_id, r.stage, r.status) for r in _records(out_dir)] == [
            ("alpha-match", StageKey.ANALYZE, "ok"),
            ("alpha-match", StageKey.SELECT, "ok"),
        ]

    def test_it_prints_the_estimate_before_running(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        run()
        out = capsys.readouterr().out
        assert out.index("Total") < out.index("Wrote")

    def test_it_prints_one_progress_line_per_record(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        run()
        lines = [
            line
            for line in capsys.readouterr().out.splitlines()
            if "stub/stub-model" in line and "alpha-match" in line
        ]
        assert len(lines) == 2

    def test_it_prints_where_the_results_went(
        self, run: Callable[..., int], out_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run()
        assert str(out_dir) in capsys.readouterr().out

    def test_it_prints_where_the_report_is(
        self, run: Callable[..., int], out_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        run()
        assert f"Report: {out_dir / 'report.md'}" in capsys.readouterr().out

    def test_failed_records_do_not_change_the_exit_code(
        self,
        run: Callable[..., int],
        install_adapter: Callable[[LLMPort], LLMPort],
        out_dir: Path,
    ) -> None:
        install_adapter(StubLLMAdapter())
        assert run() == 0
        assert {r.status for r in _records(out_dir)} == {"error"}

    def test_the_summary_counts_failed_records(
        self,
        run: Callable[..., int],
        install_adapter: Callable[[LLMPort], LLMPort],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        install_adapter(StubLLMAdapter())
        run()
        assert "2 error" in capsys.readouterr().out

    def test_the_manifest_names_the_run(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run()
        manifest = _manifest(out_dir)
        assert manifest.matrix.models[0].label == "stub/stub-model"
        assert manifest.cases == ["alpha-match"]


class TestConfirmation:
    """REQ-EV-20: a run that could spend money needs a yes."""

    def test_without_yes_off_a_terminal_it_exits_two(
        self, run: Callable[..., int]
    ) -> None:
        assert run(yes=False) == 2

    def test_it_still_prints_the_estimate(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        run(yes=False)
        captured = capsys.readouterr()
        assert "Total" in captured.out
        assert "--yes" in captured.err

    def test_no_model_is_called_and_nothing_is_written(
        self,
        run: Callable[..., int],
        canned_stub: StubLLMAdapter,
        out_dir: Path,
    ) -> None:
        run(yes=False)
        assert canned_stub.call_log == []
        assert not out_dir.exists()

    def test_on_a_terminal_y_proceeds(
        self,
        run: Callable[..., int],
        out_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("sys.stdin", Terminal())
        monkeypatch.setattr(builtins, "input", lambda prompt="": "y")
        assert run(yes=False) == 0
        assert len(_records(out_dir)) == 2

    def test_on_a_terminal_the_prompt_asks_to_proceed(
        self,
        run: Callable[..., int],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        prompts: list[str] = []
        monkeypatch.setattr("sys.stdin", Terminal())
        monkeypatch.setattr(
            builtins, "input", lambda prompt="": prompts.append(prompt) or "y"
        )
        run(yes=False)
        assert prompts == ["Proceed? [y/N] "]

    @pytest.mark.parametrize("answer", ["", "n", "no", "maybe"])
    def test_on_a_terminal_anything_but_yes_exits_two(
        self,
        answer: str,
        run: Callable[..., int],
        canned_stub: StubLLMAdapter,
        out_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("sys.stdin", Terminal())
        monkeypatch.setattr(builtins, "input", lambda prompt="": answer)
        assert run(yes=False) == 2
        assert canned_stub.call_log == []
        assert not out_dir.exists()

    def test_end_of_input_at_the_prompt_declines(
        self, run: Callable[..., int], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _eof(prompt: str = "") -> str:
            raise EOFError

        monkeypatch.setattr("sys.stdin", Terminal())
        monkeypatch.setattr(builtins, "input", _eof)
        assert run(yes=False) == 2


class TestCredentials:
    """REQ-EV-20: models without a key are skipped, or refused with --strict."""

    @pytest.fixture
    def mixed(self, tmp_path: Path) -> Path:
        path = tmp_path / "mixed.toml"
        path.write_text(MIXED_MATRIX, encoding="utf-8")
        return path

    def test_a_model_without_a_key_is_skipped_with_a_warning_naming_the_provider(
        self,
        run: Callable[..., int],
        mixed: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert run(matrix=mixed) == 0
        err = capsys.readouterr().err
        assert "warning" in err
        assert "openai" in err

    def test_other_providers_still_run(
        self, run: Callable[..., int], mixed: Path, out_dir: Path
    ) -> None:
        run(matrix=mixed)
        assert {r.provider for r in _records(out_dir)} == {"stub"}

    def test_the_skipped_model_is_listed_in_the_manifest(
        self, run: Callable[..., int], mixed: Path, out_dir: Path
    ) -> None:
        run(matrix=mixed)
        [skipped] = _manifest(out_dir).skipped_models
        assert skipped.startswith("openai/gpt-6.1-sol: ")

    def test_the_estimate_covers_only_the_models_that_will_run(
        self,
        run: Callable[..., int],
        mixed: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run(matrix=mixed)
        assert "gpt-6.1-sol" not in capsys.readouterr().out.split("Wrote")[0]

    def test_a_key_in_the_environment_makes_the_model_run(
        self,
        run: Callable[..., int],
        mixed: Path,
        out_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        run(matrix=mixed)
        assert {r.provider for r in _records(out_dir)} == {"stub", "openai"}

    def test_strict_refuses_before_any_call(
        self,
        run: Callable[..., int],
        mixed: Path,
        canned_stub: StubLLMAdapter,
        out_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert run("--strict", matrix=mixed) == 2
        assert "openai" in capsys.readouterr().err
        assert canned_stub.call_log == []
        assert not out_dir.exists()

    def test_strict_is_fine_when_every_provider_has_credentials(
        self,
        run: Callable[..., int],
        install_adapter: Callable[[LLMPort], LLMPort],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        install_adapter(judging_stub())
        assert run("--strict") == 0

    def test_every_model_skipped_still_writes_empty_results(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        assert run("--models", "openai:gpt-6.1-sol") == 0
        assert (out_dir / "results.jsonl").read_text() == ""
        assert _manifest(out_dir).skipped_models

    def test_the_shipped_matrix_with_no_keys_skips_every_model(
        self, run: Callable[..., int], out_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        shipped = (
            Path(__file__).resolve().parents[2] / "evals" / "config" / "matrix.toml"
        )
        assert run("--stages", "analyze", "--cases", "alpha-match", matrix=shipped) == 0
        manifest = _manifest(out_dir)
        assert manifest.matrix.models == []
        assert len(manifest.skipped_models) == 10
        assert capsys.readouterr().err.count("warning") == 10


class TestOverrides:
    def test_models_replace_the_matrix_models(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run("--models", "stub:other-model")
        assert {r.model for r in _records(out_dir)} == {"other-model"}

    def test_stages_filter_the_run(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run("--stages", "analyze")
        assert {r.stage for r in _records(out_dir)} == {StageKey.ANALYZE}

    def test_cases_filter_the_run(self, run: Callable[..., int], out_dir: Path) -> None:
        run("--cases", "alpha-probe", "--stages", "review")
        assert {r.case_id for r in _records(out_dir)} == {"alpha-probe"}

    def test_an_unknown_case_is_a_usage_error(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run("--cases", "ghost") == 2
        assert "ghost" in capsys.readouterr().err

    def test_an_unknown_stage_is_a_usage_error(self, run: Callable[..., int]) -> None:
        assert run("--stages", "polish") == 2

    def test_concurrency_must_be_positive(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run("--concurrency", "0") == 2
        assert "concurrency" in capsys.readouterr().err

    def test_judge_overrides_the_matrix_judge(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run("--judge", "openai:gpt-6.1-sol")
        [judge] = _manifest(out_dir).panel
        assert (judge.provider, judge.model) == ("openai", "gpt-6.1-sol")

    def test_a_judge_without_a_colon_exits_two_with_a_usage_message(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str], out_dir: Path
    ) -> None:
        assert run("--judge", "gpt-6.1-sol") == 2
        assert "provider:model" in capsys.readouterr().err
        assert not out_dir.exists()


class TestEstimateOverrides:
    def test_estimate_accepts_the_same_selection_flags(
        self,
        fixtures: Path,
        matrix_file: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = main(
            [
                "estimate",
                "--matrix",
                str(matrix_file),
                "--fixtures",
                str(fixtures),
                "--stages",
                "analyze",
                "--models",
                "anthropic:claude-haiku-5-5",
            ],
            config=make_settings(),
        )
        assert code == 0
        assert "$0.0014" in capsys.readouterr().out


class TestDefaultOutputDirectory:
    def test_results_go_under_evals_results_by_run_id(self) -> None:
        path = default_out_dir("20261104-010203-abc1234")
        assert path.parts[-3:] == ("evals", "results", "20261104-010203-abc1234")


class TestBootstrapReference:
    @pytest.fixture
    def bootstrap(
        self,
        tmp_fixtures: Path,
        matrix_file: Path,
        make_settings: Callable[..., Dynaconf],
        canned_stub: StubLLMAdapter,
        install_adapter: Callable[[LLMPort], LLMPort],
        monkeypatch: pytest.MonkeyPatch,
    ) -> Callable[..., int]:
        install_adapter(canned_stub)
        monkeypatch.setattr("sys.stdin", io.StringIO())

        def _bootstrap(*extra: str, yes: bool = True) -> int:
            argv = [
                "bootstrap-reference",
                "--matrix",
                str(matrix_file),
                "--fixtures",
                str(tmp_fixtures),
                "--state",
                str(tmp_fixtures.parent / "bootstrap-state"),
                *(["--yes"] if yes else []),
                *extra,
            ]
            return main(argv, config=make_settings())

        return _bootstrap

    def test_it_writes_the_reference_files(
        self, bootstrap: Callable[..., int], tmp_fixtures: Path
    ) -> None:
        assert bootstrap() == 0
        case = load_cases(tmp_fixtures)[0]
        assert len(case.reference_stages()) == 5

    def test_it_reminds_the_user_to_review_before_committing(
        self, bootstrap: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        bootstrap()
        assert "review" in capsys.readouterr().out.lower()

    def test_it_reports_each_case(
        self, bootstrap: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        bootstrap()
        assert "alpha-match: written" in capsys.readouterr().out

    def test_without_yes_off_a_terminal_it_exits_two_and_writes_nothing(
        self,
        bootstrap: Callable[..., int],
        tmp_fixtures: Path,
        canned_stub: StubLLMAdapter,
    ) -> None:
        assert bootstrap(yes=False) == 2
        assert canned_stub.call_log == []
        assert not (tmp_fixtures / "reference").exists()

    def test_it_prints_the_reference_model_estimate_first(
        self,
        bootstrap: Callable[..., int],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bootstrap(yes=False)
        assert "Reference model stub/stub-model" in capsys.readouterr().out

    def test_provider_and_model_override_the_matrix_reference(
        self,
        bootstrap: Callable[..., int],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bootstrap("--provider", "stub", "--model", "other-model", yes=False)
        assert "Reference model stub/other-model" in capsys.readouterr().out

    def test_provider_without_model_is_a_usage_error(
        self, bootstrap: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert bootstrap("--provider", "stub") == 2
        assert "--provider and --model" in capsys.readouterr().err

    def test_a_reference_provider_without_credentials_is_refused(
        self,
        bootstrap: Callable[..., int],
        canned_stub: StubLLMAdapter,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert bootstrap("--provider", "openai", "--model", "gpt-6.1-sol") == 2
        assert "openai" in capsys.readouterr().err
        assert canned_stub.call_log == []

    def test_an_existing_reference_is_skipped_not_overwritten(
        self,
        bootstrap: Callable[..., int],
        tmp_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        reference = tmp_fixtures / "reference" / "alpha-match"
        reference.mkdir(parents=True)
        (reference / "stage1_analysis.json").write_text("reviewed")
        assert bootstrap() == 0
        assert (reference / "stage1_analysis.json").read_text() == "reviewed"
        assert "alpha-match: skipped" in capsys.readouterr().out

    def test_a_failed_case_makes_the_exit_code_one(
        self,
        bootstrap: Callable[..., int],
        install_adapter: Callable[[LLMPort], LLMPort],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        install_adapter(StubLLMAdapter())
        assert bootstrap() == 1
        assert "alpha-match: error" in capsys.readouterr().out

    def test_cases_limit_what_is_bootstrapped(
        self, bootstrap: Callable[..., int], tmp_fixtures: Path
    ) -> None:
        bootstrap("--cases", "alpha-match")
        assert not (tmp_fixtures / "reference" / "alpha-probe").exists()

    def test_the_default_cases_are_the_matrix_cases(
        self, bootstrap: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        bootstrap()
        assert "alpha-probe" not in capsys.readouterr().out


def test_the_run_id_default_uses_the_current_time(
    run: Callable[..., int], out_dir: Path
) -> None:
    before = datetime.now(UTC).strftime("%Y%m%d")
    run()
    assert _manifest(out_dir).run_id.startswith(before)


def test_run_json_is_valid_json(run: Callable[..., int], out_dir: Path) -> None:
    run()
    assert json.loads((out_dir / "run.json").read_text())["run_id"]


class TestJudge:
    """The judge needs a key like any other provider; a run without one goes on."""

    def test_a_judge_without_a_key_is_warned_about(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert run() == 0
        err = capsys.readouterr().err
        assert "warning: judge anthropic/claude-opus-5-5" in err
        assert "no API key for provider 'anthropic'" in err

    def test_the_estimate_does_not_price_a_judge_that_will_not_run(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        run()
        out = capsys.readouterr().out
        assert "(skipped)" in out
        assert "0 calls" in out

    def test_the_manifest_records_why_the_judge_was_skipped(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run()
        reason = _manifest(out_dir).skipped_judges["anthropic/claude-opus-5-5"]
        assert "ANTHROPIC_API_KEY" in reason

    def test_the_records_have_no_judge_grades(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run()
        assert all(r.judge is None for r in _records(out_dir))

    def test_with_the_key_the_judge_is_priced_and_not_warned_about(
        self,
        run: Callable[..., int],
        install_adapter: Callable[[LLMPort], LLMPort],
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        install_adapter(judging_stub())
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        run()
        captured = capsys.readouterr()
        assert "1 calls" in captured.out
        assert "(skipped)" not in captured.out
        assert "judge" not in captured.err

    def test_a_run_without_judged_stages_does_not_mention_the_judge(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        run("--stages", "analyze")
        captured = capsys.readouterr()
        assert "judge" not in captured.err
        assert "(skipped)" not in captured.out

    def test_the_judge_flag_names_the_judge_that_grades(
        self,
        run: Callable[..., int],
        install_adapter: Callable[[LLMPort], LLMPort],
        out_dir: Path,
    ) -> None:
        install_adapter(judging_stub())
        assert run("--judge", "stub:stub-model") == 0
        select = next(r for r in _records(out_dir) if r.stage is StageKey.SELECT)
        assert select.judge == "stub/stub-model"
        assert "selection_judge" in [g.name for g in select.grades]
        assert _manifest(out_dir).skipped_judges == {}

    def test_strict_refuses_a_judge_without_a_key_before_any_call(
        self,
        run: Callable[..., int],
        canned_stub: StubLLMAdapter,
        out_dir: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert run("--strict") == 2
        assert "judge" in capsys.readouterr().err
        assert canned_stub.call_log == []
        assert not out_dir.exists()

    def test_strict_does_not_ask_for_a_judge_key_when_no_stage_needs_one(
        self, run: Callable[..., int]
    ) -> None:
        assert run("--strict", "--stages", "analyze") == 0

    def test_a_judge_flag_without_a_colon_exits_two(
        self, run: Callable[..., int], canned_stub: StubLLMAdapter
    ) -> None:
        assert run("--judge", "gpt-6.1-sol") == 2
        assert canned_stub.call_log == []

    def test_an_unknown_judge_provider_exits_two_before_any_call(
        self,
        run: Callable[..., int],
        canned_stub: StubLLMAdapter,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert run("--judge", "nope:model") == 2
        assert "Unknown LLM provider 'nope'" in capsys.readouterr().err
        assert canned_stub.call_log == []


class TestLogging:
    """mkcv's own warnings are shown on stderr once, in one format."""

    @pytest.fixture(autouse=True)
    def _restore_loggers(self) -> object:
        saved = {
            name: (
                logging.getLogger(name).level,
                list(logging.getLogger(name).handlers),
            )
            for name in ("mkcv", "evals")
        }
        yield
        for name, (level, handlers) in saved.items():
            logging.getLogger(name).setLevel(level)
            logging.getLogger(name).handlers[:] = handlers

    @pytest.fixture
    def noisy(self, install_adapter: Callable[[LLMPort], LLMPort]) -> None:
        class Noisy(StubLLMAdapter):
            async def complete_structured(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def, override]
                logging.getLogger("mkcv.adapters.llm.retry").warning("slow down")
                return await super().complete_structured(*args, **kwargs)  # type: ignore[arg-type]

        install_adapter(
            Noisy(
                responses={
                    JDAnalysis: recorded(JDAnalysis),
                    ExperienceSelection: recorded(ExperienceSelection),
                }
            )
        )

    def test_a_warning_from_mkcv_is_printed_once_per_event(
        self,
        run: Callable[..., int],
        noisy: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run()
        err = capsys.readouterr().err
        assert err.count("WARNING mkcv.adapters.llm.retry: slow down") == 2

    def test_progress_messages_are_hidden_unless_verbose(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        run()
        assert "Running alpha-match" not in capsys.readouterr().err

    def test_verbose_shows_each_stage_run_starting(
        self, run: Callable[..., int], capsys: pytest.CaptureFixture[str]
    ) -> None:
        run("--verbose")
        assert "Running alpha-match" in capsys.readouterr().err

    @pytest.mark.parametrize("command", ["run", "bootstrap-reference"])
    def test_both_long_commands_take_verbose(
        self, command: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main([command, "--help"]) == 0
        assert "--verbose" in capsys.readouterr().out


def test_runs_are_published_where_git_keeps_them() -> None:
    from evals.cli import PUBLISHED_DIR

    expected = Path(__file__).resolve().parents[2] / "evals" / "results" / "published"
    assert expected == PUBLISHED_DIR


class TestReport:
    """``report DIR`` rebuilds the summary and report; ``--publish`` shares a run."""

    @pytest.fixture
    def finished_run(self, run: Callable[..., int], out_dir: Path) -> Path:
        run()
        (out_dir / "summary.json").unlink()
        (out_dir / "report.md").unlink()
        return out_dir

    def test_it_rebuilds_the_summary_and_the_report(
        self, finished_run: Path, make_settings: Callable[..., Dynaconf]
    ) -> None:
        assert main(["report", str(finished_run)], config=make_settings()) == 0
        assert (finished_run / "summary.json").is_file()
        assert (finished_run / "report.md").is_file()

    def test_it_says_what_it_wrote(
        self,
        finished_run: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        main(["report", str(finished_run)], config=make_settings())
        assert str(finished_run / "report.md") in capsys.readouterr().out

    def test_without_publish_nothing_is_copied(
        self,
        finished_run: Path,
        make_settings: Callable[..., Dynaconf],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        published = tmp_path / "published"
        monkeypatch.setattr("evals.cli.PUBLISHED_DIR", published)
        main(["report", str(finished_run)], config=make_settings())
        assert not published.exists()

    def test_publish_copies_the_four_files_without_the_raw_outputs(
        self,
        finished_run: Path,
        make_settings: Callable[..., Dynaconf],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        published = tmp_path / "published"
        monkeypatch.setattr("evals.cli.PUBLISHED_DIR", published)
        code = main(["report", str(finished_run), "--publish"], config=make_settings())
        [destination] = published.iterdir()
        assert code == 0
        assert destination.name == _manifest(finished_run).run_id
        assert sorted(p.name for p in destination.iterdir()) == [
            "report.md",
            "results.jsonl",
            "run.json",
            "summary.json",
        ]

    def test_publish_says_where_the_run_went(
        self,
        finished_run: Path,
        make_settings: Callable[..., Dynaconf],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr("evals.cli.PUBLISHED_DIR", tmp_path / "published")
        main(["report", str(finished_run), "--publish"], config=make_settings())
        assert str(tmp_path / "published" / _manifest(finished_run).run_id) in (
            capsys.readouterr().out
        )

    def test_a_directory_without_results_exits_two(
        self,
        tmp_path: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert main(["report", str(tmp_path)], config=make_settings()) == 2
        assert "results.jsonl" in capsys.readouterr().err

    def test_the_directory_is_required(
        self, make_settings: Callable[..., Dynaconf]
    ) -> None:
        assert main(["report"], config=make_settings()) == 2


class TestOfflineRunWithoutKeys:
    """T17 acceptance: with every key absent the run skips models and still reports."""

    def test_it_exits_zero_skips_every_model_and_writes_the_four_files(
        self,
        fixtures: Path,
        out_dir: Path,
        tmp_path: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        matrix = tmp_path / "keyed.toml"
        matrix.write_text(
            STUB_MATRIX.replace(
                '[[models]]\nprovider = "stub"\nmodel = "stub-model"',
                '[[models]]\nprovider = "openai"\nmodel = "gpt-6.1-sol"\n\n'
                '[[models]]\nprovider = "google"\nmodel = "gemini-4-argon"',
            ),
            encoding="utf-8",
        )
        argv = [
            "run",
            "--matrix",
            str(matrix),
            "--fixtures",
            str(fixtures),
            "--out",
            str(out_dir),
            "--yes",
        ]
        assert main(argv, config=make_settings()) == 0
        assert sorted(p.name for p in out_dir.iterdir() if p.is_file()) == [
            "report.md",
            "results.jsonl",
            "run.json",
            "summary.json",
        ]
        captured = capsys.readouterr()
        assert "skipping openai/gpt-6.1-sol" in captured.err
        assert "skipping google/gemini-4-argon" in captured.err
        assert "Total: $0.0000" in captured.out
        assert "No results" in (out_dir / "report.md").read_text()


TOURNAMENT = """
[tournament]
screening_cases = ["alpha-match"]
"""


class TestRounds:
    @pytest.fixture
    def tournament_matrix(self, tmp_path: Path) -> Path:
        path = tmp_path / "tournament.toml"
        path.write_text(TOURNAMENT + STUB_MATRIX, encoding="utf-8")
        return path

    def test_run_executes_both_rounds(
        self, run: Callable[..., int], tournament_matrix: Path, out_dir: Path
    ) -> None:
        assert run(matrix=tournament_matrix) == 0
        assert {r.round for r in _records(out_dir)} == {"screening", "finals"}

    def test_the_round_flag_runs_only_the_screening(
        self, run: Callable[..., int], tournament_matrix: Path, out_dir: Path
    ) -> None:
        assert run("--round", "screening", matrix=tournament_matrix) == 0
        assert {r.round for r in _records(out_dir)} == {"screening"}

    def test_resume_runs_the_finals_of_a_screened_run(
        self, run: Callable[..., int], tournament_matrix: Path, out_dir: Path
    ) -> None:
        run("--round", "screening", matrix=tournament_matrix)
        run_id = _manifest(out_dir).run_id
        assert (
            run("--round", "finals", "--resume", str(out_dir), matrix=tournament_matrix)
            == 0
        )
        assert {r.round for r in _records(out_dir)} == {"screening", "finals"}
        assert _manifest(out_dir).run_id == run_id

    def test_finals_without_a_screened_run_exit_two(
        self, run: Callable[..., int], tournament_matrix: Path
    ) -> None:
        assert run("--round", "finals", matrix=tournament_matrix) == 2

    def test_single_round_turns_the_tournament_off(
        self, run: Callable[..., int], tournament_matrix: Path, out_dir: Path
    ) -> None:
        assert run("--single-round", matrix=tournament_matrix) == 0
        assert {r.round for r in _records(out_dir)} == {None}

    def test_the_estimate_shows_both_rounds(
        self,
        run: Callable[..., int],
        tournament_matrix: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        run("--round", "screening", matrix=tournament_matrix)
        out = capsys.readouterr().out
        assert "Screening:" in out
        assert "Finals:" in out
        assert "Total (screening + finals)" in out
