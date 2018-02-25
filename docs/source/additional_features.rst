Additional features
-------------------

Several mypy features are not currently covered by this tutorial,
including the following:

- inheritance between generic classes
- compatibility and subtyping of generic types, including covariance of generic types
- ``super()``


.. _attrs_package:

The attrs package
*****************

`attrs <https://www.attrs.org/en/stable>`_ is a package that lets you define
classes without writing boilerplate code. Mypy can detect uses of the
package and will generate the necessary method definitions for decorated
classes using the type annotations it finds.
Type annotations can be added as follows:

.. code-block:: python

    import attr
    @attr.s
    class A:
        one: int = attr.ib()          # Variable annotation (Python 3.6+)
        two = attr.ib()  # type: int  # Type comment
        three = attr.ib(type=int)     # type= argument

If you're using ``auto_attribs=True`` you must use variable annotations.

.. code-block:: python

    import attr
    @attr.s(auto_attribs=True)
    class A:
        one: int
        two: int = 7
        three: int = attr.ib(8)

The Typeshed has a couple of "white lie" annotations to make type checking
easier. ``attr.ib`` and ``attr.Factory`` actually return objects, but the
annotation says these return the types that they expect to be assigned to.
That enables this to work:

.. code-block:: python

    import attr
    from typing import Dict
    @attr.s(auto_attribs=True)
        one: int = attr.ib(8)
        two: Dict[str, str] = attr.Factory(dict)
        bad: str = attr.ib(16)   # Error: can't assign int to str

Caveats/Known Issues
====================

* The detection of attr classes and attributes works by function name only.
  This means that if you have your own helper functions that, for example,
  ``return attr.ib()`` mypy will not see them.

* All boolean arguments that mypy cares about must be literal ``True`` or ``False``.
  e.g the following will not work:

  .. code-block:: python

      import attr
      YES = True
      @attr.s(init=YES)
      class A:
          ...

* Currently, ``converter`` only supports named functions.  If mypy finds something else it
  will complain about not understanding the argument and the type annotation in
  ``__init__`` will be replaced by ``Any``.

* `Validator decorators <http://www.attrs.org/en/stable/examples.html#decorator>`_
  and `default decorators <http://www.attrs.org/en/stable/examples.html#defaults>`_
  are not type-checked against the attribute they are setting/validating.

* Method definitions added by mypy currently overwrite any existing method
  definitions.
