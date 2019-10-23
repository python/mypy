#!/usr/bin/env python3
"""Build and upload mypy packages for Linux and macOS to PyPI.

*** You must first tag the release and use `git push --tags`. ***

Note: This should be run on macOS using official python.org Python 3.6 or
      later, as this is the only tested configuration. Use --force to
      run anyway.

This uses a fresh repo clone and a fresh virtualenv to avoid depending on
local state.

Ideas for improvements:

- also upload Windows wheels
- try installing the generated packages and running mypy
- try installing the uploaded packages and running mypy
- run tests
- verify that there is a green travis build

"""

import argparse
import getpass
import os
import os.path
import re
import subprocess
import sys
import tempfile
from typing import Any


class Builder:
    def __init__(self, version: str, force: bool, no_upload: bool) -> None:
        if not re.match(r'0\.[0-9]{3}$', version):
            sys.exit('Invalid version {!r} (expected form 0.123)'.format(version))
        self.version = version
        self.force = force
        self.no_upload = no_upload
        self.target_dir = tempfile.mkdtemp()
        self.repo_dir = os.path.join(self.target_dir, 'mypy')

    def build_and_upload(self) -> None:
        self.prompt()
        self.run_sanity_checks()
        print('Temporary target directory: {}'.format(self.target_dir))
        self.git_clone_repo()
        self.git_check_out_tag()
        self.verify_version()
        self.make_virtualenv()
        self.install_dependencies()
        self.make_wheel()
        self.make_sdist()
        self.download_compiled_wheels()
        if not self.no_upload:
            self.upload_wheels()
            self.upload_sdist()
            self.heading('Successfully uploaded wheel and sdist for mypy {}'.format(self.version))
            print("<< All done! >>")
        else:
            self.heading('Successfully built wheel and sdist for mypy {}'.format(self.version))
            dist_dir = os.path.join(self.repo_dir, 'dist')
            print('Generated packages:')
            for fnam in sorted(os.listdir(dist_dir)):
                print('  {}'.format(os.path.join(dist_dir, fnam)))

    def prompt(self) -> None:
        if self.force:
            return
        extra = '' if self.no_upload else ' and upload'
        print('This will build{} PyPI packages for mypy {}.'.format(extra, self.version))
        response = input('Proceed? [yN] ')
        if response.lower() != 'y':
            sys.exit('Exiting')

    def verify_version(self) -> None:
        version_path = os.path.join(self.repo_dir, 'mypy', 'version.py')
        with open(version_path) as f:
            contents = f.read()
        if "'{}'".format(self.version) not in contents:
            sys.stderr.write(
                '\nError: Version {} does not match {}/mypy/version.py\n'.format(
                self.version, self.repo_dir))
            sys.exit(2)

    def run_sanity_checks(self) -> None:
        if not sys.version_info >= (3, 6):
            sys.exit('You must use Python 3.6 or later to build mypy')
        if sys.platform != 'darwin' and not self.force:
            sys.exit('You should run this on macOS; use --force to go ahead anyway')
        os_file = os.path.realpath(os.__file__)
        if not os_file.startswith('/Library/Frameworks') and not self.force:
            # Be defensive -- Python from brew may produce bad packages, for example.
            sys.exit('Error -- run this script using an official Python build from python.org')
        if getpass.getuser() == 'root':
            sys.exit('This script must not be run as root')

    def git_clone_repo(self) -> None:
        self.heading('Cloning mypy git repository')
        self.run('git clone https://github.com/python/mypy')

    def git_check_out_tag(self) -> None:
        tag = 'v{}'.format(self.version)
        self.heading('Check out {}'.format(tag))
        self.run('cd mypy && git checkout {}'.format(tag))
        self.run('cd mypy && git submodule update --init')

    def make_virtualenv(self) -> None:
        self.heading('Creating a fresh virtualenv')
        self.run('python3 -m virtualenv -p {} mypy-venv'.format(sys.executable))

    def install_dependencies(self) -> None:
        self.heading('Installing build dependencies')
        self.run_in_virtualenv('pip3 install wheel twine && pip3 install -U setuptools')

    def make_wheel(self) -> None:
        self.heading('Building wheel')
        self.run_in_virtualenv('python3 setup.py bdist_wheel')

    def make_sdist(self) -> None:
        self.heading('Building sdist')
        self.run_in_virtualenv('python3 setup.py sdist')

    def download_compiled_wheels(self) -> None:
        self.heading('Downloading wheels compiled with mypyc')
        # N.B: We run the version in the current checkout instead of
        # the one in the version we are releasing, in case we needed
        # to fix the script.
        self.run_in_virtualenv(
            '%s %s' %
            (os.path.abspath('misc/download-mypyc-wheels.py'), self.version))

    def upload_wheels(self) -> None:
        self.heading('Uploading wheels')
        for name in os.listdir(os.path.join(self.target_dir, 'mypy', 'dist')):
            if name.startswith('mypy-{}-'.format(self.version)) and name.endswith('.whl'):
                self.run_in_virtualenv(
                    'twine upload dist/{}'.format(name))

    def upload_sdist(self) -> None:
        self.heading('Uploading sdist')
        self.run_in_virtualenv('twine upload dist/mypy-{}.tar.gz'.format(self.version))

    def run(self, cmd: str) -> None:
        try:
            subprocess.check_call(cmd, shell=True, cwd=self.target_dir)
        except subprocess.CalledProcessError:
            sys.stderr.write('Error: Command {!r} failed\n'.format(cmd))
            sys.exit(1)

    def run_in_virtualenv(self, cmd: str) -> None:
        self.run('. mypy-venv/bin/activate && cd mypy &&' + cmd)

    def heading(self, heading: str) -> None:
        print()
        print('==== {} ===='.format(heading))
        print()


def parse_args() -> Any:
    parser = argparse.ArgumentParser(
        description='PyPI mypy package uploader (for non-Windows packages only)')
    parser.add_argument('--force', action='store_true', default=False,
                        help='Skip prompts and sanity checks (be careful!)')
    parser.add_argument('--no-upload', action='store_true', default=False,
                        help="Only build packages but don't upload")
    parser.add_argument('version', help='Mypy version to release')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    builder = Builder(args.version, args.force, args.no_upload)
    builder.build_and_upload()
