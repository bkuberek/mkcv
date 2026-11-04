"""The one commented config template behind both settings files.

mkcv reads settings from the user file (``~/.config/mkcv/settings.toml``) and
from a workspace ``mkcv.toml``, and any option can live in either. Both files
are rendered from the sections below, so they document the same options and
cannot drift. Provider names, key variables, and model profiles come from the
registries. The scopes differ in their header, the live settings of the
workspace file, and whether ``api_key`` placeholders are active.
"""

import textwrap
from collections.abc import Callable

from mkcv.adapters.filesystem.config_scope import ConfigScope
from mkcv.adapters.llm.builtin_providers import BUILTIN_PROVIDERS
from mkcv.adapters.llm.provider_spec import ProviderSpec
from mkcv.config.user_config_path import USER_CONFIG_DISPLAY_PATH
from mkcv.core.catalog.builtin_model_profiles import (
    BUILTIN_MODEL_PROFILES,
    get_profile,
    profile_stage_model,
)
from mkcv.core.models.model_profile import ModelProfile
from mkcv.core.models.profile_preset import BUILT_IN_PRESETS
from mkcv.core.models.stage_key import PIPELINE_STAGES, StageKey

_MODELS_GUIDE = "https://github.com/bkuberek/mkcv/blob/main/docs/models.md"
_RULE_WIDTH = 68
_PROSE_WIDTH = 74
_DEFAULT_PROFILE = "anthropic"

_KEY_PROVIDER_LABELS = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google Gemini",
    "openrouter": "OpenRouter (one key for Claude, GPT, Gemini and more)",
}

_STAGE_TEMPERATURES = {
    StageKey.ANALYZE: 0.2,
    StageKey.SELECT: 0.3,
    StageKey.TAILOR: 0.5,
    StageKey.STRUCTURE: 0.1,
    StageKey.REVIEW: 0.3,
}
_COVER_LETTER_STAGES = (
    (StageKey.COVER_LETTER_GENERATE, "generate", 0.6),
    (StageKey.COVER_LETTER_REVIEW, "review", 0.2),
)

_WORKSPACE_KEY_WARNING = (
    "WARNING: keys here are read only for this workspace; if this directory "
    "is a git repo, keep keys in ~/.config/mkcv/settings.toml instead or make "
    "sure mkcv.toml is not committed."
)


def render_config_template(scope: ConfigScope, *, version: str | None = None) -> str:
    """Render the commented settings file for ``scope``.

    Args:
        scope: Which file the text is for.
        version: mkcv version recorded in the workspace file.

    Returns:
        Valid TOML. The user file holds only empty ``api_key`` placeholders;
        the workspace file holds its workspace settings. Everything else is
        commented out.
    """
    header = _user_header() if scope is ConfigScope.USER else _workspace_header()
    live = [] if scope is ConfigScope.USER else _workspace_settings(version)
    sections = [_SECTIONS[name](scope) for name in _SECTION_ORDER[scope]]
    blocks = [header, *([live] if live else []), *sections]
    return "\n\n".join("\n".join(block) for block in blocks) + "\n"


# ---------------------------------------------------------------------------
# Headers and workspace settings
# ---------------------------------------------------------------------------


def _user_header() -> list[str]:
    return [
        f"# mkcv user configuration: {USER_CONFIG_DISPLAY_PATH}",
        f"# Docs: {_MODELS_GUIDE}#api-keys",
        "#",
        "# mkcv created this file on first run. It applies to every workspace on",
        "# this machine and lives outside every repository, so it is the place for",
        "# your API keys. Any option below can also go in a workspace mkcv.toml,",
        "# which overrides this file for that workspace.",
        "#",
        "# Layers, later ones override earlier ones:",
        "#   built-in defaults < this file < workspace mkcv.toml"
        " < environment variables < command-line flags",
        "#",
        "# Keep this file private (chmod 600).",
        "# Never put keys in a committed mkcv.toml.",
        "#",
        "# Section headers need the default. prefix, as in default.pipeline;",
        "# without it the setting is ignored.",
        "# Everything except the empty api_key placeholders is commented out;",
        "# uncomment what you want to change. Values shown are the defaults.",
    ]


def _workspace_header() -> list[str]:
    return [
        "# mkcv workspace configuration",
        "# Docs: https://github.com/bkuberek/mkcv",
        "#",
        "# All settings are optional: sensible defaults are built in.",
        "# Uncomment sections below to customise. Values shown are the defaults.",
        "#",
        f"# Any option below can also go in the user file {USER_CONFIG_DISPLAY_PATH},",
        "# which applies to every workspace. This file overrides it.",
        "#",
        "# Layers, later ones override earlier ones:",
        f"#   built-in defaults < {USER_CONFIG_DISPLAY_PATH} < this file"
        " < environment variables < command-line flags",
        "#",
        "# All section headers use the [default.] prefix because mkcv uses",
        "# Dynaconf environments. This prefix is required for settings to",
        "# take effect.",
    ]


