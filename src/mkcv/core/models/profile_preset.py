"""Profile preset model for provider/model selection."""

from mkcv.core.models.stage_config import StageConfig

BUDGET_STAGE_CONFIGS: dict[int, StageConfig] = {
    1: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.2),
    2: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.3),
    3: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.5),
    4: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.1),
    5: StageConfig(provider="ollama", model="llama3.1:8b", temperature=0.3),
}

PREMIUM_STAGE_CONFIGS: dict[int, StageConfig] = {
    1: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.2
    ),
    2: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.3
    ),
    3: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.5
    ),
    4: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.1
    ),
    5: StageConfig(
        provider="anthropic", model="claude-sonnet-4-20250514", temperature=0.3
    ),
}

PROFILE_PRESETS: dict[str, dict[int, StageConfig]] = {
    "budget": BUDGET_STAGE_CONFIGS,
    "premium": PREMIUM_STAGE_CONFIGS,
}

VALID_PROFILES: frozenset[str] = frozenset({"default", "budget", "premium"})
