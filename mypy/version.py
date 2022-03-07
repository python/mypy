import os
from mypy import git

# Base version.
# - Release versions have the form "0.NNN".
# - Dev versions have the form "0.NNN+dev" (PLUS sign to conform to PEP 440).
# - For 1.0 we'll switch back to 1.2.3 form.
base_version = '0.950+dev'
# Overridden by setup.py
__version__ = base_version


def setup_compute_version() -> str:
    # We allow an environment variable to override version, but we should probably
    # enforce that it is consistent with the existing version minus additional information.
    if "MYPY_VERSION" in os.environ:
        assert os.environ["MYPY_VERSION"].startswith(base_version)
        return os.environ["MYPY_VERSION"]

    mypy_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    if base_version.endswith('+dev') and git.is_git_repo(mypy_dir) and git.have_git():
        version = base_version + '.' + git.git_revision(mypy_dir).decode('utf-8')
        if git.is_dirty(mypy_dir):
            return version + ".dirty"
        return version
    return base_version
