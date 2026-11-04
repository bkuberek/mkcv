"""mkcv models — show which model each stage uses and what mkcv recommends."""

import json
import sys
from collections.abc import Callable
from typing import Annotated

import cyclopts
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from mkcv.adapters.factory import create_model_report, create_provider_registry
from mkcv.config import settings
from mkcv.core.catalog.builtin_model_profiles import (
    BUILTIN_MODEL_PROFILES,
    get_profile,
)
from mkcv.core.exceptions.configuration import ConfigurationError
from mkcv.core.models.capability_overlay import CapabilityOverlay
from mkcv.core.models.model_capability import ModelCapability
from mkcv.core.models.model_report import ModelReport
from mkcv.core.models.stage_advice import StageAdvice
from mkcv.core.models.stage_key import StageKey

console = Console()
error_console = Console(stderr=True)

_DEFAULT_PRESET = "standard"
_ESTIMATE_NOTE = "Estimates use rough per-stage token counts; see docs/models.md."
_NOT_AVAILABLE = "n/a"
_UNKNOWN = "unknown"
_NOT_SET = "-"

_SOURCE_NOTES = {
    "default": "default (no --model-profile, no pipeline.model_profile)",
    "config": "config (pipeline.model_profile or pipeline.provider)",
}


def models_command(
    *,
    model_profile: Annotated[
        str | None,
        cyclopts.Parameter(
            name="--model-profile",
            help=(
                "Show this profile's models: anthropic, anthropic-economy, openai, "
                "openai-economy, google, google-economy, local."
            ),
        ),
    ] = None,
    provider: Annotated[
        str | None,
        cyclopts.Parameter(
            help=(
                "Show every stage on this provider's recommended models; with "
                "--catalog, list only this provider's entries."
            ),
        ),
    ] = None,
    preset: Annotated[
        str | None,
        cyclopts.Parameter(
            help="Preset to resolve models for (concise/standard/comprehensive).",
        ),
    ] = None,
    profiles: Annotated[
        bool,
        cyclopts.Parameter(
            name="--profiles",
            negative="",
            help="List the built-in model profiles and their stage models.",
        ),
    ] = False,
    catalog: Annotated[
        bool,
        cyclopts.Parameter(
            name="--catalog",
            negative="",
            help="List the model catalog: capabilities, tiers, and prices.",
        ),
    ] = False,
    as_json: Annotated[
        bool,
        cyclopts.Parameter(
            name="--json",
            negative="",
            help="Print machine-readable JSON instead of tables.",
        ),
    ] = False,
) -> None:
    """Show the model every stage will use, with recommendations and cost.

    By default, resolves the models for your configuration and flags, then
    prints one row per stage with the model mkcv recommends, its quality
    tier, an estimated cost, and warnings for weak or unknown choices.

    Use --profiles to list the built-in model profiles, or --catalog to list
    what mkcv knows about each model. Every profile is provisional until an
    eval run backs it.
    """
    if profiles and catalog:
        error_console.print("[red]Error:[/red] Use either --profiles or --catalog.")
        sys.exit(2)

    if profiles:
        _show_profiles(as_json=as_json)
    elif catalog:
        _show_catalog(provider=provider, as_json=as_json)
    else:
        _show_report(
            preset=preset,
            model_profile=model_profile,
            provider=provider,
            as_json=as_json,
        )


# ------------------------------------------------------------------
# Default view: the resolved models
# ------------------------------------------------------------------


def _show_report(
    *,
    preset: str | None,
    model_profile: str | None,
    provider: str | None,
    as_json: bool,
) -> None:
    report = create_model_report(
        settings,
        preset_name=preset or _DEFAULT_PRESET,
        model_profile=model_profile,
        provider_override=provider,
        include_cover_letter=True,
        extra_stages=(StageKey.KB, StageKey.VALIDATE),
    )
    if as_json:
        _print_json(report.model_dump_json(indent=2))
        return

    source = _source_note(report, model_profile=model_profile, provider=provider)
    console.print(_profile_headline(report))
    console.print(f"Source: {source}   Preset: {report.preset_name}")
    console.print()
    console.print(_stage_table(report))
    console.print()
    console.print(_estimate_line(report))
    console.print(_ESTIMATE_NOTE)
    if report.warnings:
        console.print()
        console.print("Warnings:")
        for warning in report.warnings:
            console.print(f"  {escape(warning.message)}")


def _profile_headline(report: ModelReport) -> str:
    """Return the ``Model profile:`` line, with how well backed the profile is."""
    if report.profile_name is None:
        return "Model profile: none (all stages set explicitly)"
    if report.profile_evidence == "eval":
        profile = get_profile(report.profile_name)
        run = profile.eval_run if profile and profile.eval_run else _UNKNOWN
        return f"Model profile: {report.profile_name} (eval-backed: {run})"
    return (
        f"Model profile: {report.profile_name} "
        "(provisional: not yet backed by an eval run)"
    )


def _source_note(
    report: ModelReport, *, model_profile: str | None, provider: str | None
) -> str:
    """Say where the profile choice came from."""
    if report.profile_source == "cli":
        return "cli (--model-profile)" if model_profile else "cli (--provider)"
    if report.profile_source == "preset":
        return f"preset ({report.preset_name})"
    return _SOURCE_NOTES[report.profile_source]


