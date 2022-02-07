import os

from mypy import git

# Base version.
# - Release versions have the form "0.NNN".
# - Dev versions have the form "0.NNN+dev" (PLUS sign to conform to PEP 440).
# - For 1.0 we'll switch back to 1.2.3 form.
__version__ = '0.940+dev'
base_version = __version__

# tuple[major, minor, patch, releaselevel, mypy version, mypy releaselevel, hash]
__based_version__ = (
    2,
    0,
    0,
    "dev",
    __version__.split("+dev")[0],
    "dev" if "+dev" in __version__ else "release",
)

mypy_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if __based_version__[3] == 'dev' and git.is_git_repo(mypy_dir) and git.have_git():
    hash_ = git.git_revision(mypy_dir).decode('utf-8')
    if git.is_dirty(mypy_dir):
        hash_ += '.dirty'
    __based_version__ += hash_,
del mypy_dir
