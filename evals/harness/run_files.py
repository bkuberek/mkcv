"""The names of the files an eval run writes to its output directory."""

RESULTS_FILE = "results.jsonl"
MANIFEST_FILE = "run.json"
SUMMARY_FILE = "summary.json"
REPORT_FILE = "report.md"
USAGE_FILE = "usage.jsonl"
"""Every model call of the run (stage and judge), one JSON line each."""
BATCH_DIR = "batches"
"""Submitted provider batches and their results, for ``run --resume``."""

PUBLISHED_FILES = (RESULTS_FILE, SUMMARY_FILE, REPORT_FILE, MANIFEST_FILE)
"""The files ``report --publish`` copies; the ``raw/`` outputs stay behind."""
