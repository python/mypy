import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy.errors import MypyError


class ErrorFormatter(ABC):
    """Defines how errors are formatted before being printed."""
    @abstractmethod
    def report_error(self, error: 'MypyError') -> str:
        raise NotImplementedError


class JSONFormatter(ErrorFormatter):
    def report_error(self, error: 'MypyError') -> str:
        return json.dumps({
            'file': error.file_path,
            'line': error.line,
            'column': error.column,
            'message': error.message,
            'hint': error.hint,
            'code': None if error.errorcode is None else error.errorcode.code,
        })
