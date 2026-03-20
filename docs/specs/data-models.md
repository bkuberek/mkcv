# mkcv — Data Models Specification

**Version:** 0.3.0
**Date:** 2026-03-18

---

## Overview

All data flowing through the pipeline is typed with Pydantic v2 models. This ensures:
- AI outputs are validated before downstream use
- Invalid responses trigger retries with error feedback
- Intermediate artifacts are serializable to JSON/YAML
- Schema is documented and enforceable

---

## Stage 1 Output: JD Analysis

```python
from pydantic import BaseModel, Field
from typing import Literal

class Requirement(BaseModel):
    skill: str
    importance: Literal["must_have", "strong_prefer", "nice_to_have"]
    years_implied: int | None = None
    context: str = Field(description="How this skill is used in the role")

class JDAnalysis(BaseModel):
    company: str
    role_title: str
    seniority_level: Literal["junior", "mid", "senior", "staff", "principal"]
    team_or_org: str | None = None
    location: str | None = None
    compensation: str | None = None
    core_requirements: list[Requirement]
    technical_stack: list[str]
    soft_skills: list[str]
    leadership_signals: list[str]
    culture_keywords: list[str]
    ats_keywords: list[str] = Field(
        description="Exact phrases likely used as ATS keyword filters"
    )
    hidden_requirements: list[str] = Field(
        description="Requirements implied but not explicitly stated"
    )
    role_summary: str = Field(
        description="2-3 sentence synthesis of what they actually need"
    )
```

---

## Stage 2 Output: Experience Selection

```python
class SelectedExperience(BaseModel):
    company: str
    role: str
    period: str
    relevance_score: int = Field(ge=0, le=100)
    match_reasons: list[str]
    suggested_bullets: list[str] = Field(
        description="KB bullets to include for this role"
    )
    bullets_to_drop: list[str] = Field(
        description="KB bullets that aren't relevant to this JD"
    )
    reframe_suggestion: str = Field(
        description="How to angle this experience for the target role"
    )

class ExperienceSelection(BaseModel):
    selected_experiences: list[SelectedExperience]
    skills_to_highlight: list[str]
    skills_to_omit: list[str]
    gap_analysis: str = Field(
        description="What the candidate is missing vs the JD"
    )
    mission_themes: list[str] = Field(
        description="Themes to inform the mission statement"
    )
```

---

## Stage 3 Output: Tailored Content

```python
class TailoredBullet(BaseModel):
    original: str = Field(description="Source bullet from KB")
    rewritten: str = Field(
        description="Tailored version optimized for the target JD"
    )
    keywords_incorporated: list[str]
    confidence: Literal["high", "medium", "low"] = Field(
        description="high=faithful, medium=enhanced, low=stretched"
    )

class TailoredRole(BaseModel):
    company: str
    position: str
    location: str | None = None
    start_date: str
    end_date: str
    summary: str | None = Field(
        default=None,
        description="Optional 1-sentence role context"
    )
    bullets: list[TailoredBullet]
    tech_stack: str | None = Field(
        default=None,
        description="Tech line to display under the role"
    )

class MissionStatement(BaseModel):
    text: str = Field(max_length=500)
    rationale: str = Field(
        description="Why this mission statement works for this application"
    )

class SkillGroup(BaseModel):
    label: str  # e.g., "Languages", "Backend & APIs", "AI / LLM"
    skills: list[str]

class TailoredContent(BaseModel):
    mission: MissionStatement
    skills: list[SkillGroup]
    roles: list[TailoredRole]
    earlier_experience: str | None = Field(
        default=None,
        description="Condensed summary of older roles"
    )
    languages: list[str] | None = None
    low_confidence_flags: list[str] = Field(
        default_factory=list,
        description="Human-readable descriptions of items needing review"
    )
```

---

## Stage 4 Output: Resume YAML

Stage 4 produces a RenderCV-compatible YAML string. The YAML is validated against this model:

```python
class SocialNetwork(BaseModel):
    network: Literal["LinkedIn", "GitHub", "Twitter", "Website"]
    username: str

class ResumeBasics(BaseModel):
    name: str
    location: str
    email: str
    phone: str
    website: str | None = None
    social_networks: list[SocialNetwork] = []

class SkillEntry(BaseModel):
    label: str
    details: str

class ExperienceEntry(BaseModel):
    company: str
    position: str
    location: str | None = None
    start_date: str  # YYYY-MM or "present"
    end_date: str
    highlights: list[str] = Field(min_length=1, max_length=10)

class ResumeSection(BaseModel):
    """Flexible section that can hold different content types."""
    label: str
    details: str

class ResumeCV(BaseModel):
    name: str
    location: str
    email: str
    phone: str
    website: str | None = None
    social_networks: list[SocialNetwork] = []
    summary: str = Field(
        max_length=300,
        description="Mission statement rendered at top of resume"
    )
    sections: dict  # Flexible sections matching RenderCV schema

class ResumeDesign(BaseModel):
    theme: str = "sb2nov"
    font: str = "SourceSansPro"
    font_size: str = "10pt"
    page_size: str = "letterpaper"
    colors: dict[str, str] = {"primary": "003366"}

class RenderCVResume(BaseModel):
    """Top-level model matching RenderCV YAML schema."""
    cv: ResumeCV
    design: ResumeDesign
```

