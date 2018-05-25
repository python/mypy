"""Test cases that run tests as subprocesses."""

import os
import subprocess
import sys
import unittest


base_dir = os.path.join(os.path.dirname(__file__), '..', '..')


class TestExternal(unittest.TestCase):
    def test_c_unit_test(self) -> None:
        """Run C unit tests in a subprocess."""
        # Build Google Test, the C++ framework we use for testing C code.
        # The source code for Google Test is copied to this repository.
        #
        # TODO: Get this to work on Windows.
        if sys.platform == 'darwin':
            env = {'CPPFLAGS': '-mmacosx-version-min=10.10'}
        else:
            env = os.environ.copy()
        subprocess.check_call(['make', 'gtest_main.a'],
                              env=env,
                              cwd=os.path.join(base_dir, 'external', 'googletest', 'make'))
        # Build and run C unit tests.
        if sys.platform == 'darwin':
            env = {}
        else:
            env = os.environ.copy()
        if 'GTEST_COLOR' not in os.environ:
            env['GTEST_COLOR'] = 'yes'  # Use fancy colors
        status = subprocess.call(['make', 'test'],
                                 env=env,
                                 cwd=os.path.join(base_dir, 'lib-rt'))
        if status != 0:
            raise AssertionError("make test: C unit test failure")

    def test_self_type_check(self) -> None:
        """Use the bundled mypy (in git submodule) to type check mypyc."""
        mypy_dir = os.path.join(base_dir, 'external', 'mypy')
        if not os.path.exists(os.path.join(mypy_dir, 'typeshed', 'stdlib')):
            raise AssertionError('Submodule mypy/typeshed not ready')
        env = {'PYTHONPATH': mypy_dir,
               'MYPYPATH': '%s:%s' % (mypy_dir, base_dir)}
        status = subprocess.call(
                [sys.executable,
                 '-m', 'mypy',
                 '--config-file', 'mypy.ini', '-p', 'mypyc'],
                env=env)
        if status != 0:
            raise AssertionError("Self type check failure")
