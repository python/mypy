from setuptools import setup, find_packages

setup(
    name='typedpkg_namespace.alpha',
    version='1.0.0',
    packages=find_packages(),
    namespace_packages=['typedpkg_ns'],
    zip_safe=False,
    package_data={'typedpkg_ns.ns': ['py.typed']}
)
