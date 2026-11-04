"""Name every model call after the job that makes it, so a resumed run can find it.

A job (one stage run, or one judge grading one output) runs inside
``call_scope(key)``. Each call it makes gets ``<key>#<n>``, where ``n`` counts
its calls in order; calls within a job are sequential, so the same job makes
the same keys when it runs again. The batch layer derives request IDs from
these keys and the usage ledger attributes tokens to them.
"""

import hashlib
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class _Scope:
    key: str
    calls: int = 0


_CURRENT: ContextVar[_Scope | None] = ContextVar("evals_call_scope", default=None)


@contextmanager
def call_scope(key: str) -> Iterator[None]:
    """Run the calls made inside the block under ``key``."""
    token = _CURRENT.set(_Scope(key))
    try:
        yield
    finally:
        _CURRENT.reset(token)


def current_scope() -> str | None:
    """The key of the job making calls now, or None outside any job."""
    scope = _CURRENT.get()
    return scope.key if scope is not None else None


def next_call_key() -> str | None:
    """Return the next call's key in the current scope (None outside one)."""
    scope = _CURRENT.get()
    if scope is None:
        return None
    key = f"{scope.key}#{scope.calls}"
    scope.calls += 1
    return key


def request_id(call_key: str | None) -> str:
    """A provider-safe request ID (letters and digits): stable for a call key."""
    if call_key is None:
        return uuid.uuid4().hex
    return hashlib.sha256(call_key.encode("utf-8")).hexdigest()[:40]
