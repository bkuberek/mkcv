"""Render a run's summaries and recommendations as the Markdown report."""

import statistics
from collections.abc import Sequence
from datetime import UTC, datetime

from evals.models.recommendation import Recommendation
from evals.models.run_manifest import RunManifest
from evals.models.stage_summary import StageSummary
from evals.report.aggregator import LOW_SAMPLE_BELOW, ineligible_reasons
from mkcv.core.catalog.builtin_model_profiles import (
    BUILTIN_MODEL_PROFILES,
    profile_stage_model,
)
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS
from mkcv.core.models.stage_key import PIPELINE_STAGES

STAGE_COLUMNS = (
    "Provider",
    "Model",
    "n",
    "OK",
    "Schema",
    "Faithfulness (det)",
    "Faithfulness (judge)",
    "Quality",
    "Cost/run",
    "p50 latency",
    "Eligible",
    "Notes",
)
NO_RESULTS = "No results."


def render_markdown(
    manifest: RunManifest,
    summaries: Sequence[StageSummary],
    recommendations: Sequence[Recommendation],
) -> str:
    """Return the report for one run (design 9.9), ending with a newline."""
    sections = [
        [f"# mkcv eval report: {manifest.run_id}"],
        _run_section(manifest),
        _caveats_section(manifest, summaries),
        _cost_section(summaries),
        *_stage_sections(summaries),
        _recommendations_section(recommendations),
        _profile_changes_section(manifest, recommendations),
        _token_section(summaries),
    ]
    return "\n\n".join("\n".join(lines) for lines in sections) + "\n"


def _run_section(manifest: RunManifest) -> list[str]:
    settings = manifest.matrix.run
    rows = [
        ("Run", manifest.run_id),
        ("Started", _timestamp(manifest.started_at)),
        ("Finished", _timestamp(manifest.finished_at)),
        ("mkcv", manifest.mkcv_version),
        ("Commit", manifest.git_sha or "-"),
        ("Judge", manifest.judge.label),
        ("Cases", ", ".join(manifest.cases) or "-"),
        ("Models", ", ".join(m.label for m in manifest.matrix.models) or "-"),
        ("Repeats", str(settings.repeats)),
        ("Preset", settings.preset),
    ]
    return ["## Run", "", *_table(("Field", "Value"), rows)]


def _caveats_section(
    manifest: RunManifest, summaries: Sequence[StageSummary]
) -> list[str]:
    lines = [
        "- All profiles are provisional until a maintainer applies these results "
        "(see `evals/README.md`)."
    ]
    self_judged = [s for s in summaries if s.self_judged]
    if self_judged:
        lines.append(
            "- Rows that are self-judged (the judge shares the evaluated model's "
            f"provider), so read their quality scores with care: {_rows(self_judged)}."
        )
    small = [s for s in summaries if s.low_sample]
    if small:
        lines.append(
            f"- Rows with a low sample (fewer than {LOW_SAMPLE_BELOW} runs): "
            f"{_rows(small)}."
        )
    if manifest.skipped_models:
        lines.append("- Models that did not run:")
        lines.extend(f"  - {reason}" for reason in manifest.skipped_models)
    if manifest.judge_skipped:
        lines.append(
            f"- The judge did not run ({manifest.judge_skipped}); scores that "
            "need a judge are missing."
        )
    failed = sum(s.n - round(s.n * s.ok_rate) for s in summaries)
    if failed:
        noun = "record" if failed == 1 else "records"
        lines.append(f"- {failed} {noun} failed (see `results.jsonl`).")
    return ["## Caveats", "", *lines]


def _cost_section(summaries: Sequence[StageSummary]) -> list[str]:
    if not summaries:
        return ["## Cost", "", NO_RESULTS]
    totals: dict[tuple[str, str], tuple[int, float]] = {}
    for s in summaries:
        runs = round(s.n * s.ok_rate)
        runs_so_far, cost_so_far = totals.get((s.provider, s.model), (0, 0.0))
        totals[s.provider, s.model] = (
            runs_so_far + runs,
            cost_so_far + (s.cost_mean_usd or 0.0) * runs,
        )
    rows = [
        (provider, model, str(runs), _usd(cost), _usd(cost / runs if runs else None))
        for (provider, model), (runs, cost) in sorted(totals.items())
    ]
    return [
        "## Cost",
        "",
        *_table(("Provider", "Model", "Runs", "Total cost", "Mean per run"), rows),
        "",
        "Costs are the evaluated models' tokens at catalog prices (completed runs "
        "only). Judge calls are not included.",
    ]


