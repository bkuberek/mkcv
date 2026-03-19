# mkcv — Product Requirements Document

**Version:** 0.2.0<br>
**Date:** 2026-03-18<br>
**Status:** Active<br>

---

## Vision

mkcv is a tool that makes creating a perfect, job-tailored resume as easy as running a command. It combines a comprehensive career knowledge base with AI-powered content optimization and a battle-tested rendering pipeline to produce resumes that are both visually stunning and machine-readable.

## Problem Statement

Creating a tailored resume for each job application is time-consuming and error-prone:

1. **Repetitive work:** Engineers re-edit the same resume for every application, manually adjusting bullets and emphasis.
2. **ATS black hole:** Beautiful resumes with columns, graphics, and creative layouts fail to parse in Applicant Tracking Systems, making candidates invisible to recruiters.
3. **Inconsistent quality:** Without structured feedback, it's easy to use weak verbs, miss keywords, or over/under-represent experience.
4. **No single source of truth:** Career details are scattered across old resumes, LinkedIn, notes — making it hard to pull the right details for each application.

## Target Users

**Primary (Phase 1):** The tool's creator — a senior software engineer actively job searching, comfortable with CLI tools and AI APIs.

**Secondary (Phase 2-4):** Technical professionals who want AI-assisted resume generation but prefer a web interface; eventually non-technical professionals via mobile app.

## Core User Flow (Phase 1: CLI)

```
1. User maintains a Knowledge Base (Markdown file with complete career history)
2. User finds a job posting and saves the JD as a text file
3. User runs: mkcv generate --jd deepl.txt --kb career.md
4. mkcv runs the 5-stage AI pipeline:
   a. Analyzes the JD (extracts requirements, keywords, seniority)
   b. Selects relevant experience from the KB
   c. Tailors bullets and writes a mission statement
   d. Structures content into RenderCV YAML
   e. Reviews for ATS compliance and quality
5. User reviews the output (YAML + review report)
6. User optionally edits the YAML or runs interactive refinement
7. User runs: mkcv render resume.yaml
8. mkcv produces: resume.pdf + resume.png + resume.md
9. User submits the PDF
```

## Functional Requirements

### FR-1: Knowledge Base Management

| ID | Requirement | Priority |
|----|------------|----------|
| FR-1.1 | Accept a Markdown file as the career knowledge base | Must |
| FR-1.2 | Validate KB structure (warn on missing sections, dates, etc.) | Should |
| FR-1.3 | Support multiple KB files (personal info separate from experience) | Could |

### FR-2: Job Description Analysis

| ID | Requirement | Priority |
|----|------------|----------|
| FR-2.1 | Accept JD as plain text file, URL, or stdin | Must |
| FR-2.2 | Extract structured requirements: skills, seniority, keywords, culture signals | Must |
| FR-2.3 | Identify hidden/implicit requirements | Should |
| FR-2.4 | Produce a reusable `jd_analysis.json` artifact | Must |

### FR-3: AI Pipeline

| ID | Requirement | Priority |
|----|------------|----------|
| FR-3.1 | Run 5-stage pipeline (analyze → select → tailor → structure → review) | Must |
| FR-3.2 | Each stage produces a persisted intermediate artifact (JSON/YAML) | Must |
| FR-3.3 | Support resuming from any stage (skip already-completed stages) | Should |
| FR-3.4 | Support configurable AI provider per stage | Must |
| FR-3.5 | Anti-embellishment: confidence scoring on every generated bullet | Must |
| FR-3.6 | Voice consistency across all generated content | Must |
| FR-3.7 | ATS keyword coverage scoring (target ≥75% match) | Must |

### FR-4: Content Generation

