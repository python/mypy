"""Build C extension module from C source."""

import glob
import hashlib
import os
import shutil
import subprocess
import tempfile
import sys
from typing import List, Tuple
from mypyc.namegen import exported_name


class BuildError(Exception):
    def __init__(self, output: bytes) -> None:
        super().__init__('Build failed')
        self.output = output


def build_c_extension(cpath: str, module_name: str, dirname: str) -> str:
    setup_path = make_setup_py(module_name, '', cpath, dirname, [], [], [])
    return run_setup_py_build(setup_path, module_name, dirname)


shim_template = """\
#include <Python.h>

PyObject *CPyInit_{full_modname}(void);

PyMODINIT_FUNC
PyInit_{modname}(void)
{{
    return CPyInit_{full_modname}();
}}
"""


def build_c_extension_shim(full_module_name: str, shared_lib_path: str, dirname: str,
                           is_package: bool=False) -> str:
    module_parts = full_module_name.split('.')
    module_name = module_parts[-1]
    if is_package:
        module_parts.append('__init__')
    shared_lib = os.path.basename(shared_lib_path)
    assert shared_lib.startswith('lib') and shared_lib.endswith('.so')
    libname = shared_lib[3:-3]
    cname = '%s.c' % full_module_name.replace('.', '___')  # XXX
    cpath = os.path.join(dirname, cname)
    if '.' in full_module_name:
        packages = 'packages=[{}],'.format(repr('.'.join(full_module_name.split('.')[:-1])))
    else:
        packages = ''
    if len(module_parts) > 1:
        relative_lib_path = os.path.join(*(['..'] * (len(module_parts) - 1)))
    else:
        relative_lib_path = '.'
    with open(cpath, 'w') as f:
        f.write(shim_template.format(modname=module_name,
                                     full_modname=exported_name(full_module_name)))
    setup_path = make_setup_py(full_module_name,
                               packages,
                               cname,
                               dirname,
                               libraries=[libname],
                               library_dirs=[os.path.abspath(os.path.dirname(shared_lib_path))],
                               runtime_library_dirs=[relative_lib_path])
    return run_setup_py_build(setup_path, module_name, dirname)


def shared_lib_name(modules: List[str]) -> str:
    h = hashlib.sha1()
    h.update(','.join(modules).encode())
    return 'libmypyc_%s.so' % h.hexdigest()[:20]


def build_shared_lib_for_modules(cpath: str, modules: List[str],
                                 dirname: str) -> str:
    out_file = shared_lib_name(modules)
    name = os.path.splitext(os.path.basename(cpath))[0]
    lib_path = build_c_extension(cpath, name, dirname)
    out_path = os.path.join(dirname, out_file)
    shutil.copy(lib_path, out_path)
    # OS X libraries have names built into them, so change the name to what we want
    # and eliminate the relative path while we are at it.
    if sys.platform == 'darwin':
        try:
            subprocess.check_output(['install_name_tool', '-id',
                                     os.path.basename(out_path),
                                     out_path],
                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            raise BuildError(err.output)
    return out_path


def include_dir() -> str:
    return os.path.join(os.path.dirname(__file__), '..', 'lib-rt')


# TODO: Make compiler arguments platform-specific.
setup_format = """\
from distutils.core import setup, Extension
from distutils import sysconfig
import sys
import os

extra_compile_args = ['-Werror', '-Wno-unused-function', '-Wno-unused-label',
                      '-Wno-unreachable-code', '-Wno-unused-variable', '-Wno-trigraphs']

vars = sysconfig.get_config_vars()

# On OS X, Force the creation of dynamic libraries instead of bundles so that
# we can link against multi-module shared libraries.
# From https://stackoverflow.com/a/32765319
if sys.platform == 'darwin':
    vars['LDSHARED'] = vars['LDSHARED'].replace('-bundle', '-dynamiclib')

# And on Linux, set the rpath to $ORIGIN so they will look for the shared
# library in the directory that they live in.
elif sys.platform == 'linux':
    # This flag is needed for gcc but does not exist on clang. Currently we only support gcc for
    # linux.
    # TODO: Add support for clang on linux. Possibly also add support for gcc on Darwin.
    extra_compile_args += ['-Wno-unused-but-set-variable']

module = Extension('{package_name}',
                   sources=['{cpath}'],
                   extra_compile_args=extra_compile_args,
                   {packages}
                   libraries={libraries},
                   library_dirs={library_dirs},
                   runtime_library_dirs=[os.path.join("$ORIGIN", s) for s in {rt_library_dirs}],
)

setup(name='{package_name}',
      version='1.0',
      description='{package_name}',
      include_dirs=['{include_dir}'],
      ext_modules=[module])
"""


def make_setup_py(package_name: str, packages: str,
                  cpath: str, dirname: str,
                  libraries: List[str],
                  library_dirs: List[str],
                  runtime_library_dirs: List[str]) -> str:
    setup_name = '{}_setup.py'.format(package_name)
    with open(os.path.join(dirname, setup_name), 'w') as f:
        f.write(
            setup_format.format(
                package_name=package_name,
                cpath=cpath,
                packages=packages,
                libraries=libraries,
                library_dirs=library_dirs,
                include_dir=include_dir(),
                rt_library_dirs=runtime_library_dirs,
            )
        )
    return setup_name


def run_setup_py_build(setup_path: str, module_name: str, dirname: str) -> str:
    try:
        subprocess.check_output(['python', setup_path, 'build'], stderr=subprocess.STDOUT,
                                cwd=dirname)
    except subprocess.CalledProcessError as err:
        raise BuildError(err.output)
    so_path = glob.glob(os.path.join(dirname, 'build/**/%s.*.so') % module_name, recursive=True)
    assert len(so_path) == 1, so_path
    return so_path[0]
