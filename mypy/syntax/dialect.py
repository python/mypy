"""Python dialect control.

This may be incomplet or inkorrekt.

Versions < 2.7 is not a priority.
Versions >= 3.0 and < 3.2 are not a priority.
Versions < 2.4 have many fundamental differences.
Versions < 2.2 have even more fundamental differences.
Versions 1.6 and 2.0 are not distinguished.
Versions < 1.6 are not even mentioned.
"""


from typing import (
    List,
    Sequence,
    Set,
    Tuple,
)

import os
import subprocess
import sys


# Maintain our own copy instead of using __future__ just in case we need
# to parse a newer version of python than we're running.
# Also we can add artificial ones.

available_futures = {
    # Internal pseudo-futures.
    'mypy-codec': '0.0',
    'mypy-stub': '0.0',
    'mypy-instring': '0.0',

    # Pseudo-futures from platform.python_implementation().
    # Note that only PyPy and CPython are tested.
    'variant-CPython': '0.0',
    'variant-PyPy': '0.0',
    'variant-Jython': '0.0',
    'variant-IronPython': '0.0',

    # Real features from the __future__ module.
    'nested_scopes': '2.1',
    'generators': '2.2',
    'division': '2.2',
    'absolute_import': '2.5',
    'with_statement': '2.5',
    'print_function': '2.6',
    'unicode_literals': '2.6',
    'barry_as_FLUFL': '3.1',
}


def check_futures(version: str, futures: Sequence[str]) -> Set[str]:
    for fut in futures:
        assert version >= available_futures[fut]
    return set(futures)


class Dialect:

    def __init__(self, version: str, future_list: Sequence[str] = []) -> None:
        """Construct a dialect for the given Python version and future set.

        `version` is like `'2.7.0'`, e.g. `platform.python_version()`.
        `future_list` is like `['X', 'Y', 'Z']` in `from __future__ import X, Y, Z`.
        """
        self.major, self.minor, self.patchlevel = [int(x) for x in version.split('.')]
        future_set = check_futures(version, future_list)
        self.base_version = version
        self.base_future_list = future_list
        self.base_future_set = future_set

        self.possible_futures = {k for (k, v) in available_futures.items() if v <= version}

        # Additional members will be set as needed by the lexer, parser, etc.

    def __repr__(self) -> str:
        return 'Dialect(%r, %r)' % (self.base_version, self.base_future_list)

    def add_future(self, future: str) -> 'Dialect':
        if future in self.base_future_set:
            return self
        return Dialect(self.base_version, self.base_future_list + [future])


class Implementation:

    def __init__(self, executable: str) -> None:
        command = '''if True:
        import platform, sys
        print((platform.python_implementation(), platform.python_version(), sys.path))
        '''
        output = subprocess.check_output([executable, '-c', command])
        impl, version, path = eval(output)  # type: Tuple[str, str, List[str]]

        self.executable = executable
        self.base_dialect = Dialect(version, ['variant-' + impl])
        self.stub_dialect = self.base_dialect.add_future('mypy-codec')
        self.python_path = path
        # TODO self.stub_path = []


def default_implementation(*, force_py2: bool = False) -> Implementation:
    """Return the preferred python implementation for the inferior.

    This looks at the MYPY_PYTHON environment variable, or else uses
    the current python version.

    The `force_py2` argument should possibly be deprecated.
    """
    if force_py2:
        try_pythons = [os.getenv('MYPY_PYTHON'), 'python2', 'python2.7', 'python']
    else:
        try_pythons = [os.getenv('MYPY_PYTHON'), sys.executable]
    for python in try_pythons:
        if python is None:
            continue
        try:
            impl = Implementation(python)
        except (OSError, subprocess.CalledProcessError):
            pass
        if force_py2 and impl.base_dialect.major != 2:
            continue
        return impl
    sys.exit('No suitable python executable found')
