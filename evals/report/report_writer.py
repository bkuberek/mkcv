"""Read a run directory and write its summary and report; publish a run."""

import json
import shutil
from pathlib import Path

from pydantic import ValidationError

from evals.harness.run_files import (
    MANIFEST_FILE,
    PUBLISHED_FILES,
    REPORT_FILE,
    RESULTS_FILE,
    SUMMARY_FILE,
)
from evals.models.eval_record import EvalRecord
from evals.models.run_manifest import RunManifest
from evals.report.aggregator import aggregate
from evals.report.markdown_report import render_markdown
from evals.report.recommender import recommend


def read_records(out_dir: Path) -> list[EvalRecord]:
    """Return the records in ``out_dir/results.jsonl``, in file order.

    Raises:
        FileNotFoundError: If the file is missing.
        ValueError: If a line is not a valid record.
    """
    path = out_dir / RESULTS_FILE
    if not path.is_file():
        raise FileNotFoundError(
            f"No {RESULTS_FILE} in {out_dir}; is it an eval run directory?"
        )
    records: list[EvalRecord] = []
    with path.open(encoding="utf-8") as lines:
        for number, line in enumerate(lines, start=1):
            if line.strip():
                records.append(_parse_record(line, number))
    return records


def read_manifest(out_dir: Path) -> RunManifest:
    """Return the manifest in ``out_dir/run.json``.

    Raises:
        FileNotFoundError: If the file is missing.
        ValueError: If it is not a valid manifest.
    """
    path = out_dir / MANIFEST_FILE
    if not path.is_file():
        raise FileNotFoundError(
            f"No {MANIFEST_FILE} in {out_dir}; is it an eval run directory?"
        )
    try:
        return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise ValueError(
            f"{MANIFEST_FILE} is not a valid run manifest: {error}"
        ) from error


def write_report_files(out_dir: Path) -> None:
    """Write ``summary.json`` and ``report.md`` from a run's records and manifest.

    Raises:
        FileNotFoundError: If ``results.jsonl`` or ``run.json`` is missing.
        ValueError: If either is invalid.
    """
    records = read_records(out_dir)
    manifest = read_manifest(out_dir)
    summaries = aggregate(records)
    recommendations = recommend(summaries)
    (out_dir / SUMMARY_FILE).write_text(
        json.dumps([s.model_dump(mode="json") for s in summaries], indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / REPORT_FILE).write_text(
        render_markdown(manifest, summaries, recommendations), encoding="utf-8"
    )


def publish_run(out_dir: Path, published_root: Path) -> Path:
    """Copy a finished run's four result files to ``published_root/<run_id>``.

    The ``raw/`` outputs stay behind. Publishing a run again overwrites its
    folder's files.

    Returns:
        The folder the files went to.

    Raises:
        FileNotFoundError: If a result file is missing (run ``report`` first).
        ValueError: If the run ID is not a plain folder name.
    """
    missing = next((n for n in PUBLISHED_FILES if not (out_dir / n).is_file()), None)
    if missing is not None:
        raise FileNotFoundError(
            f"No {missing} in {out_dir}; run the report command first"
        )
    run_id = read_manifest(out_dir).run_id
    if Path(run_id).name != run_id or run_id in ("", ".", ".."):
        raise ValueError(f"Cannot publish a run with the ID '{run_id}'")
    destination = published_root / run_id
    destination.mkdir(parents=True, exist_ok=True)
    for name in PUBLISHED_FILES:
        shutil.copyfile(out_dir / name, destination / name)
    return destination


def _parse_record(line: str, number: int) -> EvalRecord:
    try:
        return EvalRecord.model_validate_json(line)
    except ValidationError as error:
        raise ValueError(
            f"{RESULTS_FILE} line {number} is not a valid record: {error}"
        ) from error
