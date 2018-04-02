"""Routines for finding the sources that mypy will check"""

import os

from typing import List, Sequence, Set, Tuple, Optional

from mypy.build import BuildSource, PYTHON_EXTENSIONS
from mypy.options import Options


PY_EXTENSIONS = tuple(PYTHON_EXTENSIONS)


class InvalidSourceList(Exception):
    """Exception indicating a problem in the list of sources given to mypy."""


# TODO: use a FileSystemCache for this
def create_source_list(files: Sequence[str], options: Options) -> List[BuildSource]:
    """From a list of source files/directories, makes a list of BuildSources.

    Raises InvalidSourceList on errors.
    """
    targets = []
    for f in files:
        if f.endswith(PY_EXTENSIONS):
            # Can raise InvalidSourceList if a directory doesn't have a valid module name.
            targets.append(BuildSource(f, crawl_up(f)[1], None))
        elif os.path.isdir(f):
            sub_targets = expand_dir(f)
            if not sub_targets:
                raise InvalidSourceList("There are no .py[i] files in directory '{}'"
                                        .format(f))
            targets.extend(sub_targets)
        else:
            mod = os.path.basename(f) if options.scripts_are_modules else None
            targets.append(BuildSource(f, mod, None))
    return targets


def keyfunc(name: str) -> Tuple[int, str]:
    """Determines sort order for directory listing.

    The desirable property is foo < foo.pyi < foo.py.
    """
    base, suffix = os.path.splitext(name)
    for i, ext in enumerate(PY_EXTENSIONS):
        if suffix == ext:
            return (i, base)
    return (-1, name)


def expand_dir(arg: str, mod_prefix: str = '') -> List[BuildSource]:
    """Convert a directory name to a list of sources to build."""
    f = get_init_file(arg)
    if mod_prefix and not f:
        return []
    seen = set()  # type: Set[str]
    sources = []
    if f and not mod_prefix:
        top_dir, top_mod = crawl_up(f)
        mod_prefix = top_mod + '.'
    if mod_prefix:
        sources.append(BuildSource(f, mod_prefix.rstrip('.'), None))
    names = os.listdir(arg)
    names.sort(key=keyfunc)
    for name in names:
        path = os.path.join(arg, name)
        if os.path.isdir(path):
            sub_sources = expand_dir(path, mod_prefix + name + '.')
            if sub_sources:
                seen.add(name)
                sources.extend(sub_sources)
        else:
            base, suffix = os.path.splitext(name)
            if base == '__init__':
                continue
            if base not in seen and '.' not in base and suffix in PY_EXTENSIONS:
                seen.add(base)
                src = BuildSource(path, mod_prefix + base, None)
                sources.append(src)
    return sources


def crawl_up(arg: str) -> Tuple[str, str]:
    """Given a .py[i] filename, return (root directory, module).

    We crawl up the path until we find a directory without
    __init__.py[i], or until we run out of path components.
    """
    dir, mod = os.path.split(arg)
    mod = strip_py(mod) or mod
    while dir and get_init_file(dir):
        dir, base = os.path.split(dir)
        if not base:
            break
        # Ensure that base is a valid python module name
        if not base.isidentifier():
            raise InvalidSourceList('{} is not a valid Python package name'.format(base))
        if mod == '__init__' or not mod:
            mod = base
        else:
            mod = base + '.' + mod

    return dir, mod


def strip_py(arg: str) -> Optional[str]:
    """Strip a trailing .py or .pyi suffix.

    Return None if no such suffix is found.
    """
    for ext in PY_EXTENSIONS:
        if arg.endswith(ext):
            return arg[:-len(ext)]
    return None


def get_init_file(dir: str) -> Optional[str]:
    """Check whether a directory contains a file named __init__.py[i].

    If so, return the file's name (with dir prefixed).  If not, return
    None.

    This prefers .pyi over .py (because of the ordering of PY_EXTENSIONS).
    """
    for ext in PY_EXTENSIONS:
        f = os.path.join(dir, '__init__' + ext)
        if os.path.isfile(f):
            return f
    return None
