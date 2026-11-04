"""Error text printed through Rich must keep its bracketed config paths.

Rich reads ``[name]`` as a style tag and drops it, so an error such as
``set model in [default.pipeline.stages.select]`` reached the user as
``set model in``. Every place that prints exception text escapes it.
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import mkcv.cli
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.exceptions.kb_generation import KBGenerationError

BRACKETED_PATH = "[default.pipeline.stages.select]"
BRACKETED_MESSAGE = (
    f"No model for stage 'select': set model in {BRACKETED_PATH} "
    "or choose a --model-profile."
)

_CLI_ROOT = Path(mkcv.cli.__file__).resolve().parent


def _printed(capsys: pytest.CaptureFixture[str]) -> str:
    captured = capsys.readouterr()
    return captured.out + captured.err


class TestPrintedErrorsKeepBracketedPaths:
    def test_meta_handler(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from mkcv.cli import app as app_module

        monkeypatch.chdir(tmp_path)
        with (
            patch.object(
                app_module, "app", side_effect=ConfigurationError(BRACKETED_MESSAGE)
            ),
            patch.object(app_module.logging, "basicConfig"),
            pytest.raises(SystemExit) as exit_info,
        ):
            app_module.meta_handler()

        assert exit_info.value.code == 3
        assert BRACKETED_PATH in _printed(capsys)

    def test_generate_jd_reading(self, capsys: pytest.CaptureFixture[str]) -> None:
        from mkcv.cli.commands.generate import _resolve_jd

        with (
            patch(
                "mkcv.cli.commands.generate.read_jd",
                side_effect=ConfigurationError(BRACKETED_MESSAGE),
            ),
            pytest.raises(SystemExit),
        ):
            _resolve_jd("jd.txt")

        assert BRACKETED_PATH in _printed(capsys)

    def test_generate_standard_pipeline(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mkcv.cli.commands.generate import _run_standard_pipeline

        with (
            patch("mkcv.cli.commands.generate.settings"),
            patch("mkcv.cli.commands.generate.create_pipeline_service"),
            patch(
                "mkcv.cli.commands.generate.asyncio.run",
                side_effect=ConfigurationError(BRACKETED_MESSAGE),
            ),
            pytest.raises(SystemExit),
        ):
            _run_standard_pipeline(
                jd=tmp_path / "jd.txt",
                kb=tmp_path / "kb.md",
                output_dir=tmp_path,
                preset_name="standard",
                theme="sb2nov",
            )

        assert BRACKETED_PATH in _printed(capsys)

    def test_generate_cover_letter_setup(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mkcv.cli.commands.generate import _chain_cover_letter

        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")
        result = MagicMock()
        result.output_paths = {"resume_yaml": str(resume)}
        with (
            patch("mkcv.cli.commands.generate.settings"),
            patch(
                "mkcv.cli.commands.generate.create_cover_letter_service",
                side_effect=ConfigurationError(BRACKETED_MESSAGE),
            ),
        ):
            _chain_cover_letter(
                result=result,
                jd_text="JD",
                output_dir=tmp_path,
                provider_override=None,
                cl_preset="standard",
            )

        assert BRACKETED_PATH in _printed(capsys)

    def test_generate_cover_letter_generation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mkcv.cli.commands.generate import _chain_cover_letter

        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")
        result = MagicMock()
        result.output_paths = {"resume_yaml": str(resume)}
        with (
            patch("mkcv.cli.commands.generate.settings"),
            patch("mkcv.cli.commands.generate.create_cover_letter_service"),
            patch(
                "mkcv.cli.commands.generate.asyncio.run",
                side_effect=ConfigurationError(BRACKETED_MESSAGE),
            ),
        ):
            _chain_cover_letter(
                result=result,
                jd_text="JD",
                output_dir=tmp_path,
                provider_override=None,
                cl_preset="standard",
            )

        assert BRACKETED_PATH in _printed(capsys)

    def test_cover_letter_service_creation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mkcv.cli.commands.cover_letter import cover_letter_command

        jd = tmp_path / "jd.txt"
        jd.write_text("Job description", encoding="utf-8")
        kb = tmp_path / "kb.md"
        kb.write_text("# KB", encoding="utf-8")
        with (
            patch("mkcv.cli.commands.cover_letter.settings") as mock_settings,
            patch(
                "mkcv.cli.commands.cover_letter.create_cover_letter_service",
                side_effect=ConfigurationError(BRACKETED_MESSAGE),
            ),
            pytest.raises(SystemExit) as exit_info,
        ):
            mock_settings.in_workspace = False
            cover_letter_command(jd=str(jd), kb=kb, output_dir=tmp_path / "out")

        assert exit_info.value.code == 3
        assert BRACKETED_PATH in _printed(capsys)

    def test_kb_service_creation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mkcv.cli.commands.kb import kb_generate_command

        source = tmp_path / "resume.txt"
        source.write_text("content", encoding="utf-8")
        with (
            patch("mkcv.cli.commands.kb.settings") as mock_settings,
            patch(
                "mkcv.cli.commands.kb.create_kb_generation_service",
                side_effect=ConfigurationError(BRACKETED_MESSAGE),
            ),
            pytest.raises(SystemExit),
        ):
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            kb_generate_command(sources=[source], output=tmp_path / "kb.md")

        assert BRACKETED_PATH in _printed(capsys)

    def test_kb_generation(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from mkcv.cli.commands.kb import kb_generate_command

        source = tmp_path / "resume.txt"
        source.write_text("content", encoding="utf-8")
        with (
            patch("mkcv.cli.commands.kb.settings") as mock_settings,
            patch("mkcv.cli.commands.kb.create_kb_generation_service"),
            patch(
                "mkcv.cli.commands.kb.asyncio.run",
                side_effect=KBGenerationError(f"failed near {BRACKETED_PATH}"),
            ),
            pytest.raises(SystemExit),
        ):
            mock_settings.in_workspace = False
            mock_settings.workspace_root = None
            kb_generate_command(sources=[source], output=tmp_path / "kb.md")

        assert BRACKETED_PATH in _printed(capsys)

    def test_validate(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from mkcv.cli.commands.validate import validate_command

        resume = tmp_path / "resume.yaml"
        resume.write_text("cv:\n  name: Test\n", encoding="utf-8")
        with (
            patch("mkcv.cli.commands.validate.create_validation_service"),
            patch(
                "mkcv.cli.commands.validate.asyncio.run",
                side_effect=ConfigurationError(BRACKETED_MESSAGE),
            ),
            pytest.raises(SystemExit),
        ):
            validate_command(resume)

        assert BRACKETED_PATH in _printed(capsys)


def _unescaped_exception_prints(source_path: Path) -> list[int]:
    """Return line numbers of ``print(f"...{exc}...")`` calls that do not escape."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    offending: list[int] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "print"
        ):
            continue
        for argument in node.args:
            if not isinstance(argument, ast.JoinedStr):
                continue
            for part in argument.values:
                if (
                    isinstance(part, ast.FormattedValue)
                    and isinstance(part.value, ast.Name)
                    and part.value.id in {"exc", "e"}
                ):
                    offending.append(node.lineno)
    return offending


class TestNoUnescapedExceptionText:
    @pytest.mark.parametrize(
        "source_path",
        sorted(_CLI_ROOT.rglob("*.py")),
        ids=lambda path: str(path.relative_to(_CLI_ROOT)),
    )
    def test_cli_module_escapes_exception_text(self, source_path: Path) -> None:
        assert _unescaped_exception_prints(source_path) == []
