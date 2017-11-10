import os
from mypy import git

__version__ = '0.550'
base_version = __version__

mypy_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if git.is_git_repo(mypy_dir) and git.have_git():
    __version__ += '-' + git.git_revision(mypy_dir).decode('utf-8')
    if git.is_dirty(mypy_dir):
        __version__ += '-dirty'
del mypy_dir
