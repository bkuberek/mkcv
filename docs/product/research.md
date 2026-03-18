# mkcv — Research Findings

**Date:** 2026-03-18
**Source:** Full research document at `../../resume/pipeline/Resume Pipeline Research.md`

---

## 1. ATS (Applicant Tracking Systems) — How Hiring Works

### Key Insight

ATS does NOT "reject" resumes. It fails to *index* them. A poorly parsed resume is stored but invisible to keyword searches — the candidate is in the database but no recruiter will ever find them.

### Market Share (2025-2026)

**Fortune 500:** Workday (39%), SuccessFactors (13%), Taleo (8%), iCIMS (7%)
**Tech/Startups:** Greenhouse (19%), Lever (17%), Workday (16%), iCIMS (15%), Ashby (growing)

### What Recruiters Filter By

| Filter | Usage |
|--------|-------|
| Skills | 76% |
| Education | 60% |
| Job titles | 55% |
| Certifications | 51% |
| Years of experience | 44% |
| Location | 43% |

### What Breaks ATS Parsing

**Critical failures:** Multi-column layouts, tables, text boxes, headers/footers
**High risk:** Images, icon fonts (Font Awesome), graphics, charts
**Medium risk:** Fancy bullet characters, decorative fonts

**Proven failure:** Lever was demonstrated dropping an entire sidebar column — skills, contact info, links all vanished. Only the main column survived.

### What's Safe

Bold, italic, uppercase headings, one accent color for headings, thin horizontal rules, standard bullets (solid circle), whitespace, font size variation.

### The Design Philosophy

"Beautiful" ATS-compliant resumes achieve design through **typography, whitespace, and restraint** — not graphics. Single column, one accent color, generous margins, clean hierarchy.

---

## 2. PDF Generation Tools — Evaluation

### Winner: RenderCV (YAML → Typst → PDF)

| Criteria | Score |
|----------|-------|
| Visual design | 8/10 |
| ATS compliance | 9/10 |
| AI integration (YAML input) | 10/10 |
| Repeatability | 10/10 |
| Self-hostable | Yes |
| **Total** | **37/40** |

- 16k GitHub stars, active development
- Migrated from LaTeX to Typst (modern, fast, single binary)
- YAML input with JSON Schema validation
- 5 built-in themes + custom theme support
- Single command: `rendercv render resume.yaml`

### Runner-up: WeasyPrint (HTML/CSS → PDF)

Scored 34/40. Best for pixel-perfect custom designs when you need full CSS control. 14 years of production use. Pure Python. Excellent text extraction quality.

### Rejected Approaches

- **LaTeX:** LLMs struggle with syntax (escaping), slow compilation, massive dependencies. Score: 28/40.
- **Puppeteer/Gotenberg:** Chromium dependency for marginal benefit. Score: 32/40.
- **Reactive Resume:** Full SaaS app, too heavy for a CLI pipeline. Score: 29/40.
- **Markdown → PDF:** Not expressive enough. Score: 29/40.

---

## 3. AI Pipeline — Model Selection

### Recommended Models Per Stage

| Stage | Model | Why | Cost |
|-------|-------|-----|------|
| 1. Analyze JD | Claude Sonnet 4 | Best structured extraction | ~$0.02 |
| 2. Select experience | Claude Sonnet 4 | 200K context for full KB | ~$0.10 |
| 3. Tailor bullets | Claude Sonnet 4 | Natural prose, no AI-speak | ~$0.15 |
| 4. Structure YAML | GPT-4o | Strict schema enforcement | ~$0.04 |
| 5. Review | Claude Sonnet 4 | Conservative critic | ~$0.07 |
| **Total** | | | **~$0.38** |

### Local Model (Ollama) Viability

| Task | Viability | Model |
|------|-----------|-------|
| JD keyword extraction | High | Qwen 2.5 7B-32B |
| Draft bullets | Medium | Llama 3.1 8B |
| YAML formatting | Medium | Qwen 2.5 Coder 14B-32B |
| Privacy-sensitive KB | High | Llama 3.1 70B |
| Final polish | Low | Use cloud |

### Temperature Settings

Analytical stages (1, 2, 4, 5): 0.1-0.3
Creative stages (3): 0.5-0.6

---

## 4. Resume Writing Best Practices

### Structure (2025-2026 Consensus)

1. Header (name, contact, links)
2. Mission statement (1-2 sentences, forward-looking)
3. Skills (grouped by category, above experience)
4. Work Experience (reverse chronological)
5. Earlier Experience (condensed)
6. Education (optional at 10+ years)
7. Languages / Certifications (optional)

### Bullet Writing

**XYZ Formula:** "Accomplished [X] as measured by [Y], by doing [Z]"

**Good verbs:** Architected, Delivered, Led, Drove, Established, Pioneered
**Bad verbs:** Helped, Assisted, Participated, Responsible for

**Every bullet should have a number:** team size, user count, %, time saved, revenue, documents processed.

### Length

- < 10 years: 1 page
- 10+ years: 2 pages acceptable
- Never exceed 2 pages
- Page 1 must be self-sufficient (assume some reviewers only read page 1)

### Staff+ Level Signals

Four pillars: Technical Leadership, Cross-team Influence, Mentorship, Strategic/Business Impact.

Show scope ("across 5 teams"), decision authority ("defined technical strategy"), ambiguity navigation, and multiplier effect.

---

## 5. Mission Statement Research

### Definition

A 1-2 sentence declaration of professional purpose. Forward-looking (what you want to do), not backward-looking (what you've done). 15-30 words.

### How It Differs from Professional Summary

| Mission Statement | Professional Summary |
|-------------------|---------------------|
| Forward-looking | Backward-looking |
| 15-30 words | 50-100 words |
| Philosophy/impact | Skills/experience |
| Subtly signals role alignment | Explicitly states qualifications |

### Examples

> "Designing systems where operational simplicity enables product velocity — building platforms that make the right thing the easy thing."

> "Shipping products at the intersection of AI and infrastructure, where production quality and user outcomes matter more than hype."

---

## 6. Anti-Embellishment Strategy

1. **Prompts:** Explicitly forbid fabricating metrics; require source attribution
2. **Confidence scoring:** Every bullet rated high/medium/low; low = stretched beyond source
3. **Review stage:** Classifies bullets as FAITHFUL / ENHANCED / STRETCHED / FABRICATED
4. **Human-in-the-loop:** Low-confidence items flagged for manual review
5. **Audit trail:** Original KB bullets preserved alongside rewrites for comparison
