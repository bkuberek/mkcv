# Proposal: Job search and a local workspace UI

**Status:** Proposed, not scheduled. Revisit after the first eval run (see `docs/changes/multi-provider-support/` and `evals/README.md`).

## Intent

Let mkcv find relevant job postings, add them to the workspace as applications, and generate tailored résumés and cover letters for them, with a local web UI to browse postings, applications, and the workspace. This turns mkcv from a résumé generator into the place where a job search happens. The workspace already has `applications/`, so the feature extends an existing concept rather than adding a new one.

## Job sources

Most applicant tracking systems (ATS) publish company job boards as public JSON that needs no authentication:

| ATS | Public endpoint | Coverage |
|---|---|---|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{company}/jobs` | Most startups and scale-ups |
| Lever | `https://api.lever.co/v0/postings/{company}?mode=json` | Many startups |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{org}` | Newer startups |
| SmartRecruiters | `https://api.smartrecruiters.com/v1/companies/{id}/postings` | Mid-market |
| Workable | `https://apply.workable.com/api/v3/accounts/{subdomain}/jobs` | Mid-market |
| Workday | No public API; scraping is fragile | Enterprises; out of scope for phase 1 |

Verify each endpoint's current shape and terms before implementation.

**Constraint:** these boards are per company. There is no cross-ATS search, and LinkedIn and Indeed prohibit scraping. mkcv therefore works from a user-curated **company watchlist** (with discovery helpers such as importing a list of company board URLs), syncs those boards into a local index, and searches the index.

Use only public APIs, respect each provider's terms and rate limits, and never scrape sites that forbid it.

## Proposed user experience

### CLI (phase 1)

```text
mkcv jobs watch <company | board-url>   # add a company board to the watchlist
mkcv jobs sync                          # fetch new and changed postings
mkcv jobs search "staff platform remote" [--min-score 0.7] [--new]
mkcv jobs show <job-id>
mkcv jobs add <job-id>                  # create applications/<company>/<role>/<date>/ with the JD
```

`mkcv jobs add` creates the application folder exactly as a manual `mkcv generate --jd` does today and can chain straight into generation.

### Relevance scoring

Score each posting against the user's knowledge base in two passes:

1. A cheap filter on title, location, seniority, and keyword overlap.
2. A strong model for the top matches, returning a score and a short explanation (for example "strong fit: Kubernetes, incident response; gap: Rust").

New postings since the last sync are flagged. Scoring uses the model profile machinery, so the eval-backed recommendation applies here too.

### `mkcv serve` (phase 3)

A local web app bound to localhost, following the `cstudy serve` pattern in bkuberek/coding-study (Starlette and uvicorn):

- **Job feed:** match score, filters, a "new" badge, and an "add to applications" action.
- **Applications board:** saved, applied, interviewing, offer, and closed, with status stored in each application folder.
- **Application detail:** the job description, résumé versions with PDF preview and diffs, the cover letter, and a Generate button with live stage progress and cost.
- **Workspace:** a knowledge base editor and a file browser.

## Architecture

The feature follows the existing hexagonal rules:

- `core/ports/job_source.py`: a `JobSourcePort` protocol, with one adapter per ATS under `adapters/jobs/`.
- `core/ports/job_index.py`: a local index port, with an SQLite and FTS5 adapter stored in the workspace (for example `.mkcv/jobs.db`, git-ignored).
- `core/services/job_matching.py`: relevance scoring through `LLMPort`.
- `core/models/`: `JobPosting`, `JobMatch`, `WatchedBoard`, and `ApplicationStatus` Pydantic models.
- The CLI and the web app call the same services; neither holds business logic.

## Phases

1. **Jobs core and CLI:** Greenhouse, Lever, and Ashby adapters, the local index, KB-based matching, and `mkcv jobs`. High value and low risk.
2. **Application status tracking:** a status field and history in each application folder, plus `mkcv applications` to list and update them. Small, and a prerequisite for the UI.
3. **`mkcv serve`:** the local web UI. The largest surface, built once the data model has settled.

## Out of scope

- Workday and other ATS platforms without a public API.
- Scraping LinkedIn, Indeed, or any site whose terms forbid it.
- Submitting applications automatically.
- A hosted or multi-user service.

## Risks

- **API drift:** public board endpoints can change without notice. Mitigation: per-adapter contract tests against recorded responses, and clear errors when a board fails to parse.
- **Matching cost:** scoring many postings with a strong model adds up. Mitigation: the cheap first pass, caching scores per posting version, and batch APIs.
- **Scope creep:** a UI invites features. Mitigation: ship phases 1 and 2 first and keep the UI a thin layer over the same services.
- **Terms of service:** mitigated by using only documented public endpoints and rate limiting.

## Rollback

Each phase is additive behind new commands (`mkcv jobs`, `mkcv applications`, `mkcv serve`). Removing a phase removes its commands and adapters without touching résumé generation.

## Prerequisites

Run the model evals first, because job matching and automatic generation multiply how much depends on choosing the right models.
