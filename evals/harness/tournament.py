"""The two-round tournament: who is screened, by whom, and who reaches the finals."""

import math
from collections.abc import Sequence

from evals.models.eval_case import EvalCase
from evals.models.judge_config import JudgeConfig
from evals.models.matrix_model import MatrixModel
from evals.models.screening_decision import ScreeningDecision
from evals.models.stage_summary import StageSummary
from evals.models.tournament_settings import TournamentSettings
from evals.report.recommender import lead_noise
from evals.stages import stage_position
from mkcv.core.models.stage_key import StageKey

_EPSILON = 1e-9


def screening_cases(
    cases: Sequence[EvalCase], settings: TournamentSettings
) -> list[EvalCase]:
    """Return the cases the screening round runs.

    They are the ``settings.screening_cases`` among ``cases``, in the order
    listed, then every review probe (resume or cover letter) not already
    listed, since only the probes give the review stages a quality score.
    With no subset configured, or none of it among ``cases`` (a run narrowed
    with ``--cases``), every case is screened.
    """
    by_id = {case.id: case for case in cases}
    chosen = [by_id[name] for name in settings.screening_cases if name in by_id]
    if not chosen:
        return list(cases)
    probes = [
        case
        for case in cases
        if (case.review_probe_defects or case.is_cover_letter_probe)
        and case not in chosen
    ]
    return [*chosen, *probes]


def unknown_screening_cases(
    known: Sequence[EvalCase], settings: TournamentSettings
) -> list[str]:
    """Return the configured screening case IDs that no case in ``known`` has."""
    ids = {case.id for case in known}
    return [name for name in settings.screening_cases if name not in ids]


def screening_judges(
    model: MatrixModel, panel: Sequence[JudgeConfig]
) -> list[JudgeConfig]:
    """Return the judges that screen ``model``: the finals' rule.

    They are every judge of the panel but the one from the model's own
    provider, and the grade is their mean, so a harsh or lenient judge
    weighs on every provider alike and no screening score is self-judged.
    With only judges of the model's own provider, those (the grade is then
    self-judged); with no judge, none.
    """
    others = [judge for judge in panel if judge.provider != model.provider]
    return others or list(panel)


def decide_survivors(
    summaries: Sequence[StageSummary], settings: TournamentSettings
) -> list[ScreeningDecision]:
    """Return, per stage, whether each screened model goes on to the finals.

    A model is eliminated only when it failed a hard gate, or when its
    primary score trails the stage leader's by more than ``margin`` plus the
    noise of the leader's lead over it (the standard error of their per-case
    differences). The top ``keep_top`` models (eligible ones first, then by
    score) and the best ``keep_per_provider`` of each provider always go on,
    so every provider profile can still be filled. A model without a quality
    score cannot be compared, so it goes on too.
    """
    by_stage: dict[StageKey, list[StageSummary]] = {}
    for summary in summaries:
        by_stage.setdefault(summary.stage, []).append(summary)
    decisions: list[ScreeningDecision] = []
    for stage in sorted(by_stage, key=stage_position):
        decisions.extend(_decide_stage(stage, by_stage[stage], settings))
    return decisions


def finals_models(decisions: Sequence[ScreeningDecision]) -> dict[StageKey, set[str]]:
    """``provider/model`` of the models that go on, per stage."""
    survivors: dict[StageKey, set[str]] = {}
    for decision in decisions:
        if decision.kept:
            survivors.setdefault(decision.stage, set()).add(decision.label)
    return survivors


def _decide_stage(
    stage: StageKey, group: list[StageSummary], settings: TournamentSettings
) -> list[ScreeningDecision]:
    ranked = sorted(group, key=_rank)
    floor = {
        id(summary): "in the top " + str(settings.keep_top)
        for summary in ranked[: settings.keep_top]
    }
    for provider in sorted({s.provider for s in group}):
        best = [s for s in ranked if s.provider == provider][
            : settings.keep_per_provider
        ]
        for summary in best:
            floor.setdefault(id(summary), f"best of {provider}")
    scored = [s for s in ranked if s.eligible and s.primary_score is not None]
    leader = scored[0] if scored else None

    decisions: list[ScreeningDecision] = []
    for summary in group:
        kept, reason = _verdict(summary, leader, floor.get(id(summary)), settings)
        decisions.append(
            ScreeningDecision(
                stage=stage,
                provider=summary.provider,
                model=summary.model,
                score=summary.primary_score,
                kept=kept,
                reason=reason,
            )
        )
    return decisions


def _verdict(
    summary: StageSummary,
    leader: StageSummary | None,
    floor_reason: str | None,
    settings: TournamentSettings,
) -> tuple[bool, str]:
    if floor_reason is not None:
        return True, floor_reason
    if not summary.eligible:
        return False, "failed a hard gate: " + "; ".join(summary.gate_failures)
    if summary.primary_score is None or leader is None or leader.primary_score is None:
        return True, "no quality score to compare"
    gap = leader.primary_score - summary.primary_score
    noise = lead_noise(leader, summary) or 0.0
    zone = settings.margin + noise
    if gap > zone + _EPSILON:
        return False, (
            f"{gap:.2f} behind the leader {leader.provider}/{leader.model} "
            f"(margin {settings.margin} + noise {noise:.2f})"
        )
    return True, f"within {zone:.2f} of the leader"


def _rank(summary: StageSummary) -> tuple[bool, float]:
    score = summary.primary_score
    return (not summary.eligible, -score if score is not None else math.inf)
