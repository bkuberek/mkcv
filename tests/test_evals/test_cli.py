"""Tests for the evals command line (REQ-EV-1, REQ-EV-21, design 9.8)."""

import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from dynaconf import Dynaconf

from evals.cli import main

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ("list-cases", "estimate", "run", "report", "bootstrap-reference")
HAIKU_ANALYZE_MATRIX = """
[run]
stages = ["analyze"]
cases = ["alpha-match"]

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
EXPENSIVE_HAIKU = """
[[default.model_catalog]]
provider = "anthropic"
match = "claude-haiku-5-5"
input_price_per_mtok = 1.0
output_price_per_mtok = 5.0
"""


@pytest.fixture
def matrix_file(tmp_path: Path) -> Path:
    path = tmp_path / "matrix.toml"
    path.write_text(HAIKU_ANALYZE_MATRIX, encoding="utf-8")
    return path


class TestHelp:
    def _help(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "evals", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_help_exits_zero(self) -> None:
        assert self._help("--help").returncode == 0

    @pytest.mark.parametrize("command", COMMANDS)
    def test_help_lists_every_command(self, command: str) -> None:
        assert command in self._help("--help").stdout

    def test_running_without_a_command_is_a_usage_error(self) -> None:
        assert self._help().returncode == 2


class TestListCases:
    def test_prints_each_case_id(
        self, tmp_fixtures: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(["list-cases", "--fixtures", str(tmp_fixtures)])
        out = capsys.readouterr().out
        assert (code, "alpha-match" in out, "alpha-probe" in out) == (0, True, True)

    def test_prints_the_persona_and_job_description_files(
        self, tmp_fixtures: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["list-cases", "--fixtures", str(tmp_fixtures)])
        out = capsys.readouterr().out
        assert "personas/alpha.md" in out
        assert "jds/alpha-match.md" in out

    def test_reports_that_no_reference_exists(
        self, tmp_fixtures: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["list-cases", "--fixtures", str(tmp_fixtures)])
        assert "no" in capsys.readouterr().out.splitlines()[1].split()

    def test_reports_the_stages_that_have_a_reference(
        self, tmp_fixtures: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reference = tmp_fixtures / "reference" / "alpha-match"
        reference.mkdir(parents=True)
        (reference / "stage1_analysis.json").write_text("{}", encoding="utf-8")
        main(["list-cases", "--fixtures", str(tmp_fixtures)])
        assert "partial: analyze" in capsys.readouterr().out

    def test_reports_a_complete_reference(
        self, tmp_fixtures: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reference = tmp_fixtures / "reference" / "alpha-match"
        reference.mkdir(parents=True)
        for name in (
            "stage1_analysis.json",
            "stage2_selection.json",
            "stage3_content.json",
            "stage4_structure.json",
            "resume.yaml",
            "cover_letter_content.json",
        ):
            (reference / name).write_text("{}", encoding="utf-8")
        main(["list-cases", "--fixtures", str(tmp_fixtures)])
        assert "yes" in capsys.readouterr().out.splitlines()[1].split()

    def test_a_case_without_its_cover_letter_is_partial(
        self, tmp_fixtures: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reference = tmp_fixtures / "reference" / "alpha-match"
        reference.mkdir(parents=True)
        for name in (
            "stage1_analysis.json",
            "stage2_selection.json",
            "stage3_content.json",
            "stage4_structure.json",
            "resume.yaml",
        ):
            (reference / name).write_text("{}", encoding="utf-8")
        main(["list-cases", "--fixtures", str(tmp_fixtures)])
        row = capsys.readouterr().out.splitlines()[1]
        assert "partial:" in row
        assert "cover_letter.generate" not in row

    def test_a_review_probe_needs_no_cover_letter(
        self, tmp_fixtures: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reference = tmp_fixtures / "reference" / "alpha-probe"
        reference.mkdir(parents=True)
        for name in (
            "stage1_analysis.json",
            "stage2_selection.json",
            "stage3_content.json",
            "stage4_structure.json",
            "resume.yaml",
        ):
            (reference / name).write_text("{}", encoding="utf-8")
        main(["list-cases", "--fixtures", str(tmp_fixtures)])
        assert capsys.readouterr().out.splitlines()[2].split()[-1] == "yes"

    def test_missing_fixtures_directory_is_a_usage_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main(["list-cases", "--fixtures", str(tmp_path / "nowhere")])
        assert (code, "cases.toml" in capsys.readouterr().err) == (2, True)


class TestEstimate:
    def _estimate(
        self,
        matrix: Path,
        fixtures: Path,
        settings: Dynaconf,
        capsys: pytest.CaptureFixture[str],
    ) -> tuple[int, str, str]:
        code = main(
            ["estimate", "--matrix", str(matrix), "--fixtures", str(fixtures)],
            config=settings,
        )
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    def test_reports_the_evaluated_model_cost(
        self,
        matrix_file: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """One case on analyze is half of REQ-EV-21's two-case $0.0028."""
        code, out, _ = self._estimate(
            matrix_file, tmp_fixtures, make_settings(), capsys
        )
        assert code == 0
        assert "anthropic/claude-haiku-5-5" in out
        assert "$0.0014" in out

    def test_reports_zero_judge_cost_for_analyze(
        self,
        matrix_file: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _, out, _ = self._estimate(matrix_file, tmp_fixtures, make_settings(), capsys)
        judge_line = next(line for line in out.splitlines() if "judge" in line.lower())
        assert "$0.0000" in judge_line

    def test_reports_the_total(
        self,
        matrix_file: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _, out, _ = self._estimate(matrix_file, tmp_fixtures, make_settings(), capsys)
        total_line = next(line for line in out.splitlines() if "Total" in line)
        assert "$0.0014" in total_line

    def test_user_catalog_overrides_change_the_estimate(
        self,
        matrix_file: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        _, out, _ = self._estimate(
            matrix_file, tmp_fixtures, make_settings(EXPENSIVE_HAIKU), capsys
        )
        # (4000 x 1.00 + 2000 x 5.00) / 1e6 = $0.0140 for one analyze run
        assert "$0.0140" in out

    def test_an_unpriced_model_prints_not_available(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        matrix = tmp_path / "unpriced.toml"
        matrix.write_text(
            HAIKU_ANALYZE_MATRIX.replace(
                '[[models]]\nprovider = "anthropic"\nmodel = "claude-haiku-5-5"',
                '[[models]]\nprovider = "stub"\nmodel = "stub-model"',
            ),
            encoding="utf-8",
        )
        _, out, _ = self._estimate(matrix, tmp_fixtures, make_settings(), capsys)
        stub_line = next(line for line in out.splitlines() if "stub/stub-model" in line)
        assert "n/a" in stub_line

    def test_a_partial_total_says_so(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        matrix = tmp_path / "mixed.toml"
        matrix.write_text(
            HAIKU_ANALYZE_MATRIX
            + '\n[[models]]\nprovider = "stub"\nmodel = "stub-model"\n',
            encoding="utf-8",
        )
        _, out, _ = self._estimate(matrix, tmp_fixtures, make_settings(), capsys)
        total_line = next(line for line in out.splitlines() if "Total" in line)
        assert "some prices unknown" in total_line

    def test_only_the_selected_cases_are_counted(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        matrix = tmp_path / "both.toml"
        matrix.write_text(
            HAIKU_ANALYZE_MATRIX.replace('cases = ["alpha-match"]', 'cases = ["*"]'),
            encoding="utf-8",
        )
        _, out, _ = self._estimate(matrix, tmp_fixtures, make_settings(), capsys)
        # alpha-probe only runs the review stage, so analyze still costs one case.
        assert "$0.0014" in out

    def test_a_missing_matrix_is_a_usage_error(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, _, err = self._estimate(
            tmp_path / "nope.toml", tmp_fixtures, make_settings(), capsys
        )
        assert (code, "nope.toml" in err) == (2, True)

    def test_an_unknown_case_in_the_matrix_is_a_usage_error(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        matrix = tmp_path / "unknown.toml"
        matrix.write_text(
            HAIKU_ANALYZE_MATRIX.replace("alpha-match", "ghost"), encoding="utf-8"
        )
        code, _, err = self._estimate(matrix, tmp_fixtures, make_settings(), capsys)
        assert (code, "ghost" in err) == (2, True)

    def test_an_invalid_catalog_override_is_a_usage_error(
        self,
        matrix_file: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        broken = make_settings('[[default.model_catalog]]\nprovider = "anthropic"\n')
        code, _, err = self._estimate(matrix_file, tmp_fixtures, broken, capsys)
        assert (code, "model_catalog" in err) == (2, True)

    def test_the_shipped_matrix_is_estimated_without_unknown_prices(
        self,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code = main(
            ["estimate", "--fixtures", str(tmp_fixtures)], config=make_settings()
        )
        assert (code, "n/a" in capsys.readouterr().out) == (0, False)


class TestEstimatePanel:
    """The estimate prices every judge of the panel, keys or not."""

    PANEL_MATRIX = HAIKU_ANALYZE_MATRIX.replace(
        'stages = ["analyze"]', 'stages = ["tailor"]'
    ).replace(
        '[judge]\nprovider = "anthropic"\nmodel = "claude-opus-5-5"\n',
        '[[judges]]\nprovider = "anthropic"\nmodel = "claude-opus-5-5"\n\n'
        '[[judges]]\nprovider = "openai"\nmodel = "gpt-6-astra"\n',
    )

    def _out(
        self,
        tmp_path: Path,
        fixtures: Path,
        settings: Dynaconf,
        capsys: pytest.CaptureFixture[str],
        *extra: str,
    ) -> str:
        matrix = tmp_path / "panel.toml"
        matrix.write_text(self.PANEL_MATRIX, encoding="utf-8")
        code = main(
            ["estimate", "--matrix", str(matrix), "--fixtures", str(fixtures), *extra],
            config=settings,
        )
        assert code == 0
        return capsys.readouterr().out

    def test_every_judge_has_its_own_line(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = self._out(tmp_path, tmp_fixtures, make_settings(), capsys)
        lines = [line for line in out.splitlines() if line.startswith("Judge ")]
        assert len(lines) == 2
        assert "anthropic/claude-opus-5-5" in lines[0]
        assert "openai/gpt-6-astra" in lines[1]
        assert all("2 calls" in line for line in lines)

    def test_judges_are_priced_without_their_keys(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = self._out(tmp_path, tmp_fixtures, make_settings(), capsys)
        assert "(skipped)" not in out

    def test_the_cost_is_broken_down_by_provider(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = self._out(tmp_path, tmp_fixtures, make_settings(), capsys)
        lines = out.splitlines()
        start = lines.index("By provider (models and judges):")
        providers = [line.split()[0] for line in lines[start + 1 : start + 3]]
        assert providers == ["anthropic", "openai"]

    def test_the_judge_flag_takes_a_panel(
        self,
        tmp_path: Path,
        tmp_fixtures: Path,
        make_settings: Callable[..., Dynaconf],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = self._out(
            tmp_path,
            tmp_fixtures,
            make_settings(),
            capsys,
            "--judge",
            "google:gemini-4-argon",
            "openai:gpt-6-luna",
        )
        judges = [
            line.split()[1] for line in out.splitlines() if line.startswith("Judge ")
        ]
        assert judges == ["google/gemini-4-argon", "openai/gpt-6-luna"]


class TestUsage:
    def test_no_command_exits_two(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main([]) == 2

    def test_an_unknown_command_exits_two(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["frobnicate"]) == 2

    def test_help_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["--help"]) == 0


def test_the_shipped_matrix_file_is_valid_toml() -> None:
    path = REPO_ROOT / "evals" / "config" / "matrix.toml"
    assert tomllib.loads(path.read_text(encoding="utf-8"))["models"]
