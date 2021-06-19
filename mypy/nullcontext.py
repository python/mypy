import sys
from contextlib import contextmanager
from typing import Iterator

if sys.version_info < (3, 7):
    @contextmanager
    def nullcontext() -> Iterator[None]:
        yield
else:
    from contextlib import nullcontext as nullcontext, contextmanager  # noqa: F401
