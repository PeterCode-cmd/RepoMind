"""Module with intentionally complex functions used by RepoMind's test-suite."""


def tangled_branches(value: int, a: int) -> int:
    """Compute a value using deeply nested branching (intentionally complex)."""
    result = 0
    if value > 0:
        if a > 0:
            if value > a:
                if value % 2 == 0:
                    if a % 2 == 0:
                        result = value + a
                    else:
                        result = value - a
                else:
                    result = value * a
            else:
                for index in range(a):
                    if index % 2 == 0:
                        result += index
                    else:
                        result -= index
        elif a == 0:
            while result < value:
                result += 2
                if result > 100:
                    break
        else:
            try:
                result = value // a
            except ZeroDivisionError:
                result = 0
    elif value < -10:
        result = -value
    else:
        result = 1
    return result


def too_many_parameters(
    alpha: int,
    beta: int,
    gamma: int,
    delta: int,
    epsilon: int,
    zeta: int,
) -> int:
    """Accept more parameters than the configured threshold."""
    return alpha + beta + gamma + delta + epsilon + zeta


def long_function() -> int:
    """Grow well beyond the configured function length threshold."""
    total = 0
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    total += 1
    return total
