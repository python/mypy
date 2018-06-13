"""Build C extension module from C source."""

import glob
import os
import shutil
import subprocess
import tempfile


# TODO: Make compiler arguments platform-specific.
setup_format = """\
from distutils.core import setup, Extension

module = Extension('{package_name}',
                   sources=['{cpath}'],
                   extra_compile_args=['-Wno-unused-function', '-Wno-unused-label', '-Werror',
                                       '-Wno-unreachable-code'])

setup(name='{package_name}',
      version='1.0',
      description='{package_name}',
      include_dirs=['{include_dir}'],
      ext_modules=[module])
"""


class BuildError(Exception):
    def __init__(self, output: bytes) -> None:
        super().__init__('Build failed')
        self.output = output


def build_c_extension(cpath: str, preserve_setup: bool = False) -> str:
    if preserve_setup:
        tempdir = '.'
    else:
        tempdir = tempfile.mkdtemp()
    include_dir = os.path.join(os.path.dirname(__file__), '..', 'lib-rt')
    try:
        setup_path = os.path.join(tempdir, 'setup.py')
        basename = os.path.basename(cpath)
        package_name = os.path.splitext(basename)[0]
        with open(setup_path, 'w') as f:
            f.write(setup_format.format(
                cpath=cpath,
                package_name=package_name,
                include_dir=include_dir))
        try:
            subprocess.check_output(['python', setup_path, 'build'], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            raise BuildError(err.output)
        so_path = glob.glob('build/*/*.so')
        assert len(so_path) == 1
        return so_path[0]
    finally:
        if not preserve_setup:
            shutil.rmtree(tempdir)
