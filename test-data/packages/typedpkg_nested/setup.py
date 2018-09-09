from setuptools import setup, find_packages

setup(
    name='typedpkg_nested',
    version='1.0.0',
    packages=find_packages(),
    zip_safe=False,
    package_data={'typedpkg_nested.nested_package': ['py.typed']}
)