def _workspace_settings(version: str | None) -> list[str]:
    return [
        "[default.workspace]",
        f'version = "{version or "0.0.0"}"',
        "",
        "[default.paths]",
        'knowledge_base_dir = "knowledge-base"',
        'applications_dir = "applications"',
        'templates_dir = "templates"',
        "",
        "[default.naming]",
        "company_slug = true",
        'application_pattern = "{company}/{position}/{date}"',
        "",
        "[default.defaults]",
        'theme = "sb2nov"',
        'profile = "standard"',
    ]


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def _prose(text: str, width: int = _PROSE_WIDTH) -> list[str]:
    return [f"# {line}" for line in textwrap.wrap(text, width=width)]


def _title(name: str) -> list[str]:
    return [f"# ── {name} ".ljust(_RULE_WIDTH, "─")]


def _commented(lines: list[str]) -> list[str]:
    return [f"# {line}" if line else "#" for line in lines]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

_RENDERING_BLOCK = """\
# Theme controls the visual design of your resume PDF. Run
# `mkcv themes` to list themes, `mkcv themes --preview <name>`
# to preview one.
#
# [default.rendering]
# theme = "sb2nov"           # classic, engineeringresumes, moderncv, ...
# font = "SourceSansPro"     # any system font
# font_size = "10pt"
# page_size = "letterpaper"  # letterpaper or a4paper
#
# [default.rendering.overrides]
# primary_color = "003366"   # hex colour without #
#
# Page margins: override RenderCV theme defaults
# [default.rendering.page]
# top_margin = "0.7in"
# bottom_margin = "0.7in"
# left_margin = "0.5in"
# right_margin = "0.5in"
#
# Header spacing below name/headline/connections
# [default.rendering.header]
# space_below_name = "0.15cm"
# space_below_headline = "0.15cm"
# space_below_connections = "0.3cm"
#
# Experience section geometry
# [default.rendering.entries]
# date_and_location_width = "3.6cm"
#
# Section heading style
# [default.rendering.section_titles]
# type = "with_full_line"
# space_above = "0.3cm"
# space_below = "0.15cm"
#
# Line spacing and text alignment
# [default.rendering.typography]
# line_spacing = "0.7em"
# alignment = "justified"
"""


def _providers(scope: ConfigScope) -> list[str]:
    live = scope is ConfigScope.USER
    lines = _title("Providers")
    if live:
        lines += _prose(
            "API keys. Fill in the key of each provider you use and leave the "
            "others empty. An empty key counts as not set, so mkcv falls back "
            "to the provider's environment variable, named in the comment "
            "above each section. A key here wins over that variable."
        )
    else:
        lines += _prose(_WORKSPACE_KEY_WARNING)
        lines += _prose(
            "Use the same table names in the user file. A key in config wins "
            "over the provider's environment variable, named in the comment "
            "above each section."
        )
    for name, spec in BUILTIN_PROVIDERS.items():
        if spec.api_key_env:
            lines += ["#", *_key_provider(name, spec, live=live)]
    lines += ["#", *_ollama()]
    lines += ["#", *_custom_provider()]
    return lines


def _key_provider(name: str, spec: ProviderSpec, *, live: bool) -> list[str]:
    variables = " or ".join(spec.api_key_env)
    lines = [f"# {_KEY_PROVIDER_LABELS.get(name, name)}. Or set {variables}."]
    body = [f"[default.providers.{name}]", 'api_key = ""']
    lines += body if live else _commented(body)
    if name == "google":
        lines += _vertex_options()
    return lines


def _vertex_options() -> list[str]:
    return [
        "# No API key? Call Gemini on Vertex AI with Application Default",
        "# Credentials instead (run: gcloud auth application-default login).",
        "# Vertex mode wins over an API key.",
        "# vertexai = true",
        "# Google Cloud project (default: the one ADC or gcloud reports).",
        '# project = "my-gcp-project"',
        "# Vertex AI location.",
        '# location = "global"',
        "# Pin one ADC file, for example one per Google account.",
        "# credentials_file = "
        '"~/.config/gcloud-mkcv/application_default_credentials.json"',
    ]


def _ollama() -> list[str]:
    spec = BUILTIN_PROVIDERS["ollama"]
    return [
        "# Ollama runs locally and needs no key. Set base_url only if it listens",
        "# somewhere else.",
        *_commented(
            [
                "[default.providers.ollama]",
                f'base_url = "{spec.base_url}"',
            ]
        ),
    ]


def _custom_provider() -> list[str]:
    return [
        "# Any OpenAI-compatible endpoint (Groq, Together, vLLM, LM Studio, ...) is",
        "# a provider too. Name it, then use it in a stage or with --provider.",
        *_commented(
            [
                "[default.providers.groq]",
                'type = "openai-compatible"',
                'base_url = "https://api.groq.com/openai/v1"',
                'api_key_env = "GROQ_API_KEY"',
            ]
        ),
    ]


