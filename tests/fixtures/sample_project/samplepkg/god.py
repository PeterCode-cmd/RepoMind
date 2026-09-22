"""Module with an intentionally god-like class used by RepoMind's test-suite."""


class TinyWorker:
    """Small, well-behaved class that must not be flagged."""

    def run(self) -> int:
        """Return a constant."""
        return 1


class GodClass:
    """Class with too many responsibilities (intentionally god-like)."""

    def __init__(self) -> None:
        """Initialize internal state."""
        self._state = 0
        self._log: list[str] = []

    def step_01(self) -> int:
        """Mutate internal state."""
        self._state += 1
        return self._state

    def step_02(self) -> int:
        """Mutate internal state."""
        self._state += 2
        return self._state

    def step_03(self) -> int:
        """Mutate internal state."""
        self._state += 3
        return self._state

    def step_04(self) -> int:
        """Mutate internal state."""
        self._state += 4
        return self._state

    def step_05(self) -> int:
        """Mutate internal state."""
        self._state += 5
        return self._state

    def step_06(self) -> int:
        """Mutate internal state."""
        self._state += 6
        return self._state

    def step_07(self) -> int:
        """Mutate internal state."""
        self._state += 7
        return self._state

    def step_08(self) -> int:
        """Mutate internal state."""
        self._state += 8
        return self._state

    def step_09(self) -> int:
        """Mutate internal state."""
        self._state += 9
        return self._state

    def step_10(self) -> int:
        """Mutate internal state."""
        self._state += 10
        return self._state

    def step_11(self) -> int:
        """Mutate internal state."""
        self._state += 11
        return self._state

    def step_12(self) -> int:
        """Mutate internal state."""
        self._state += 12
        return self._state

    def step_13(self) -> int:
        """Mutate internal state."""
        self._state += 13
        return self._state

    def step_14(self) -> int:
        """Mutate internal state."""
        self._state += 14
        return self._state

    def step_15(self) -> int:
        """Mutate internal state."""
        self._state += 15
        return self._state

    def step_16(self) -> int:
        """Mutate internal state."""
        self._state += 16
        return self._state
