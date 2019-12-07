from typing import List, Optional

import mypy.errors


class Errors:
    def __init__(
            self,
            ignore_errors_by_regex: Optional[List[str]] = None
    ) -> None:
        self.num_errors = 0
        self.num_warnings = 0
        self._errors = mypy.errors.Errors(
            ignore_errors_by_regex=ignore_errors_by_regex
        )

    def error(self, msg: str, path: str, line: int) -> None:
        self._errors.report(line, None, msg, severity='error', file=path)
        self.num_errors += 1

    def warning(self, msg: str, path: str, line: int) -> None:
        self._errors.report(line, None, msg, severity='warning', file=path)
        self.num_warnings += 1

    def new_messages(self) -> List[str]:
        return self._errors.new_messages()

    def flush_errors(self) -> None:
        for error in self.new_messages():
            print(error)
