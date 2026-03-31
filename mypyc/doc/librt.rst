.. _librt:

Librt overview
==============

The `librt <https://pypi.org/project/librt/>`_ package defines fast
primitive operations that are optimized for code compiled
using mypyc. It has carefully selected efficient alternatives for
certain Python standard library features.

``librt`` is a small, focused library. The goal is not to reimplement
the Python standard library, but to address specific gaps or
bottlenecks.

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

Backward compatibility
----------------------

We aim to keep librt backward compatible. It's recommended that you allow users
of your published projects that use librt to update to a more recent version. For
example, use a ``>=`` version constraint in your ``requirements.txt``.

Using librt in non-compiled code
--------------------------------

Using librt in code that is *not* compiled with mypyc is fully supported. However,
some librt features may have significantly degraded performance when used from
interpreted code. We will document the most notable such cases, but it's always
recommended to measure the performance impact when considering a switch from Python
standard library functionality to librt in a non-compiled use case.
