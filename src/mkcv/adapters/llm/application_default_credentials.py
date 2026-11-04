"""Local checks of Google credentials for Vertex AI.

Credentials come from a pinned file (``credentials_file``) or from Application
Default Credentials (ADC): the environment, the gcloud login file, or the
metadata server. No API call is made. ``google.auth`` is imported on use so it
costs nothing for providers that never touch Google Cloud.
"""

from pathlib import Path
from typing import Any

from mkcv.core.exceptions.configuration import ConfigurationError

LOGIN_COMMAND = "gcloud auth application-default login"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def has_vertex_credentials(credentials_file: str | None = None) -> bool:
    """Return True if the pinned file loads, or else ADC can be found."""
    try:
        if credentials_file:
            credentials_from_file(credentials_file)
        else:
            application_default_project()
    except ConfigurationError:
        return False
    return True


def credentials_from_file(credentials_file: str) -> tuple[Any, str | None]:
    """Load a credentials file, expanding ``~``; return ``(credentials, project)``.

    Raises:
        ConfigurationError: If the file is missing or unreadable.
    """
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    path = str(Path(credentials_file).expanduser())
    try:
        credentials, project = google.auth.load_credentials_from_file(  # type: ignore[no-untyped-call]
            path, scopes=[CLOUD_PLATFORM_SCOPE]
        )
    except (OSError, DefaultCredentialsError) as error:
        raise ConfigurationError(
            f"Cannot read credentials_file '{path}' for provider 'google' "
            f"({error}). Check the path in [default.providers.google], or create "
            f"the file with '{LOGIN_COMMAND}'."
        ) from error
    return credentials, project or None


def application_default_project() -> str | None:
    """Return the project ADC reports, or None if it reports none.

    Raises:
        ConfigurationError: If no Application Default Credentials are found.
    """
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    try:
        _credentials, project = google.auth.default()
    except DefaultCredentialsError as error:
        raise ConfigurationError(
            "Vertex AI mode for provider 'google' found no Application Default "
            f"Credentials ({error}). Run '{LOGIN_COMMAND}', and set project in "
            "[default.providers.google] or GOOGLE_CLOUD_PROJECT."
        ) from error
    return project or None
