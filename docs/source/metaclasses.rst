.. _metaclasses:

Metaclasses
===========

A :ref:`metaclass <python:metaclasses>` is a class that describes
the construction and behavior of other classes, similarly to how classes
describe the construction and behavior of objects.
The default metaclass is :py:class:`type`, but it's possible to use other metaclasses.
Metaclasses allows one to create "a different kind of class", such as
:py:class:`~enum.Enum`\s, :py:class:`~typing.NamedTuple`\s and singletons.

Mypy has some special understanding of :py:class:`~abc.ABCMeta` and ``EnumMeta``.

.. _defining:

Defining a metaclass
********************

.. code-block:: python

    class M(type):
        pass

    class A(metaclass=M):
        pass

.. _examples:

Metaclass usage example
***********************

Mypy supports the lookup of attributes in the metaclass:

.. code-block:: python

    from typing import ClassVar, Self

    class M(type):
        count: ClassVar[int] = 0

        def make(cls) -> Self:
            M.count += 1
            return cls()

    class A(metaclass=M):
        pass

    a: A = A.make()  # make() is looked up at M; the result is an object of type A
    print(A.count)

    class B(A):
        pass

    b: B = B.make()  # metaclasses are inherited
    print(B.count + " objects were created")  # Error: Unsupported operand types for + ("int" and "str")

.. note::
    In Python 3.10 and earlier, ``Self`` is available in ``typing_extensions``.

.. _limitations:

Gotchas and limitations of metaclass support
********************************************

Note that metaclasses pose some requirements on the inheritance structure,
so it's better not to combine metaclasses and class hierarchies:

.. code-block:: python

    class M1(type): pass
    class M2(type): pass

    class A1(metaclass=M1): pass
    class A2(metaclass=M2): pass

    class B1(A1, metaclass=M2): pass  # Mypy Error: metaclass conflict
    # At runtime the above definition raises an exception
    # TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass of the metaclasses of all its bases

    class B12(A1, A2): pass  # Mypy Error: metaclass conflict

    # This can be solved via a common metaclass subtype:
    class CorrectMeta(M1, M2): pass
    class B2(A1, A2, metaclass=CorrectMeta): pass  # OK, runtime is also OK

* Mypy does not understand dynamically-computed metaclasses,
  such as ``class A(metaclass=f()): ...``
* Mypy does not and cannot understand arbitrary metaclass code.
* Mypy only recognizes subclasses of :py:class:`type` as potential metaclasses.
