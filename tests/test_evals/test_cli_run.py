"""Tests for the ``run`` and ``bootstrap-reference`` commands (REQ-EV-20)."""

import builtins
import io
import json
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
from mkcv.core.models.stage_key import StageKey
from mkcv.core.ports.llm import LLMPort

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

    def test_it_writes_results_and_the_manifest(
        self, run: Callable[..., int], out_dir: Path
    ) -> None:
        run()
        assert sorted(p.name for p in out_dir.iterdir() if p.is_file()) == [
            "results.jsonl",
            "run.json",
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
        self, run: Callable[..., int]
    ) -> None:
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
        judge = _manifest(out_dir).judge
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
        assert len(case.reference_stages()) == 4

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


def test_unfinished_report_command_is_still_registered(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["report"]) == 2
    assert "not implemented yet" in capsys.readouterr().err


def test_the_run_id_default_uses_the_current_time(
    run: Callable[..., int], out_dir: Path
) -> None:
    before = datetime.now(UTC).strftime("%Y%m%d")
    run()
    assert _manifest(out_dir).run_id.startswith(before)


def test_run_json_is_valid_json(run: Callable[..., int], out_dir: Path) -> None:
    run()
    assert json.loads((out_dir / "run.json").read_text())["run_id"]
