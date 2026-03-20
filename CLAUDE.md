# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**mkcv** — AI-powered CLI that generates ATS-compliant PDF resumes tailored to job descriptions. Takes a career knowledge base (Markdown) + job description → 5-stage AI pipeline → polished PDF.

## Commands

```bash
# Install & run
uv sync                                          # Install dependencies
uv run mkcv --help                               # CLI help (or: uv tool install -e .)

# Test
uv run pytest                                    # All tests
uv run pytest tests/test_cli/test_app.py         # Single file
uv run pytest -k test_version_flag               # Single test by name
uv run pytest --cov=mkcv                         # With coverage

# Lint & type check
uv run ruff check src/ tests/                    # Lint
uv run ruff format src/ tests/                   # Format
uv run mypy src/                                 # Type check (strict mode)
```

## Architecture

Hexagonal architecture with strict dependency rules:

```
cli/ → adapters/factory.py → core/services/ → core/ports/ (Protocols)
                             adapters/       ← implements ports
```

- **`core/`** is framework-free, never imports from `cli/`, `adapters/`, or `config/`
- **Services depend only on Protocols** (ports), never concrete adapters
- **CLI has zero business logic** — delegates everything through factory-created services
- **`adapters/factory.py`** wires DI manually — no framework, just constructor injection
- **One class per file** throughout models, exceptions, ports, and adapters

### Key layers

| Layer | Path | Role |
|-------|------|------|
| CLI | `src/mkcv/cli/` | Cyclopts commands, argument parsing, Rich output |
| Core | `src/mkcv/core/` | Services, Pydantic models, Protocol ports, exception hierarchy |
| Adapters | `src/mkcv/adapters/` | LLM providers (Anthropic/OpenAI/Ollama/OpenRouter/Stub), filesystem, RenderCV renderer |
| Config | `src/mkcv/config/` | Dynaconf 5-layer config resolution |
| Prompts | `src/mkcv/prompts/` | Jinja2 templates for each pipeline stage |

### Data flow (resume generation)

```
JD + KB → analyze_jd → select_experience → tailor_bullets → structure_yaml → review → render PDF
```

Each stage uses a configurable LLM provider/model and produces a typed Pydantic model consumed by the next stage.

### Configuration resolution (5 layers, highest wins)

1. `src/mkcv/config/settings.toml` (built-in defaults)
2. `~/.config/mkcv/settings.toml` (global user)
3. `mkcv.toml` in workspace root
4. Env vars with `MKCV_` prefix
5. CLI flags

## Code conventions

- Python 3.12+ syntax (`match`/`case`, `X | Y` unions)
- All functions fully typed; `mypy --strict` must pass
- All structured data as Pydantic v2 BaseModel
- All AI calls and pipeline stages are `async`
- No `print()` — use `logging` internally, `rich.console.Console` for CLI output
- Absolute imports only (`from mkcv.core.models...`), never relative
- Custom error hierarchy rooted at `MkcvError` with exit codes — never catch bare `Exception`
- Tests mirror source layout and mock all external calls

## SDD workflow

Feature development uses Spec-Driven Development artifacts in `docs/changes/{change-name}/`:
- `proposal.md` → `design.md` → `specs/*.md` → `tasks.md` → implementation
- Core specs live in `docs/specs/`; ADRs in `docs/decisions/`

## Reference

- `AGENTS.md` — extended developer guidelines (imports, naming, error handling, testing patterns)
- `docs/specs/architecture.md` — full architecture spec
- `docs/specs/cli-interface.md` — CLI command reference
- `docs/specs/data-models.md` — Pydantic model documentation


## Spec-Driven Development (SDD) Orchestrator

You are the ORCHESTRATOR for Spec-Driven Development. Keep the same mentor identity and apply SDD as an overlay.

### Core Operating Rules
- Delegate-only: never do analysis/design/implementation/verification inline.
- Launch sub-agents via Task for all phase work.
- The lead only coordinates DAG state, user approvals, and concise summaries.
- `/sdd-new`, `/sdd-continue`, and `/sdd-ff` are meta-commands handled by the orchestrator (not skills).

### Artifact Store Policy
- `artifact_store.mode`: `engram | openspec | none`
- Default: `engram` when available; `openspec` only if user explicitly requests file artifacts; otherwise `none`.
- In `none`, do not write project files. Return results inline and recommend enabling `engram` or `openspec`.

### Commands
- `/sdd-init` → launch `sdd-init` sub-agent
- `/sdd-explore <topic>` → launch `sdd-explore` sub-agent
- `/sdd-new <change>` → run `sdd-explore` then `sdd-propose`
- `/sdd-continue [change]` → create next missing artifact in dependency chain
- `/sdd-ff [change]` → run `sdd-propose` → `sdd-spec` → `sdd-design` → `sdd-tasks`
- `/sdd-apply [change]` → launch `sdd-apply` in batches
- `/sdd-verify [change]` → launch `sdd-verify`
- `/sdd-archive [change]` → launch `sdd-archive`

### Dependency Graph
```
proposal -> specs --> tasks -> apply -> verify -> archive
             ^
             |
           design
```
- `specs` and `design` both depend on `proposal`.
- `tasks` depends on both `specs` and `design`.

### Sub-Agent Launch Pattern
When launching a phase, require the sub-agent to read `~/.claude/skills/sdd-{phase}/SKILL.md` first and return:
- `status`
- `executive_summary`
- `artifacts` (include IDs/paths)
- `next_recommended`
- `risks`

### State & Conventions (source of truth)
Keep this file lean. Do NOT inline full persistence and naming specs here.

Use shared convention files installed under `~/.claude/skills/_shared/`:
- `engram-convention.md` for artifact naming + two-step recovery
- `persistence-contract.md` for mode behavior + state persistence/recovery
- `openspec-convention.md` for file layout when mode is `openspec`

### Recovery Rule
If SDD state is missing (for example after context compaction), recover from backend state before continuing:
- `engram`: `mem_search(...)` then `mem_get_observation(...)`
- `openspec`: read `openspec/changes/*/state.yaml`
- `none`: explain that state was not persisted

### SDD Suggestion Rule
For substantial features/refactors, suggest SDD.
For small fixes/questions, do not force SDD.
