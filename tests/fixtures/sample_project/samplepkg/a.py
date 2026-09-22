"""Module A: intentionally imports module B to form a dependency cycle."""

from .b import beta


def alpha(value: int) -> int:
    """Return a value processed through the cycle."""
    return beta(value) + 1
