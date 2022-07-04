import os
from mypy import git
from mypy.versionutil import VersionInfo

# Base version.
# - Release versions have the form "0.NNN".
# - Dev versions have the form "0.NNN+dev" (PLUS sign to conform to PEP 440).
# - For 1.0 we'll switch back to 1.2.3 form.
__version__ = '0.970+dev'
base_version = __version__

# friendly version information
based_version_info = VersionInfo(
    1,
    5,
    0,
    "dev",
    0,
    __version__.split("+dev")[0],
    "dev" if "+dev" in __version__ else "final",
)
# simple string version with git info
__based_version__ = based_version_info.simple_str()
# simple string version without git info
base_based_version = __based_version__

mypy_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if based_version_info.release_level == 'dev' and git.is_git_repo(mypy_dir) and git.have_git():
    __based_version__ += '.' + git.git_revision(mypy_dir).decode('utf-8')
    if git.is_dirty(mypy_dir):
        __based_version__ += '.dirty'
del mypy_dir
