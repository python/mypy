from typing import Iterable, Tuple


def ex(a: Iterable[str]) -> Tuple[str, ...]:
    """Example typed package. This intentionally has an error."""
    return a + ('Hello')
