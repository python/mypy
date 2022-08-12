from setuptools import setup

setup(
    name='typedpkg_namespace.alpha',
    version='1.0.0',
    namespace_packages=['typedpkg_ns'],
    zip_safe=False,
    package_data={'typedpkg_ns.a': ['py.typed']},
    packages=['typedpkg_ns.a'],
)
