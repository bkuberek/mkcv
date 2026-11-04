"""Record the tokens of every model call a run makes, in memory and on disk."""

from pathlib import Path

from evals.models.call_usage import CallUsage


class UsageLedger:
    """Every call's usage, appended to ``path`` (one JSON line each) when given."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._entries: list[CallUsage] = []

    @property
    def entries(self) -> list[CallUsage]:
        """The calls recorded so far, in order."""
        return list(self._entries)

    def record(self, usage: CallUsage) -> None:
        """Keep ``usage`` and append it to the file."""
        self._entries.append(usage)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as sink:
                sink.write(usage.model_dump_json() + "\n")

    def for_scope(self, scope: str) -> list[CallUsage]:
        """The calls the job ``scope`` made itself."""
        return [entry for entry in self._entries if entry.scope == scope]


def read_usage(path: Path) -> list[CallUsage]:
    """Return the calls recorded in ``path``, or none if it does not exist."""
    if not path.is_file():
        return []
    return [
        CallUsage.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
