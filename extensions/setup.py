# NOTE: This package must support Python 2.7 in addition to Python 3.x

from setuptools import setup

version = '0.5.0-dev'
description = 'Experimental type system extensions for programs checked with the mypy typechecker.'
long_description = '''
Mypy Extensions
===============

The "mypy_extensions" module defines experimental extensions to the
standard "typing" module that are supported by the mypy typechecker.
'''.lstrip()

classifiers = [
    'Development Status :: 2 - Pre-Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Topic :: Software Development',
]

setup(
    name='mypy_extensions',
    version=version,
    description=description,
    long_description=long_description,
    author='The mypy developers',
    author_email='jukka.lehtosalo@iki.fi',
    url='http://www.mypy-lang.org/',
    license='MIT License',
    py_modules=['mypy_extensions'],
    classifiers=classifiers,
    install_requires=[
        'typing >= 3.5.3; python_version < "3.5"',
    ],
)
