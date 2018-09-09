from setuptools import setup, find_packages

setup(
    name='macbeth_nested',
    version='1.0.0',
    packages=find_packages(),
    zip_safe=False,
    package_data={'macbeth_nested.nested_package': ['py.typed']}
)