---

## Stage 5 Output: Review Report

```python
class BulletReview(BaseModel):
    bullet_text: str
    classification: Literal["faithful", "enhanced", "stretched", "fabricated"]
    explanation: str | None = None
    suggested_fix: str | None = None

class KeywordCoverage(BaseModel):
    total_keywords: int
    matched_keywords: int
    coverage_percent: float
    missing_keywords: list[str]
    suggestions: list[str]

class ATSCheck(BaseModel):
    single_column: bool
    no_tables: bool
    no_text_boxes: bool
    standard_headings: bool
    contact_in_body: bool
    standard_bullets: bool
    standard_fonts: bool
    text_extractable: bool
    reading_order_correct: bool
    overall_pass: bool
    issues: list[str]

class ReviewReport(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    bullet_reviews: list[BulletReview]
    keyword_coverage: KeywordCoverage
    ats_check: ATSCheck
    tone_consistency: str = Field(
        description="Assessment of voice consistency across the resume"
    )
    section_balance: str = Field(
        description="Assessment of space allocation across sections"
    )
    length_assessment: str = Field(
        description="Is the resume the right length?"
    )
    top_suggestions: list[str] = Field(
        max_length=5,
        description="The 3-5 most impactful improvements"
    )
    low_confidence_items: list[str] = Field(
        description="Items flagged for human review"
    )
```

---

## Pipeline Metadata

```python
class TokenUsage(BaseModel):
    """Token counts from a single LLM call."""
    input_tokens: int = 0
    output_tokens: int = 0

class StageMetadata(BaseModel):
    """Metadata about a single pipeline stage execution."""
    stage_number: int
    stage_name: str
    provider: str
    model: str
    temperature: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    duration_seconds: float
    retries: int = 0

class PipelineResult(BaseModel):
    """Complete result of a pipeline execution."""
    run_id: str
    timestamp: datetime
    jd_source: str
    kb_source: str
    company: str
    role_title: str
    stages: list[StageMetadata]
    total_cost_usd: float
    total_duration_seconds: float
    review_score: int
    output_paths: dict[str, str]  # {"resume_yaml": "path", ...}
```

---

## Stage Configuration

```python
class StageConfig(BaseModel):
    """Configuration for a single pipeline stage's LLM call."""
    provider: str    # e.g. "anthropic", "ollama"
    model: str       # e.g. "claude-sonnet-4-20250514"
    temperature: float  # 0.0–2.0

# Profile presets define per-stage configs for budget/premium modes
PROFILE_PRESETS: dict[str, dict[int, StageConfig]] = {
    "budget": {1: StageConfig(provider="ollama", ...), ...},
    "premium": {1: StageConfig(provider="anthropic", ...), ...},
}
```

---

## Pricing

```python
# MODEL_PRICING: dict of model → (input_cost_per_1k, output_cost_per_1k)
# Covers Claude, GPT-4o, GPT-4.1 variants. Returns 0.0 for unknown models.

def calculate_cost(model: str, usage: TokenUsage) -> float:
    """Calculate USD cost for a single LLM call."""
```

---

## Theme Info

```python
class ThemeInfo(BaseModel):
    """Metadata about an available resume theme."""
    name: str
    description: str
    font_family: str
    primary_color: str
    accent_color: str
    page_size: str
```

---

## KB Validation

```python
class KBValidationResult(BaseModel):
    """Result of validating a knowledge base Markdown file."""
    is_valid: bool
    warnings: list[str]
    errors: list[str]
    sections_found: list[str]
    sections_missing: list[str]
```

---

## Knowledge Base Format

The knowledge base is a Markdown file with expected sections. While not strictly validated (it's human-authored), the pipeline expects these sections:

```markdown
# [Name] — Knowledge Base

## Personal Information
(table with name, location, phone, email, website, LinkedIn, GitHub)

## Languages
(human languages with proficiency levels)

## Professional Summary
(2-3 paragraphs)

## Technical Skills — Master List
### Programming Languages
### Frontend
### Backend Frameworks
### AI / ML / LLM
### APIs & Protocols
### Databases & Data Stores
### Data & Pipeline
### Infrastructure & DevOps

## Career History — Complete and Detailed
### [Company] — [Title]
**[Date range]** | [Location]
- Bullet points with full detail
- Tech stack listed per role

## Key Achievements
## Strengths
## Passions & Interests
## About / Personal Narrative
```
