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

Librt contents
--------------

Follow submodule links in the table to a detailed description of each submodule.

.. list-table::
   :header-rows: 1
   :widths: 30 70
   :width: 100%

   * - Module
     - Description
   * - :doc:`librt.base64 <librt_base64>`
     - Fast Base64 encoding and decoding
