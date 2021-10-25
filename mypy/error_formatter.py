import json
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy.errors import ErrorTuple


class ErrorFormatter(ABC):
    """Defines how errors are formatted before being printed."""
    @abstractmethod
    def report_error(self, error: 'ErrorTuple') -> str:
        raise NotImplementedError

class JSONFormatter(ErrorFormatter):
    def report_error(self, error: 'ErrorTuple') -> str:
        file, line, column, severity, message, _, errorcode = error
        return json.dumps({
            'file': file,
            'line': line,
            'column': column,
            'severity': severity,
            'message': message,
            'code': None if errorcode is None else errorcode.code,
        })
