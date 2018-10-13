from setuptools import setup, Extension

setup(
    name='typedpkg_c_ext',
    version='1.0',
    packages=['typedpkg_c_ext'],
    ext_modules=[Extension('typedpkg_c_ext.hello', ['hello.c'])],
    zip_safe=False,
    package_data={
        'typedpkg_c_ext': ['py.typed']
    },
)
