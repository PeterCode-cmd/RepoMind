"""Module B: intentionally imports module A to form a dependency cycle."""

from .a import alpha


def beta(value: int) -> int:
    """Return a value processed through the cycle."""
    if value > 100:
        return alpha(value - 1) + 1
    return max(value, 0)
