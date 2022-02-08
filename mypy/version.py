import os
from typing import NamedTuple

from mypy import git


class VersionInfo(NamedTuple):
    """Mypy version information.

    Release versions have the form "0.NNN".
    Dev versions have the form "0.NNN+dev" (PLUS sign to conform to PEP 440).
    For 1.0 we'll switch back to 1.2.3 form.
    """
    major: int = 0
    minor: int = 940
    patch: int = 0  # not currently used
    releaselevel: str = "dev"

    def __str__(self) -> str:
        result = f"{self.major}.{self.minor}"
        if self.releaselevel == "dev":
            result += "+dev"
        return result

# Base version.
# Deprecated, prefer VersionInfo
# EOF
__version__ = str(VersionInfo())
base_version = __version__

mypy_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if __version__.endswith('+dev') and git.is_git_repo(mypy_dir) and git.have_git():
    __version__ += '.' + git.git_revision(mypy_dir).decode('utf-8')
    if git.is_dirty(mypy_dir):
        __version__ += '.dirty'
del mypy_dir
