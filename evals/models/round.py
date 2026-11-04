"""The rounds of a tournament run."""

from typing import Literal

type Round = Literal["screening", "finals"]
"""Screening runs every model on a few cases; the finals run the survivors."""

ROUNDS: tuple[Round, ...] = ("screening", "finals")
