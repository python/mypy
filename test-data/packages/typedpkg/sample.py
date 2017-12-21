from typing import Iterable, List
def ex(a: Iterable[str]) -> List[str]:
    """Example typed package. This intentionally has an error."""
    return a + ['Hello']