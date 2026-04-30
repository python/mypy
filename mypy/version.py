from __future__ import annotations

import os

from mypy import git

# Base version.
# - Release versions have the form "1.2.3".
# - Dev versions have the form "1.2.3+dev" (PLUS sign to conform to PEP 440).
# - Before 1.0 we had the form "0.NNN".
__version__ = "2.1.0+dev"
base_version = __version__

mypy_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if __version__.endswith("+dev") and git.is_git_repo(mypy_dir):
    revision = git.git_revision_no_subprocess(mypy_dir)
    if revision is not None:
        __version__ += "." + revision.decode("ascii")
    elif git.have_git():
        __version__ += "." + git.git_revision(mypy_dir).decode("utf-8")
del mypy_dir
