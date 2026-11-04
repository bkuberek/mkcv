"""The names of the files an eval run writes to its output directory."""

RESULTS_FILE = "results.jsonl"
MANIFEST_FILE = "run.json"
SUMMARY_FILE = "summary.json"
REPORT_FILE = "report.md"

PUBLISHED_FILES = (RESULTS_FILE, SUMMARY_FILE, REPORT_FILE, MANIFEST_FILE)
"""The files ``report --publish`` copies; the ``raw/`` outputs stay behind."""
