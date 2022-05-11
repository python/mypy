from _typeshed import Self, StrPath
from typing import Text

_Label = tuple[int, Text | None]
_DFA = list[list[tuple[int, int]]]
_DFAS = tuple[_DFA, dict[int, int]]

class Grammar:
    symbol2number: dict[Text, int]
    number2symbol: dict[int, Text]
    states: list[_DFA]
    dfas: dict[int, _DFAS]
    labels: list[_Label]
    keywords: dict[Text, int]
    tokens: dict[int, int]
    symbol2label: dict[Text, int]
    start: int
    def __init__(self) -> None: ...
    def dump(self, filename: StrPath) -> None: ...
    def load(self, filename: StrPath) -> None: ...
    def copy(self: Self) -> Self: ...
    def report(self) -> None: ...

opmap_raw: Text
opmap: dict[Text, Text]
