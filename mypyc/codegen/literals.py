from typing import Dict, Type, Optional


class Literals:
    """Collection of literal values used in a compilation group."""

    def __init__(self) -> None:
        self.literals = {}  # type: Dict[Type[object], Dict[str, int]]

    def record_literal(self, value: str) -> None:
        literals = self.literals
        t = type(value)
        if t not in literals:
            literals[t] = {}
        d = literals[t]
        if value not in d:
            d[value] = len(d)

    def literal_index(self, value: str) -> int:
        return self.literals[str][value]
