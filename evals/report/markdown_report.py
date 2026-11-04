"""Render a run's summaries and recommendations as the Markdown report."""

import statistics
from collections.abc import Sequence
from datetime import UTC, datetime

from evals.graders.judge_panel import AGREEMENT_SPREAD
from evals.graders.stage_graders import JUDGED_GRADES, PRIMARY_METRIC
from evals.harness.pricing import actual_cost, online_cost
from evals.models.call_usage import CallUsage
from evals.models.judge_config import JudgeConfig
from evals.models.recommendation import OVERALL, Recommendation
from evals.models.run_manifest import RunManifest
from evals.models.screening_decision import ScreeningDecision
from evals.models.stage_summary import StageSummary
from evals.models.suggested_profile import SuggestedProfile
from evals.report.aggregator import LOW_SAMPLE_BELOW
from evals.report.profile_suggester import (
    RECOMMENDED_PROFILE,
    not_evaluated,
    suggest_profiles,
)
from evals.stages import EVALUATED_STAGES
from mkcv.core.catalog.stage_requirements import STAGE_REQUIREMENTS

STAGE_COLUMNS = (
    "Provider",
    "Model",
    "n",
    "OK",
    "Schema",
    "Fabricated (det)",
    "Fabricated (judge)",
    "Faithfulness (judge)",
    "Quality (mean ± sd)",
    "All judges",
    "Judge spread",
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
    *,
    screening: Sequence[ScreeningDecision] = (),
    screening_only: bool = False,
    usage: Sequence[CallUsage] = (),
) -> str:
    """Return the report for one run (design 9.9), ending with a newline.

    ``summaries`` and ``recommendations`` come from the finals (or the single
    round); ``screening`` holds the screening round's decisions, if any, and
    ``screening_only`` says the summaries are the screening's own. ``usage``
    lists every call of the run (``usage.jsonl``); with it the cost section
    sets what the calls cost as sent beside their online price.
    """
    sections = [
        [f"# mkcv eval report: {manifest.run_id}"],
        _run_section(manifest),
        _caveats_section(manifest, summaries, screening_only=screening_only),
        _judge_panel_section(manifest, summaries),
        _usage_cost_section(manifest, usage) if usage else _cost_section(summaries),
        *([_tournament_section(screening)] if screening else []),
        *_stage_sections(summaries, recommendations),
        _recommendations_section(manifest, summaries, recommendations),
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
        ("Judges", ", ".join(j.label for j in manifest.panel) or "-"),
        ("Judges that ran", ", ".join(manifest.judges_that_ran) or "none"),
        ("Cases", ", ".join(manifest.cases) or "-"),
        ("Models", ", ".join(m.label for m in manifest.matrix.models) or "-"),
        ("Repeats", str(settings.repeats)),
        ("Preset", settings.preset),
    ]
    return ["## Run", "", *_table(("Field", "Value"), rows)]


