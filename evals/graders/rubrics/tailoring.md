Return only the JSON object for the requested schema.

You are scoring tailored resume content for a job. You are shown the job description, the candidate's knowledge base, and the tailored content (a mission statement, skill groups, and roles with rewritten bullets).

Score each criterion from 1 to 5, where 1 is poor, 3 is acceptable, and 5 is excellent. Give a one or two sentence rationale for each score, then a short overall summary. Return exactly these five criteria, using these names.

| Criterion | 1 | 3 | 5 |
|---|---|---|---|
| `relevance` | Bullets ignore the JD's main requirements | Most bullets map to some requirement | Every bullet supports a stated requirement, strongest first |
| `keyword_integration` | JD terms missing or stuffed | Key terms present but sometimes forced | Key terms woven in naturally, only where the KB supports them |
| `impact` | Duties, no outcomes | Some outcomes, few numbers | Outcome-first bullets using every KB-supported metric |
| `clarity` | Long, vague, or repetitive | Clear with some filler | Concise, specific, one idea per bullet, strong verbs |
| `prioritization` | Irrelevant roles and bullets lead | Order mostly sensible | Most relevant experience and bullets come first; weak ones dropped |