| ID | Requirement | Priority |
|----|------------|----------|
| FR-4.1 | Generate a tailored mission statement (15-30 words) | Must |
| FR-4.2 | Generate impact-driven bullets using XYZ formula | Must |
| FR-4.3 | Never fabricate metrics — only use data from KB | Must |
| FR-4.4 | Weave ATS keywords naturally into bullets | Must |
| FR-4.5 | Select and order skills by relevance to JD | Must |
| FR-4.6 | Condense old/irrelevant roles appropriately | Should |

### FR-5: Rendering

| ID | Requirement | Priority |
|----|------------|----------|
| FR-5.1 | Render to PDF via RenderCV (Typst engine) | Must |
| FR-5.2 | Render to PNG (for LinkedIn/social preview) | Should |
| FR-5.3 | Render to Markdown (for text-based review) | Should |
| FR-5.4 | Support multiple themes (sb2nov, classic, moderncv, custom) | Must |
| FR-5.5 | Support custom colors, fonts, margins via config | Should |
| FR-5.6 | WeasyPrint as secondary renderer for custom HTML/CSS designs | Could |

### FR-6: Quality Assurance

| ID | Requirement | Priority |
|----|------------|----------|
| FR-6.1 | Generate a review report with scores and actionable suggestions | Must |
| FR-6.2 | ATS compliance checklist (auto-verified) | Must |
| FR-6.3 | Copy-paste test: verify all text is extractable from PDF | Should |
| FR-6.4 | Flag low-confidence bullets for human review | Must |
| FR-6.5 | Compare generated resume against source KB for accuracy | Should |

### FR-7: Configuration

| ID | Requirement | Priority |
|----|------------|----------|
| FR-7.1 | TOML config file for defaults (models, theme, voice guidelines) via Dynaconf | Must |
| FR-7.2 | Environment variables for API keys | Must |
| FR-7.3 | CLI flags override config file | Must |
| FR-7.4 | Support provider profiles (e.g., "budget" uses Ollama, "premium" uses Claude) | Should |

## Non-Functional Requirements

| ID | Requirement | Target |
|----|------------|--------|
| NFR-1 | End-to-end pipeline execution time | < 60 seconds |
| NFR-2 | Cost per tailored resume (premium mode) | < $0.50 |
| NFR-3 | Cost per tailored resume (budget mode) | < $0.15 |
| NFR-4 | PDF render time | < 5 seconds |
| NFR-5 | Works offline for rendering (given a completed YAML) | Yes |
| NFR-6 | No data sent to cloud without user consent | Yes |
| NFR-7 | All intermediate artifacts human-readable | Yes |

## Out of Scope (Phase 1)

- Web UI / web service
- User accounts / multi-user support
- Cover letter generation (future feature)
- Resume hosting / sharing
- Integration with job boards (LinkedIn, Indeed)
- Automatic job description scraping from URLs
- A/B testing of resume variants

## Success Metrics

1. **Time to tailored resume:** < 5 minutes from JD to submitted PDF
2. **ATS parse rate:** 100% of generated resumes pass the copy-paste test
3. **Keyword coverage:** ≥ 75% of JD keywords present in resume
4. **User satisfaction:** Creator feels confident submitting every generated resume
5. **Accuracy:** Zero fabricated metrics or achievements in any generated resume

## Glossary

| Term | Definition |
|------|-----------|
| **Knowledge Base (KB)** | A comprehensive Markdown document containing all career history, skills, achievements, and personal details. Single source of truth. |
| **JD** | Job Description — the posting text for a specific role. |
| **ATS** | Applicant Tracking System — software used by companies to manage hiring pipelines. Parses resumes into structured data. |
| **Mission Statement** | A 1-2 sentence forward-looking declaration of professional purpose, placed at the top of the resume. |
| **XYZ Formula** | Resume bullet structure: "Accomplished [X] as measured by [Y], by doing [Z]" |
| **RenderCV** | Open-source tool that renders YAML → PDF via the Typst typesetting engine. |
| **Confidence Score** | Per-bullet rating (high/medium/low) indicating how faithfully the bullet represents source material. |
