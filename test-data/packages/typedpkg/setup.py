"""
This setup file installs packages to test mypy's PEP 561 implementation
"""

from setuptools import setup

setup(
    name='typedpkg',
    author="The mypy team",
    version='0.1',
    package_data={'typedpkg': ['py.typed']},
    packages=['typedpkg', 'typedpkg.pkg'],
    include_package_data=True,
    zip_safe=False,
)
