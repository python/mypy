# Stubs for argparse

# NOTE: These are incomplete!

from typing import Any, List

class Action(): pass
class Namespace(): pass

class ArgumentParser():

    def add_argument(
        *args: str,
        action: str = None,
        nargs: str = None,
        default: Any = None,
        type: Any = None,
        choices: List[Any] = None,
        required: bool = None,
        help: str = None,
        metavar: str = None,
        dest: str = None,
    ) -> None: pass

    # TODO this funciton returns a namespace
    def parse_args(args: List[str] = None, namespace: Any = None) -> Any: pass
