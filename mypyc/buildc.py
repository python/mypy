"""Build C extension module from C source."""

import glob
import os
import shutil
import subprocess
import tempfile
import sys
from typing import List, Tuple


class BuildError(Exception):
    def __init__(self, output: bytes) -> None:
        super().__init__('Build failed')
        self.output = output


def build_c_extension(cpath: str, module_name: str, preserve_setup: bool = False) -> str:
    tempdir = tempfile.mkdtemp()
    if preserve_setup:
        tempdir = '.'
    else:
        tempdir = tempfile.mkdtemp()
    try:
        setup_path = make_setup_py(cpath, tempdir, '', '')
        return run_setup_py_build(setup_path, module_name)
    finally:
        if not preserve_setup:
            shutil.rmtree(tempdir)


shim_template = """\
#include <Python.h>

PyObject *CPyInit_{modname}(void);

PyMODINIT_FUNC
PyInit_{modname}(void)
{{
    return CPyInit_{modname}();
}}
"""


def build_c_extension_shim(module_name: str, shared_lib: str) -> str:
    tempdir = tempfile.mkdtemp()
    cpath = os.path.join(tempdir, '%s.c' % module_name)
    with open(cpath, 'w') as f:
        f.write(shim_template.format(modname=module_name))
    try:
        setup_path = make_setup_py(cpath, tempdir, libraries=repr('stuff'), library_dirs=repr('.'))
        return run_setup_py_build(setup_path, module_name)
    finally:
        shutil.rmtree(tempdir)


def build_shared_lib_for_modules(cpath: str) -> str:
    out_file = 'libstuff.so'
    name = os.path.splitext(os.path.basename(cpath))[0]
    lib_path = build_c_extension(cpath, name, preserve_setup = True)
    shutil.copy(lib_path, out_file)
    return out_file


def include_dir() -> str:
    return os.path.join(os.path.dirname(__file__), '..', 'lib-rt')


# TODO: Make compiler arguments platform-specific.
setup_format = """\
from distutils.core import setup, Extension

module = Extension('{package_name}',
                   sources=['{cpath}'],
                   extra_compile_args=['-Wno-unused-function', '-Wno-unused-label', '-Werror',
                                       '-Wno-unreachable-code'],
                   libraries=[{libraries}],
                   library_dirs=[{library_dirs}])

setup(name='{package_name}',
      version='1.0',
      description='{package_name}',
      include_dirs=['{include_dir}'],
      ext_modules=[module])
"""


def make_setup_py(cpath: str, dirname: str, libraries: str, library_dirs: str) -> str:
    setup_path = os.path.join(dirname, 'setup.py')
    basename = os.path.basename(cpath)
    package_name = os.path.splitext(basename)[0]
    with open(setup_path, 'w') as f:
        f.write(
            setup_format.format(
                package_name=package_name,
                cpath=cpath,
                libraries=libraries,
                library_dirs=library_dirs,
                include_dir=include_dir()
            )
        )
    return setup_path


def run_setup_py_build(setup_path: str, module_name: str) -> str:
    try:
        subprocess.check_output(['python', setup_path, 'build'], stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        raise BuildError(err.output)
    so_path = glob.glob('build/*/%s*.so' % module_name)
    assert len(so_path) == 1
    return so_path[0]
