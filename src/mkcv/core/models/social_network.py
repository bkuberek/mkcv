"""Social network link model for resume contact section."""

from typing import Literal

from pydantic import BaseModel


class SocialNetwork(BaseModel):
    """A social network profile link."""

    network: Literal["LinkedIn", "GitHub", "Twitter", "Website"]
    username: str
