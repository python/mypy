"""Routines for finding the sources that mypy will check"""

import functools
import os.path

from typing import List, Sequence, Set, Tuple, Optional
from typing_extensions import Final

from mypy.modulefinder import BuildSource, PYTHON_EXTENSIONS
from mypy.fscache import FileSystemCache
from mypy.options import Options
from mypy.util import normalise_package_root

PY_EXTENSIONS = tuple(PYTHON_EXTENSIONS)  # type: Final


class InvalidSourceList(Exception):
    """Exception indicating a problem in the list of sources given to mypy."""


def create_source_list(paths: Sequence[str], options: Options,
                       fscache: Optional[FileSystemCache] = None,
                       allow_empty_dir: bool = False) -> List[BuildSource]:
    """From a list of source files/directories, makes a list of BuildSources.

    Raises InvalidSourceList on errors.
    """
    fscache = fscache or FileSystemCache()
    finder = SourceFinder(fscache, explicit_package_roots=options.package_root or None)

    sources = []
    for path in paths:
        path = os.path.normpath(path)
        if path.endswith(PY_EXTENSIONS):
            # Can raise InvalidSourceList if a directory doesn't have a valid module name.
            name, base_dir = finder.crawl_up(path)
            sources.append(BuildSource(path, name, None, base_dir))
        elif fscache.isdir(path):
            sub_sources = finder.find_sources_in_dir(path)
            if not sub_sources and not allow_empty_dir:
                raise InvalidSourceList(
                    "There are no .py[i] files in directory '{}'".format(path)
                )
            sources.extend(sub_sources)
        else:
            mod = os.path.basename(path) if options.scripts_are_modules else None
            sources.append(BuildSource(path, mod, None))
    return sources


def keyfunc(name: str) -> Tuple[int, str]:
    """Determines sort order for directory listing.

    The desirable property is foo < foo.pyi < foo.py.
    """
    base, suffix = os.path.splitext(name)
    for i, ext in enumerate(PY_EXTENSIONS):
        if suffix == ext:
            return (i, base)
    return (-1, name)


class SourceFinder:
    def __init__(
        self, fscache: FileSystemCache, explicit_package_roots: Optional[List[str]]
    ) -> None:
        self.fscache = fscache
        self.explicit_package_roots = explicit_package_roots

    def is_package_root(self, path: str) -> bool:
        assert self.explicit_package_roots
        return normalise_package_root(path) in self.explicit_package_roots

    def find_sources_in_dir(self, path: str) -> List[BuildSource]:
        mod_prefix, root_dir = self.crawl_up_dir(path)
        if mod_prefix:
            mod_prefix += "."
        return self.find_sources_in_dir_helper(path, mod_prefix, root_dir)

    def find_sources_in_dir_helper(
        self, dir_path: str, mod_prefix: str, root_dir: str
    ) -> List[BuildSource]:
        assert not mod_prefix or mod_prefix.endswith(".")

        init_file = self.get_init_file(dir_path)
        # If the current directory is an explicit package root, explore it as such.
        # Alternatively, if we aren't given explicit package roots and we don't have an __init__
        # file, recursively explore this directory as a new package root.
        if (
            (self.explicit_package_roots is not None and self.is_package_root(dir_path))
            or (self.explicit_package_roots is None and init_file is None)
        ):
            mod_prefix = ""
            root_dir = dir_path

        seen = set()  # type: Set[str]
        sources = []

        if init_file:
            sources.append(BuildSource(init_file, mod_prefix.rstrip("."), None, root_dir))

        names = self.fscache.listdir(dir_path)
        names.sort(key=keyfunc)
        for name in names:
            # Skip certain names altogether
            if name == '__pycache__' or name.startswith('.') or name.endswith('~'):
                continue
            path = os.path.join(dir_path, name)

            if self.fscache.isdir(path):
                sub_sources = self.find_sources_in_dir_helper(
                    path, mod_prefix + name + '.', root_dir
                )
                if sub_sources:
                    seen.add(name)
                    sources.extend(sub_sources)
            else:
                stem, suffix = os.path.splitext(name)
                if stem == '__init__':
                    continue
                if stem not in seen and '.' not in stem and suffix in PY_EXTENSIONS:
                    seen.add(stem)
                    src = BuildSource(path, mod_prefix + stem, None, root_dir)
                    sources.append(src)

        return sources

    def crawl_up(self, path: str) -> Tuple[str, str]:
        """Given a .py[i] filename, return module and base directory.

        If we are given explicit package roots, we crawl up until we find one (or run out of
        path components).

        Otherwise, we crawl up the path until we find an directory without __init__.py[i]
        """
        parent, filename = os.path.split(path)
        module_name = strip_py(filename) or os.path.basename(filename)
        module_prefix, base_dir = self.crawl_up_dir(parent)
        if module_name == '__init__' or not module_name:
            module = module_prefix
        else:
            module = module_join(module_prefix, module_name)

        return module, base_dir

    # Add a cache in case many files are passed to mypy
    @functools.lru_cache()
    def crawl_up_dir(self, dir: str) -> Tuple[str, str]:
        """Given a directory name, return the corresponding module name and base directory."""
        parent_dir, base = os.path.split(dir)
        if (
            not dir or not base
            # In the absence of explicit package roots, a lack of __init__.py means we've reached
            # an (implicit) package root
            or (self.explicit_package_roots is None and not self.get_init_file(dir))
        ):
            module = ""
            base_dir = dir or "."
            return module, base_dir

        # Ensure that base is a valid python module name
        if base.endswith('-stubs'):
            base = base[:-6]  # PEP-561 stub-only directory
        if not base.isidentifier():
            raise InvalidSourceList('{} is not a valid Python package name'.format(base))

        if self.explicit_package_roots is not None:
            if self.is_package_root(parent_dir):
                return base, parent_dir

        parent_module, base_dir = self.crawl_up_dir(parent_dir)
        module = module_join(parent_module, base)
        return module, base_dir

    def get_init_file(self, dir: str) -> Optional[str]:
        """Check whether a directory contains a file named __init__.py[i].

        If so, return the file's name (with dir prefixed).  If not, return None.

        This prefers .pyi over .py (because of the ordering of PY_EXTENSIONS).
        """
        for ext in PY_EXTENSIONS:
            f = os.path.join(dir, '__init__' + ext)
            if self.fscache.isfile(f):
                return f
        return None


def module_join(parent: str, child: str) -> str:
    """Join module ids, accounting for a possibly empty parent."""
    if parent:
        return parent + '.' + child
    else:
        return child


def strip_py(arg: str) -> Optional[str]:
    """Strip a trailing .py or .pyi suffix.

    Return None if no such suffix is found.
    """
    for ext in PY_EXTENSIONS:
        if arg.endswith(ext):
            return arg[:-len(ext)]
    return None
