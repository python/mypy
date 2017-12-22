"""
This setup file install packages to test mypy's PEP 561 implementation
"""

from distutils.core import setup

setup(
    name='typedpkg',
    author="The mypy team",
    version='0.1',
    package_data={'typedpkg': ['py.typed']},
    packages=['typedpkg'],
    include_package_data=True,
)