def _caveats_section(
    manifest: RunManifest,
    summaries: Sequence[StageSummary],
    *,
    screening_only: bool = False,
) -> list[str]:
    lines = [
        "- All profiles are provisional until a maintainer applies these results "
        "(see `evals/README.md`)."
    ]
    if screening_only:
        lines.append(
            "- Only the screening round has run: one judge per model and a subset "
            "of cases. Run the finals before adopting anything below."
        )
    self_judged = [s for s in summaries if s.self_judged]
    if self_judged:
        lines.append(
            "- Rows that are self-judged (only a judge from the evaluated model's "
            "own provider scored them), so read their quality scores with care: "
            f"{_rows(self_judged)}."
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
    skipped_judges = manifest.judge_skip_reasons
    if skipped_judges:
        lines.append("- Judges that did not run:")
        lines.extend(
            f"  - {label}: {reason}" for label, reason in skipped_judges.items()
        )
    if manifest.panel and not manifest.judges_that_ran:
        lines.append("- No judge ran, so every score that needs a judge is missing.")
    failed = sum(s.n - round(s.n * s.ok_rate) for s in summaries)
    if failed:
        noun = "record" if failed == 1 else "records"
        lines.append(f"- {failed} {noun} failed (see `results.jsonl`).")
    return ["## Caveats", "", *lines]


def _judge_panel_section(
    manifest: RunManifest, summaries: Sequence[StageSummary]
) -> list[str]:
    lines = [
        "## Judge panel",
        "",
        "Every judge that ran scores each judged output, and the output's score "
        "is their mean. A model's quality score leaves out the judge from its own "
        "provider whenever another judge scored it, to remove self-preference; "
        "the *All judges* column keeps every judge.",
        "",
    ]
    judged = sum(s.judged_outputs for s in summaries)
    if len(manifest.judges_that_ran) < 2 or not judged:
        return [*lines, "One judge (or none) ran, so there is no agreement to report."]
    agreeing = sum((s.judge_agreement or 0.0) * s.judged_outputs for s in summaries)
    spread = sum((s.judge_spread or 0.0) * s.judged_outputs for s in summaries)
    lines.append(
        f"The judges were within {AGREEMENT_SPREAD} of each other on "
        f"{agreeing / judged:.0%} of {judged} judged outputs (mean spread "
        f"{spread / judged:.2f})."
    )
    rows = _judge_means(manifest.panel, summaries)
    if rows:
        columns = ("Stage", *(judge.label for judge in manifest.panel))
        lines.extend(
            [
                "",
                "Mean primary score each judge gave, across the stage's models:",
                "",
                *_table(columns, rows),
            ]
        )
    return lines


def _judge_means(
    panel: Sequence[JudgeConfig], summaries: Sequence[StageSummary]
) -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for stage in EVALUATED_STAGES:
        stage_rows = [s for s in summaries if s.stage is stage and s.primary_by_judge]
        if not stage_rows:
            continue
        cells = []
        for judge in panel:
            values = [
                s.primary_by_judge[judge.label]
                for s in stage_rows
                if judge.label in s.primary_by_judge
            ]
            cells.append(_score(statistics.fmean(values)) if values else "-")
        rows.append((stage.value, *cells))
    return rows


def _tournament_section(decisions: Sequence[ScreeningDecision]) -> list[str]:
    dropped = sum(1 for d in decisions if not d.kept)
    rows = [
        (
            d.stage.value,
            d.provider,
            d.model,
            _score(d.score),
            "yes" if d.kept else "no",
            d.reason,
        )
        for d in decisions
    ]
    return [
        "## Tournament",
        "",
        "Screening ran every model on a subset of cases (and every review "
        "probe) once, graded by one judge from another provider. A model left "
        "a stage only when it failed a hard gate or trailed the leader by more "
        "than the margin plus the noise of that lead; the top models of each "
        "stage and the best of each provider always went on. The finals ran "
        "the survivors on every case with the whole judge panel, and the rest "
        f"of this report is theirs. {dropped} of {len(decisions)} screened "
        "stage entries were eliminated.",
        "",
        *_table(
            ("Stage", "Provider", "Model", "Screening quality", "Finals", "Why"),
            rows,
        ),
    ]


def _usage_cost_section(manifest: RunManifest, usage: Sequence[CallUsage]) -> list[str]:
    groups: dict[tuple[str, str, str], list[CallUsage]] = {}
    for call in usage:
        role = "judge" if "/judge/" in (call.scope or "") else "evaluated"
        groups.setdefault((call.provider, call.model, role), []).append(call)
    rows: list[tuple[str, ...]] = []
    online_total = actual_total = 0.0
    unpriced = False
    for (provider, model, role), calls in sorted(groups.items()):
        price = manifest.catalog_prices.get(f"{provider}/{model}")
        if price is None:
            unpriced = True
            online = actual = None
        else:
            online = sum(online_cost(call, price) for call in calls)
            actual = sum(
                actual_cost(call, price, manifest.matrix.pricing) for call in calls
            )
            online_total += online
            actual_total += actual
        rows.append(
            (
                provider,
                model,
                role,
                str(len(calls)),
                str(sum(call.batched for call in calls)),
                str(sum(call.cache_read_tokens for call in calls)),
                _usd(online),
                _usd(actual),
            )
        )
    saved = online_total - actual_total
    share = saved / online_total if online_total else 0.0
    columns = (
        "Provider",
        "Model",
        "Role",
        "Calls",
        "Batched",
        "Cache read tokens",
        "Online cost",
        "Actual cost",
    )
    return [
        "## Cost",
        "",
        *_table(columns, rows),
        "",
        f"Online: {_usd(online_total)}; as sent: {_usd(actual_total)} "
        f"(saved {_usd(saved)}, {share:.0%}). Every stage and judge call is "
        "counted at catalog prices, with the batch discount and cache prices of "
        "`[pricing]`."
        + (" Some models have no catalog price and are left out." if unpriced else ""),
    ]


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


def _stage_sections(
    summaries: Sequence[StageSummary], recommendations: Sequence[Recommendation]
) -> list[list[str]]:
    sections: list[list[str]] = []
    for stage in EVALUATED_STAGES:
        rows = [_stage_row(s) for s in summaries if s.stage is stage]
        if rows:
            recs = [r for r in recommendations if r.stage is stage]
            sections.append(
                [
                    f"## Stage: {stage.value}",
                    "",
                    f"Primary score: `{PRIMARY_METRIC.get(stage, '-')}`.",
                    "",
                    *_winner_lines(recs),
                    *_table(STAGE_COLUMNS, rows),
                ]
            )
    return sections


def _winner_lines(recs: Sequence[Recommendation]) -> list[str]:
    overall = next((r for r in recs if r.scope == OVERALL), None)
    per_provider = [r for r in recs if r.scope != OVERALL]
    lines: list[str] = []
    if overall is not None:
        lines.extend([_best_overall_line(overall), ""])
    if per_provider:
        rows = [
            (r.scope, r.model or "-", _score(r.score), r.reason) for r in per_provider
        ]
        columns = ("Provider", "Best model", "Quality", "Why")
        lines.extend([*_table(columns, rows), ""])
    return lines


def _best_overall_line(rec: Recommendation) -> str:
    if rec.label is None:
        return f"Best overall: none ({rec.reason})"
    line = f"Best overall: **{rec.label}** ({_quality(rec.score, rec.std)})."
    if rec.decided_by_cost:
        line += f" Cost decided a tie with {', '.join(rec.tied_with)}."
    if rec.too_close_to_call:
        runners_up = "; ".join(
            f"{r.label} ({r.score:.2f}; lead {r.margin:.2f}, noise {_score(r.noise)})"
            for r in rec.runners_up
        )
        line += (
            " **Too close to call.** Its lead is smaller than the noise over: "
            f"{runners_up}."
        )
    return line


def _stage_row(s: StageSummary) -> tuple[str, ...]:
    return (
        s.provider,
        s.model,
        str(s.n),
        f"{s.ok_rate:.0%}",
        _score(s.mean.get("schema")),
        _percent(s.fabrication_rate.get("faithfulness_extraction")),
        _percent(s.fabrication_rate.get("faithfulness_judge")),
        _score(s.mean.get("faithfulness_judge")),
        _quality(s.primary_score, s.primary_std),
        _score(s.mean.get(PRIMARY_METRIC.get(s.stage, ""))) if _is_judged(s) else "-",
        _score(s.judge_spread),
        _usd(s.cost_mean_usd),
        _seconds(s.latency_p50_s),
        "yes" if s.eligible else "no",
        ", ".join(_notes(s)),
    )


def _is_judged(s: StageSummary) -> bool:
    return PRIMARY_METRIC.get(s.stage, "") in JUDGED_GRADES


def _notes(s: StageSummary) -> list[str]:
    notes = list(s.gate_failures)
    if s.primary_score is None:
        notes.append("no quality score")
    if s.self_judged:
        notes.append("self-judged")
    if s.low_sample:
        notes.append(f"low sample (n<{LOW_SAMPLE_BELOW})")
    return notes


def _recommendations_section(
    manifest: RunManifest,
    summaries: Sequence[StageSummary],
    recommendations: Sequence[Recommendation],
) -> list[str]:
    missing = [
        f"- {stage.value}: {reason}"
        for stage, reason in not_evaluated(summaries).items()
    ]
    footer = ["", "Not evaluated:", "", *missing]
    if not recommendations:
        return ["## Recommendations", "", NO_RESULTS, *footer]
    epsilon = manifest.matrix.recommendation.tie_epsilon
    providers = sorted({r.scope for r in recommendations if r.scope != OVERALL})
    rows: list[tuple[str, ...]] = []
    for stage in EVALUATED_STAGES:
        overall = next(
            (r for r in recommendations if r.stage is stage and r.scope == OVERALL),
            None,
        )
        if overall is None:
            continue
        cells = {
            r.scope: _cell(r)
            for r in recommendations
            if r.stage is stage and r.scope != OVERALL
        }
        rows.append(
            (
                stage.value,
                overall.label or "-",
                _score(overall.score),
                *(cells.get(provider, "-") for provider in providers),
                "; ".join(_recommendation_notes(overall)),
            )
        )
    columns = ("Stage", "Best overall", "Quality", *providers, "Notes")
    return [
        "## Recommendations",
        "",
        "Each stage recommends the eligible model with the highest quality score, "
        "across all providers and within each one. Cost only breaks a tie: models "
        f"within {epsilon} of the best score count as tied, and the cheapest wins. "
        "A win is *too close to call* when its lead over another model is smaller "
        "than the noise: the standard error of the per-case differences between "
        "the two. Those runners-up are listed; re-run with more repeats or cases "
        "to separate them.",
        "",
        *_table(columns, rows),
        *footer,
    ]


def _cell(rec: Recommendation) -> str:
    return "-" if rec.model is None else f"{rec.model} ({_score(rec.score)})"


def _recommendation_notes(rec: Recommendation) -> list[str]:
    if rec.model is None:
        return [rec.reason]
    notes: list[str] = []
    if rec.decided_by_cost:
        notes.append(f"cost tie with {', '.join(rec.tied_with)}")
    if rec.too_close_to_call:
        labels = ", ".join(r.label for r in rec.runners_up)
        notes.append(f"too close to call: {labels}")
    return notes


def _profile_changes_section(
    manifest: RunManifest, recommendations: Sequence[Recommendation]
) -> list[str]:
    profiles = suggest_profiles(recommendations)
    changes = [
        f"- {profile.name} / {choice.stage.value}: {choice.current} → {choice.model}"
        + (" (too close to call)" if choice.too_close_to_call else "")
        for profile in profiles
        if profile.provider is not None
        for choice in profile.changes
    ]
    lines = [
        "## Suggested profile changes",
        "",
        "Nothing here is applied automatically. Apply provider profile changes by "
        "hand in `src/mkcv/core/catalog/builtin_model_profiles.py` "
        f'(set `evidence="eval"` and `eval_run="{manifest.run_id}"`) and '
        "`docs/models.md`, citing the published report.",
        "",
        "### Provider profiles",
        "",
        "Each provider profile follows that provider's best model. Economy "
        "profiles are not changed: this rule recommends the best model, not "
        "the cheapest.",
        "",
        *(changes or ["No changes suggested."]),
    ]
    recommended = next((p for p in profiles if p.name == RECOMMENDED_PROFILE), None)
    if recommended is not None:
        lines.extend(["", *_recommended_lines(recommended)])
    return lines


def _recommended_lines(profile: SuggestedProfile) -> list[str]:
    rows = [
        (
            c.stage.value,
            c.provider,
            c.model,
            _score(c.score),
            "too close to call" if c.too_close_to_call else "",
        )
        for c in profile.choices
    ]
    settings: list[str] = []
    for choice in profile.choices:
        settings.extend(
            [
                f"[default.{STAGE_REQUIREMENTS[choice.stage].config_path}]",
                f'provider = "{choice.provider}"',
                f'model = "{choice.model}"',
                "",
            ]
        )
    return [
        f"### Cross-provider profile `{RECOMMENDED_PROFILE}`",
        "",
        "The best model of every stage, whatever its provider. A built-in "
        "profile runs on one provider, so until profiles can mix providers this "
        "is a suggestion for your settings, written below as `mkcv.toml` stage "
        "overrides.",
        "",
        *_table(("Stage", "Provider", "Model", "Quality", "Notes"), rows),
        "",
        "```toml",
        *settings[:-1],
        "```",
    ]


def _token_section(summaries: Sequence[StageSummary]) -> list[str]:
    rows: list[tuple[str, ...]] = []
    for stage in EVALUATED_STAGES:
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


def _quality(value: float | None, std: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}" if std is None else f"{value:.2f} ± {std:.2f}"


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.0%}"


def _usd(value: float | None) -> str:
    return "-" if value is None else f"${value:.4f}"


def _seconds(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}s"
