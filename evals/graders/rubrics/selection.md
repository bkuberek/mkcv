Return only the JSON object for the requested schema.

You are scoring an experience selection for a job. You are shown the job description, the candidate's knowledge base, and the selection (the roles chosen, why, the bullets suggested for each, the skills to highlight and omit, and a gap analysis).

Score each criterion from 1 to 5, where 1 is poor, 3 is acceptable, and 5 is excellent. Give a one or two sentence rationale for each score, then a short overall summary. Return exactly these four criteria, using these names.

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| `role_relevance` | Chosen roles have little to do with the job | Most chosen roles are relevant | Every chosen role clearly serves the job, with accurate match reasons |
| `requirement_coverage` | Main JD requirements are not addressed by the chosen bullets | Most main requirements are covered | Every main requirement the knowledge base can support is covered, and real gaps are named |
| `omission_quality` | Strong relevant experience was left out, or irrelevant experience kept | Reasonable cuts, some misses | Irrelevant or weak material is left out and nothing relevant is lost |
| `ordering` | Weakest material leads | Order mostly sensible | Roles and bullets run from most to least relevant |
