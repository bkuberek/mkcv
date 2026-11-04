"""Keep submitted batches and their results on disk, so a run can resume."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from evals.batch.batch_outcome import BatchOutcome
from evals.batch.submitted_batch import SubmittedBatch

SUBMITTED_FILE = "submitted.jsonl"
RESULTS_FILE = "results.jsonl"


class BatchStore:
    """``submitted.jsonl`` and ``results.jsonl`` under one directory.

    A request is never sent twice: once its batch is submitted the store
    knows which batch to wait for, and once results arrive it holds them.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._results: dict[str, BatchOutcome] = {}
        self._batches: dict[str, SubmittedBatch] = {}
        self._batch_of: dict[str, str] = {}
        self._load()

    @property
    def directory(self) -> Path:
        """Where the batch files live."""
        return self._directory

    def result(self, custom_id: str) -> BatchOutcome | None:
        """The stored outcome of a request, if its batch has finished."""
        return self._results.get(custom_id)

    def batch_of(self, custom_id: str) -> SubmittedBatch | None:
        """The submitted batch that holds a request, if any."""
        batch_id = self._batch_of.get(custom_id)
        return self._batches.get(batch_id) if batch_id is not None else None

    def unfinished(self) -> list[SubmittedBatch]:
        """Submitted batches with a request that has no stored outcome yet."""
        return [
            batch
            for batch in self._batches.values()
            if any(cid not in self._results for cid in batch.custom_ids)
        ]

    def record_submitted(self, batch: SubmittedBatch) -> None:
        """Remember ``batch`` before waiting for it."""
        self._remember(batch)
        self._append(
            SUBMITTED_FILE,
            {
                "provider": batch.provider,
                "model": batch.model,
                "batch_id": batch.batch_id,
                "custom_ids": list(batch.custom_ids),
                "extra": batch.extra,
            },
        )

    def record_results(self, outcomes: Sequence[BatchOutcome]) -> None:
        """Remember the outcomes of a finished batch."""
        for outcome in outcomes:
            self._results[outcome.custom_id] = outcome
            self._append(
                RESULTS_FILE,
                {
                    "custom_id": outcome.custom_id,
                    "response": outcome.response,
                    "error": outcome.error,
                },
            )

    def _remember(self, batch: SubmittedBatch) -> None:
        self._batches[batch.batch_id] = batch
        for custom_id in batch.custom_ids:
            self._batch_of[custom_id] = batch.batch_id

    def _append(self, name: str, entry: dict[str, Any]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        with (self._directory / name).open("a", encoding="utf-8") as sink:
            sink.write(json.dumps(entry) + "\n")

    def _load(self) -> None:
        for entry in _lines(self._directory / SUBMITTED_FILE):
            self._remember(
                SubmittedBatch(
                    provider=entry["provider"],
                    model=entry["model"],
                    batch_id=entry["batch_id"],
                    custom_ids=tuple(entry["custom_ids"]),
                    extra=dict(entry.get("extra") or {}),
                )
            )
        for entry in _lines(self._directory / RESULTS_FILE):
            self._results[entry["custom_id"]] = BatchOutcome(
                custom_id=entry["custom_id"],
                response=entry.get("response"),
                error=entry.get("error"),
            )


def _lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
