.. _librt:

Librt overview
==============

The `librt <https://pypi.org/project/librt/>`_ package defines fast
primitive operations that are optimized for code compiled
using mypyc. It has carefully selected efficient alternatives for
certain Python standard library features.

``librt`` is a small, focused library. The goal is not to reimplement
the Python standard library, but to fill in specific gaps or
limitations.

Librt submodules
----------------

The top-level ``librt`` includes these submodules:

 * :doc:`librt.base64 <librt_base64>`
