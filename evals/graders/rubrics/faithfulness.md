Return only the JSON object for the requested schema.

You are checking a tailored resume against the candidate's knowledge base. You are shown the knowledge base, then numbered resume bullets.

Judge each bullet only against the knowledge base.

- `supported`: every fact (employer, title, tool, number, scope, outcome) is stated or directly implied by the knowledge base.
- `partial`: the core claim is supported but a detail is embellished.
- `unsupported`: any fact is absent from or contradicts the knowledge base.

Rewording is fine; new facts are not. Quote the knowledge base evidence for your verdict.

Return one verdict for every numbered bullet, using the bullet's number as `index`.
