from setuptools import setup

setup(
    name='typedpkg_namespace.beta',
    version='1.0.0',
    namespace_packages=['typedpkg_ns'],
    zip_safe=False,
    package_data={'typedpkg_ns.b': []},
    packages=['typedpkg_ns.b'],
)
