from setuptools import setup, find_packages

setup(
    name='macbeth_namespace',
    version='1.0.0',
    packages=find_packages(),
    zip_safe=False,
    package_data={'macbeth_namespace.inside_namespace_package': ['py.typed']}
)