def _stage_table(report: ModelReport) -> Table:
    table = Table(box=box.SIMPLE_HEAD, header_style="bold", show_edge=False)
    for column in (
        "Stage",
        "Provider",
        "Model",
        "Source",
        "Recommended",
        "Tier",
        "Est. cost",
    ):
        table.add_column(column, no_wrap=True)
    for advice in report.stages:
        table.add_row(*_stage_cells(advice))
    return table


def _stage_cells(advice: StageAdvice) -> tuple[str, ...]:
    assignment = advice.assignment
    recommended = (
        f"{advice.recommended_provider}/{advice.recommended_model}"
        if advice.recommended_provider and advice.recommended_model
        else _NOT_SET
    )
    return tuple(
        escape(cell)
        for cell in (
            assignment.stage.value,
            assignment.provider,
            assignment.model,
            assignment.source,
            recommended,
            advice.tier.value if advice.tier else _UNKNOWN,
            _dollars(advice.estimated_cost_usd, places=4),
        )
    )


def _estimate_line(report: ModelReport) -> str:
    total, partial = report.resume_run_estimate()
    line = f"Estimated cost per resume run (5 stages): {_dollars(total, places=2)}"
    return f"{line} (partial: some prices unknown)" if partial else line


def _dollars(amount: float | None, *, places: int) -> str:
    return _NOT_AVAILABLE if amount is None else f"${amount:.{places}f}"


# ------------------------------------------------------------------
# --profiles
# ------------------------------------------------------------------


def _show_profiles(*, as_json: bool) -> None:
    profiles = list(BUILTIN_MODEL_PROFILES.values())
    if as_json:
        _print_json(json.dumps([p.model_dump(mode="json") for p in profiles], indent=2))
        return

    summary = Table(box=box.SIMPLE_HEAD, header_style="bold", show_edge=False)
    for column in ("Profile", "Provider", "Economy", "Evidence", "Description"):
        summary.add_column(column, no_wrap=column != "Description")
    for profile in profiles:
        summary.add_row(
            escape(profile.name),
            escape(profile.provider),
            "yes" if profile.economy else "no",
            profile.evidence,
            escape(profile.description),
        )
    console.print(summary)

    for profile in profiles:
        stages = Table(box=None, show_header=False, pad_edge=False)
        stages.add_column("Stage", no_wrap=True)
        stages.add_column("Model", no_wrap=True)
        for stage, model in profile.stages.items():
            stages.add_row(stage.value, escape(model))
        console.print()
        console.print(
            f"[bold]{escape(profile.name)}[/bold] ({escape(profile.provider)})"
        )
        console.print(stages)
        if profile.extends:
            console.print(f"[dim]Other stages: as {escape(profile.extends)}[/dim]")


# ------------------------------------------------------------------
# --catalog
# ------------------------------------------------------------------


def _show_catalog(*, provider: str | None, as_json: bool) -> None:
    registry = create_provider_registry(settings)
    if provider is not None:
        registry.get(provider)
    entries = [
        entry
        for entry in registry.catalog.entries
        if provider is None or entry.provider == provider
    ]
    if as_json:
        _print_json(json.dumps([e.model_dump(mode="json") for e in entries], indent=2))
        return
    if not entries:
        console.print(f"No catalog entries for provider '{escape(str(provider))}'.")
        return

    table = Table(box=box.SIMPLE_HEAD, header_style="bold", show_edge=False)
    for column in (
        "Provider",
        "Match",
        "Type",
        "Tier",
        "Structured output",
        "Sampling",
        "In $/Mtok",
        "Out $/Mtok",
    ):
        table.add_column(column, no_wrap=True)
    table.add_column("Notes")
    for entry in entries:
        effective = _effective_capabilities(entry, registry.defaults_for)
        table.add_row(*_catalog_cells(entry, effective))
    console.print(table)


def _effective_capabilities(
    entry: ModelCapability, defaults_for: Callable[[str], CapabilityOverlay]
) -> CapabilityOverlay:
    """Return the entry's capabilities laid over its provider's defaults.

    An entry for a provider that is not defined has no defaults to inherit.
    """
    try:
        defaults = defaults_for(entry.provider)
    except ConfigurationError:
        defaults = CapabilityOverlay()
    return defaults.overlay(entry)


def _catalog_cells(
    entry: ModelCapability, effective: CapabilityOverlay
) -> tuple[str, ...]:
    sampling = effective.accepts_sampling_params
    note = entry.notes or ("deprecated" if effective.deprecated else "")
    return tuple(
        escape(cell)
        for cell in (
            entry.provider,
            entry.match,
            entry.match_type,
            effective.tier.value if effective.tier else _UNKNOWN,
            effective.structured_output.value
            if effective.structured_output
            else _NOT_SET,
            _NOT_SET if sampling is None else ("yes" if sampling else "no"),
            _price(effective.input_price_per_mtok),
            _price(effective.output_price_per_mtok),
            note,
        )
    )


def _price(price: float | None) -> str:
    return _NOT_SET if price is None else f"{price:.2f}"


# ------------------------------------------------------------------
# Output
# ------------------------------------------------------------------


def _print_json(text: str) -> None:
    """Print JSON verbatim: no markup, highlighting, wrapping, or emoji codes."""
    console.print(text, markup=False, highlight=False, soft_wrap=True, emoji=False)
