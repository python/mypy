"""Stuff that we had to move out of its right place because of mypyc limitations."""

from typing import Dict, Any
import sys


# Extracted from build.py because we can't handle *args righit
class BuildManagerBase:
    def __init__(self) -> None:
        self.stats = {}  # type: Dict[str, Any]  # Values are ints or floats

    def verbosity(self) -> int:
        return self.options.verbosity  # type: ignore

    def log(self, *message: str) -> None:
        if self.verbosity() >= 1:
            if message:
                print('LOG: ', *message, file=sys.stderr)
            else:
                print(file=sys.stderr)
            sys.stderr.flush()

    def log_fine_grained(self, *message: str) -> None:
        import mypy.build
        if self.verbosity() >= 1:
            self.log('fine-grained:', *message)
        elif mypy.build.DEBUG_FINE_GRAINED:
            # Output log in a simplified format that is quick to browse.
            if message:
                print(*message, file=sys.stderr)
            else:
                print(file=sys.stderr)
            sys.stderr.flush()

    def trace(self, *message: str) -> None:
        if self.verbosity() >= 2:
            print('TRACE:', *message, file=sys.stderr)
            sys.stderr.flush()

    def add_stats(self, **kwds: Any) -> None:
        for key, value in kwds.items():
            if key in self.stats:
                self.stats[key] += value
            else:
                self.stats[key] = value
