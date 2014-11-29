"""Classes for representing mypy annotations"""

from typing import List

import mypy.nodes


class Annotation(mypy.nodes.Context):
	"""Abstract base class for all annotations."""

	def __init__(self, line: int = -1) -> None:
		self.line = line


class IgnoreAnnotation(Annotation):
    """The 'mypy: ignore' annotation"""

    def __init__(self, line: int = -1) -> None:
        super().__init__(line)

    def get_line(self) -> int:
        return self.line