def _stage_sections(summaries: Sequence[StageSummary]) -> list[list[str]]:
    sections: list[list[str]] = []
    for stage in PIPELINE_STAGES:
        rows = [_stage_row(s) for s in summaries if s.stage is stage]
        if rows:
            sections.append(
                [f"## Stage: {stage.value}", "", *_table(STAGE_COLUMNS, rows)]
            )
    return sections


def _stage_row(s: StageSummary) -> tuple[str, ...]:
    return (
        s.provider,
        s.model,
        str(s.n),
        f"{s.ok_rate:.0%}",
        _score(s.mean.get("schema")),
        _score(s.mean.get("faithfulness_extraction")),
        _score(s.mean.get("faithfulness_judge")),
        _score(s.primary_score),
        _usd(s.cost_mean_usd),
        _seconds(s.latency_p50_s),
        "yes" if s.eligible else "no",
        ", ".join(_notes(s)),
    )


def _notes(s: StageSummary) -> list[str]:
    notes = [] if s.eligible else ineligible_reasons(s.ok_rate, s.mean)
    if s.primary_score is None:
        notes.append("no quality score")
    if s.self_judged:
        notes.append("self-judged")
    if s.low_sample:
        notes.append(f"low sample (n<{LOW_SAMPLE_BELOW})")
    return notes


def _recommendations_section(recommendations: Sequence[Recommendation]) -> list[str]:
    if not recommendations:
        return ["## Recommendations", "", NO_RESULTS]
    rows = [
        (
            r.stage.value,
            r.provider,
            r.best or "-",
            r.recommended or "-",
            r.economy or "-",
            r.reason,
        )
        for r in recommendations
    ]
    columns = ("Stage", "Provider", "Best", "Recommended", "Economy", "Reason")
    return ["## Recommendations", "", *_table(columns, rows)]


def _profile_changes_section(
    manifest: RunManifest, recommendations: Sequence[Recommendation]
) -> list[str]:
    by_stage_provider = {(r.stage, r.provider): r for r in recommendations}
    changes: list[str] = []
    for profile in BUILTIN_MODEL_PROFILES.values():
        for stage in PIPELINE_STAGES:
            rec = by_stage_provider.get((stage, profile.provider))
            target = (
                (rec.economy if profile.economy else rec.recommended) if rec else None
            )
            current = profile_stage_model(profile, stage)
            if target and target != current:
                changes.append(
                    f"- {profile.name} / {stage.value}: {current} → {target}"
                )
    return [
        "## Suggested profile changes",
        "",
        "Apply these by hand in `src/mkcv/core/catalog/builtin_model_profiles.py` "
        f'(set `evidence="eval"` and `eval_run="{manifest.run_id}"`) and '
        "`docs/models.md`, citing the published report.",
        "",
        *(changes or ["No changes suggested."]),
    ]


def _token_section(summaries: Sequence[StageSummary]) -> list[str]:
    rows: list[tuple[str, ...]] = []
    for stage in PIPELINE_STAGES:
        measured_in = [
            s.median_input_tokens
            for s in summaries
            if s.stage is stage and s.median_input_tokens is not None
        ]
        measured_out = [
            s.median_output_tokens
            for s in summaries
            if s.stage is stage and s.median_output_tokens is not None
        ]
        if measured_in and measured_out:
            requirement = STAGE_REQUIREMENTS[stage]
            rows.append(
                (
                    stage.value,
                    f"{statistics.median(measured_in):.0f}",
                    f"{statistics.median(measured_out):.0f}",
                    str(requirement.est_input_tokens),
                    str(requirement.est_output_tokens),
                )
            )
    if not rows:
        return ["## Token estimates", "", "No measurements."]
    columns = (
        "Stage",
        "Measured input (median)",
        "Measured output (median)",
        "Estimated input",
        "Estimated output",
    )
    return [
        "## Token estimates",
        "",
        "Measured medians (across models) beside the planning estimates in "
        "`STAGE_REQUIREMENTS`.",
        "",
        *_table(columns, rows),
    ]


def _table(columns: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return lines


def _rows(summaries: Sequence[StageSummary]) -> str:
    return ", ".join(f"{s.provider}/{s.model} ({s.stage.value})" for s in summaries)


def _timestamp(moment: datetime | None) -> str:
    if moment is None:
        return "-"
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def _score(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _usd(value: float | None) -> str:
    return "-" if value is None else f"${value:.4f}"


def _seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}s"
