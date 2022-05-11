from distutils.config import PyPIRCCommand
from typing import ClassVar

class upload(PyPIRCCommand):
    description: ClassVar[str]
    boolean_options: ClassVar[list[str]]
    def run(self) -> None: ...
    def upload_file(self, command, pyversion, filename) -> None: ...
