from contextlib import contextmanager
from typing import Optional, Tuple, Iterator
STRICT_OPTIONAL = False
find_occurrences = None  # type: Optional[Tuple[str, str]]


@contextmanager
def strict_optional_set(value: bool) -> Iterator[None]:
    global STRICT_OPTIONAL
    saved = STRICT_OPTIONAL
    STRICT_OPTIONAL = value
    yield
    STRICT_OPTIONAL = saved