def _rendering() -> list[str]:
    return [*_title("Rendering"), *_RENDERING_BLOCK.splitlines()]


def _default_profile() -> ModelProfile:
    return get_profile(_DEFAULT_PROFILE) or next(iter(BUILTIN_MODEL_PROFILES.values()))


def _pipeline() -> list[str]:
    profile = _default_profile()
    profile_names = ", ".join(BUILTIN_MODEL_PROFILES)
    presets = ", ".join(BUILT_IN_PRESETS)
    lines = [
        *_title("Pipeline"),
        *_prose(
            "Which models run each stage comes from a model profile. The default "
            f'is the "{profile.name}" profile. {profile.description} Run '
            "`mkcv models` to see what every stage will use, and "
            "`mkcv models --profiles` to list the profiles. All profiles are "
            "provisional: they are not yet backed by an eval run."
        ),
        "#",
        *_prose(f"Profiles: {profile_names}."),
        *_prose(
            f"Resume density is not a config key: pass --preset ({presets}) "
            "on the command line."
        ),
        "#",
        "# [default.pipeline]",
        f'# model_profile = "{profile.name}"',
        f'# provider = "{profile.provider}"  # used when model_profile is not set',
        "# model_warnings = true  # warn about weak or unknown models",
        "#",
        *_prose(
            "Per-stage settings below beat the profile; --model-profile and "
            "--provider on the command line beat both. A stage that sets only "
            "`model` runs on the provider mkcv finds that model under."
        ),
    ]
    for stage in PIPELINE_STAGES:
        lines += [
            "#",
            *_commented(
                [
                    f"[default.pipeline.stages.{stage.value}]",
                    f'provider = "{profile.provider}"',
                    f'model = "{profile_stage_model(profile, stage)}"',
                    f"temperature = {_STAGE_TEMPERATURES[stage]}",
                ]
            ),
        ]
    return lines


def _cover_letter() -> list[str]:
    profile = _default_profile()
    lines = [
        *_title("Cover Letter"),
        "# Settings for cover letter generation (used with --cover-letter).",
        "#",
        "# [default.cover_letter]",
        "# auto_render = true",
    ]
    for stage, name, temperature in _COVER_LETTER_STAGES:
        lines += [
            "#",
            *_commented(
                [
                    f"[default.cover_letter.stages.{name}]",
                    f'provider = "{profile.provider}"',
                    f'model = "{profile_stage_model(profile, stage)}"',
                    f"temperature = {temperature}",
                ]
            ),
        ]
    lines += [
        "#",
        "# Cover letter page layout",
        *_commented(
            [
                "[default.cover_letter.design]",
                'page_size = "us-letter"',
                'margin_top = "1.2in"',
                'margin_bottom = "1in"',
                'margin_left = "1in"',
                'margin_right = "1in"',
                'font = "Source Sans Pro"',
                'font_size = "11pt"',
                'name_size = "16pt"',
                'line_spacing = "0.7em"',
                'default_salutation = "Dear Hiring Manager,"',
            ]
        ),
    ]
    return lines


def _voice() -> list[str]:
    return [
        *_title("Voice"),
        "# Writing-style guidelines applied during content generation.",
        "# For detailed control, edit knowledge-base/voice.md instead.",
        "#",
        "# [default.voice]",
        '# guidelines = ""',
    ]


def _model_catalog() -> list[str]:
    return [
        *_title("Model catalog"),
        *_prose(
            "Tell mkcv about a model it does not know: its quality tier, prices "
            "(USD per 1M tokens), and how it returns structured output. Unknown "
            "models still run, with conservative defaults and a warning."
        ),
        "#",
        "# [[default.model_catalog]]",
        '# provider = "groq"',
        '# match = "llama-3.3-70b-versatile"',
        '# tier = "efficient"  # minimal, efficient, strong, frontier',
        '# structured_output = "json_object"  # json_schema, tool, json_object, prompt',
        "# input_price_per_mtok = 0.59",
        "# output_price_per_mtok = 0.79",
    ]


_SECTIONS: dict[str, Callable[[ConfigScope], list[str]]] = {
    "providers": _providers,
    "rendering": lambda _scope: _rendering(),
    "pipeline": lambda _scope: _pipeline(),
    "cover_letter": lambda _scope: _cover_letter(),
    "voice": lambda _scope: _voice(),
    "model_catalog": lambda _scope: _model_catalog(),
}


_SECTION_ORDER: dict[ConfigScope, tuple[str, ...]] = {
    ConfigScope.USER: (
        "providers",
        "pipeline",
        "rendering",
        "cover_letter",
        "voice",
        "model_catalog",
    ),
    ConfigScope.WORKSPACE: (
        "rendering",
        "pipeline",
        "cover_letter",
        "voice",
        "providers",
        "model_catalog",
    ),
}
