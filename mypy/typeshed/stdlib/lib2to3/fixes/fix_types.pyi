from typing import ClassVar
from typing_extensions import Literal

from .. import fixer_base

class FixTypes(fixer_base.BaseFix):
    BM_compatible: ClassVar[Literal[True]]
    PATTERN: ClassVar[str]
    def transform(self, node, results): ...
