from pipes import Template

table: dict[str, Template]
t: Template
uncompress: Template

class error(Exception): ...

def toaiff(filename: str) -> str: ...
def _toaiff(filename: str, temps: list[str]) -> str: ...
