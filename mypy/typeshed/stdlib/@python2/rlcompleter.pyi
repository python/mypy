from typing import Any, Union

_Text = Union[str, unicode]

class Completer:
    def __init__(self, namespace: dict[str, Any] | None = ...) -> None: ...
    def complete(self, text: _Text, state: int) -> str | None: ...
