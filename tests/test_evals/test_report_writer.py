"""Tests for writing summary.json and report.md and publishing a run (REQ-EV-19)."""

import json
from pathlib import Path

import pytest

from evals.models.stage_summary import StageSummary
from evals.report.report_writer import publish_run, read_records, write_report_files
from mkcv.core.models.stage_key import StageKey
from tests.test_evals.report_support import RUN_ID, grade, manifest, record

PUBLISHED_NAMES = ["report.md", "results.jsonl", "run.json", "summary.json"]


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """A finished run directory: results.jsonl, run.json, and a raw/ tree."""
    directory = tmp_path / "run"
    (directory / "raw" / "case" / "tailor").mkdir(parents=True)
    (directory / "raw" / "case" / "tailor" / "stage3_content.json").write_text("{}")
    records = [
        record(
            stage=StageKey.TAILOR,
            repeat=i,
            grades=[
                grade("schema", 1.0),
                grade("faithfulness_extraction", 1.0),
                grade("faithfulness_judge", 0.95),
                grade("tailoring_judge", 0.8),
            ],
        )
        for i in range(6)
    ]
    (directory / "results.jsonl").write_text(
        "".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8"
    )
    (directory / "run.json").write_text(manifest().model_dump_json(indent=2) + "\n")
    return directory


class TestWriteReportFiles:
    def test_it_writes_the_summary_and_the_report(self, run_dir: Path) -> None:
        write_report_files(run_dir)
        assert (run_dir / "summary.json").is_file()
        assert (run_dir / "report.md").is_file()

    def test_the_summary_is_a_list_of_stage_summaries(self, run_dir: Path) -> None:
        write_report_files(run_dir)
        loaded = json.loads((run_dir / "summary.json").read_text())
        [summary] = [StageSummary.model_validate(item) for item in loaded]
        assert (summary.stage, summary.n, summary.eligible) == (
            StageKey.TAILOR,
            6,
            True,
        )

    def test_the_report_names_the_run(self, run_dir: Path) -> None:
        write_report_files(run_dir)
        text = (run_dir / "report.md").read_text()
        assert text.startswith(f"# mkcv eval report: {RUN_ID}")

    def test_the_report_recommends_the_only_eligible_model(self, run_dir: Path) -> None:
        write_report_files(run_dir)
        assert (
            "| tailor | openai/gpt-6.1-sol | 0.80 | gpt-6.1-sol (0.80) |"
            in (run_dir / "report.md").read_text()
        )

    def test_running_it_again_gives_the_same_files(self, run_dir: Path) -> None:
        write_report_files(run_dir)
        first = (run_dir / "report.md").read_text()
        write_report_files(run_dir)
        assert (run_dir / "report.md").read_text() == first

    def test_a_directory_without_results_is_a_file_not_found_error(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(FileNotFoundError, match=r"results\.jsonl"):
            write_report_files(tmp_path)

    def test_a_directory_without_a_manifest_is_a_file_not_found_error(
        self, run_dir: Path
    ) -> None:
        (run_dir / "run.json").unlink()
        with pytest.raises(FileNotFoundError, match=r"run\.json"):
            write_report_files(run_dir)

    def test_an_empty_results_file_gives_an_empty_report(self, run_dir: Path) -> None:
        (run_dir / "results.jsonl").write_text("")
        write_report_files(run_dir)
        assert json.loads((run_dir / "summary.json").read_text()) == []
        assert "No results" in (run_dir / "report.md").read_text()


class TestReadRecords:
    def test_a_bad_line_is_reported_with_its_number(self, run_dir: Path) -> None:
        with (run_dir / "results.jsonl").open("a") as sink:
            sink.write("{not json\n")
        with pytest.raises(ValueError, match=r"results.jsonl line 7"):
            read_records(run_dir)

    def test_blank_lines_are_ignored(self, run_dir: Path) -> None:
        with (run_dir / "results.jsonl").open("a") as sink:
            sink.write("\n\n")
        assert len(read_records(run_dir)) == 6


class TestPublishRun:
    def test_it_copies_the_four_files_into_a_folder_named_for_the_run(
        self, run_dir: Path, tmp_path: Path
    ) -> None:
        write_report_files(run_dir)
        destination = publish_run(run_dir, tmp_path / "published")
        assert destination == tmp_path / "published" / RUN_ID
        assert sorted(p.name for p in destination.iterdir()) == PUBLISHED_NAMES

    def test_the_raw_outputs_are_not_published(
        self, run_dir: Path, tmp_path: Path
    ) -> None:
        write_report_files(run_dir)
        destination = publish_run(run_dir, tmp_path / "published")
        assert not (destination / "raw").exists()

    def test_the_copies_match_the_originals(
        self, run_dir: Path, tmp_path: Path
    ) -> None:
        write_report_files(run_dir)
        destination = publish_run(run_dir, tmp_path / "published")
        for name in PUBLISHED_NAMES:
            assert (destination / name).read_bytes() == (run_dir / name).read_bytes()

    def test_publishing_twice_overwrites_quietly(
        self, run_dir: Path, tmp_path: Path
    ) -> None:
        write_report_files(run_dir)
        publish_run(run_dir, tmp_path / "published")
        destination = publish_run(run_dir, tmp_path / "published")
        assert sorted(p.name for p in destination.iterdir()) == PUBLISHED_NAMES

    @pytest.mark.parametrize("run_id", ["../evil", "a/b", "..", "."])
    def test_a_run_id_that_is_not_a_plain_folder_name_is_refused(
        self, run_id: str, run_dir: Path, tmp_path: Path
    ) -> None:
        write_report_files(run_dir)
        text = (run_dir / "run.json").read_text().replace(RUN_ID, run_id)
        (run_dir / "run.json").write_text(text)
        with pytest.raises(ValueError, match="Cannot publish"):
            publish_run(run_dir, tmp_path / "published")
        assert not (tmp_path / "published").exists()

    def test_a_refused_publish_leaves_no_half_published_folder(
        self, run_dir: Path, tmp_path: Path
    ) -> None:
        with pytest.raises(FileNotFoundError):
            publish_run(run_dir, tmp_path / "published")
        assert not (tmp_path / "published").exists()

    def test_a_run_without_a_summary_cannot_be_published(
        self, run_dir: Path, tmp_path: Path
    ) -> None:
        with pytest.raises(FileNotFoundError, match=r"summary\.json"):
            publish_run(run_dir, tmp_path / "published")
