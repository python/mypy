import sys

if sys.platform == "win32":

    _SequenceType = list[tuple[str, str | None, int]]

    AdminExecuteSequence: _SequenceType
    AdminUISequence: _SequenceType
    AdvtExecuteSequence: _SequenceType
    InstallExecuteSequence: _SequenceType
    InstallUISequence: _SequenceType

    tables: list[str]
