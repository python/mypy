.. _final_attrs:

Final names, methods and classes
================================

This section introduces these related features:

1. *Final names* are variables or attributes that should not be reassigned after
   initialization. They are useful for declaring constants.
2. *Final methods* should not be overridden in a subclass.
3. *Final classes* should not be subclassed.

All of these are only enforced by mypy, and only in annotated code.
They is no runtime enforcement by the Python runtime.

.. note::

   These are experimental features. They might change in later
   versions of mypy. The *final* qualifiers are available through the
   ``typing_extensions`` package on PyPI.

Final names
-----------

You can use the ``typing_extensions.Final`` qualifier to indicate that
a name or attribute should not be reassigned, redefined, or
overridden.  This is often useful for module and class level constants
as a way to prevent unintended modification.  Mypy will prevent
further assignments to final names in type-checked code:

.. code-block:: python

   from typing_extensions import Final

   RATE: Final = 3000

   class Base:
       DEFAULT_ID: Final = 0

   RATE = 300  # Error: can't assign to final attribute
   Base.DEFAULT_ID = 1  # Error: can't override a final attribute

Another use case for final attributes is to protect certain attributes
from being overridden in a subclass:

.. code-block:: python

   from typing_extensions import Final

   class Window:
       BORDER_WIDTH: Final = 2.5
       ...

   class ListView(Window):
       BORDER_WIDTH = 3  # Error: can't override a final attribute

You can use :py:class:`@property <property>` to make an attribute read-only, but unlike ``Final``,
it doesn't work with module attributes, and it doesn't prevent overriding in
subclasses.

Syntax variants
***************

You can use ``Final`` in one of these forms:

* You can provide an explicit type using the syntax ``Final[<type>]``. Example:

  .. code-block:: python

     ID: Final[float] = 1

* You can omit the type:

  .. code-block:: python

     ID: Final = 1

  Here mypy will infer type ``int`` for ``ID``. Note that unlike for
  generic classes this is *not* the same as ``Final[Any]``.

* In class bodies and stub files you can omit the right hand side and just write
  ``ID: Final[float]``.

* Finally, you can write ``self.id: Final = 1`` (also optionally with
  a type in square brackets). This is allowed *only* in
  :py:meth:`__init__ <object.__init__>` methods, so that the final instance attribute is
  assigned only once when an instance is created.

Details of using ``Final``
**************************

These are the two main rules for defining a final name:

* There can be *at most one* final declaration per module or class for
  a given attribute. There can't be separate class-level and instance-level
  constants with the same name.

* There must be *exactly one* assignment to a final name.

A final attribute declared in a class body without an initializer must
be initialized in the :py:meth:`__init__ <object.__init__>` method (you can skip the
initializer in stub files):

.. code-block:: python

   class ImmutablePoint:
       x: Final[int]
       y: Final[int]  # Error: final attribute without an initializer

       def __init__(self) -> None:
           self.x = 1  # Good

``Final`` can only be used as the outermost type in assignments or variable
annotations. Using it in any other position is an error. In particular,
``Final`` can't be used in annotations for function arguments:

.. code-block:: python

   x: List[Final[int]] = []  # Error!

   def fun(x: Final[List[int]]) ->  None:  # Error!
       ...

``Final`` and :py:data:`~typing.ClassVar` should not be used together. Mypy will infer
the scope of a final declaration automatically depending on whether it was
initialized in the class body or in :py:meth:`__init__ <object.__init__>`.

A final attribute can't be overridden by a subclass (even with another
explicit final declaration). Note however that a final attribute can
override a read-only property:

.. code-block:: python

   class Base:
       @property
       def ID(self) -> int: ...

   class Derived(Base):
       ID: Final = 1  # OK

Declaring a name as final only guarantees that the name wll not be re-bound
to another value. It doesn't make the value immutable. You can use immutable ABCs
and containers to prevent mutating such values:

.. code-block:: python

   x: Final = ['a', 'b']
   x.append('c')  # OK

   y: Final[Sequence[str]] = ['a', 'b']
   y.append('x')  # Error: Sequence is immutable
   z: Final = ('a', 'b')  # Also an option

Final methods
-------------

Like with attributes, sometimes it is useful to protect a method from
overriding. You can use the ``typing_extensions.final``
decorator for this purpose:

.. code-block:: python

   from typing_extensions import final

   class Base:
       @final
       def common_name(self) -> None:
           ...

   class Derived(Base):
       def common_name(self) -> None:  # Error: cannot override a final method
           ...

This ``@final`` decorator can be used with instance methods, class methods,
static methods, and properties.

For overloaded methods you should add ``@final`` on the implementation
to make it final (or on the first overload in stubs):

.. code-block:: python

   from typing import Any, overload

   class Base:
       @overload
       def method(self) -> None: ...
       @overload
       def method(self, arg: int) -> int: ...
       @final
       def method(self, x=None):
           ...

Final classes
-------------

You can apply the ``typing_extensions.final`` decorator to a class to indicate
to mypy that it should not be subclassed:

.. code-block:: python

   from typing_extensions import final

   @final
   class Leaf:
       ...

   class MyLeaf(Leaf):  # Error: Leaf can't be subclassed
       ...

The decorator acts as a declaration for mypy (and as documentation for
humans), but it doesn't actually prevent subclassing at runtime.

Here are some situations where using a final class may be useful:

* A class wasn't designed to be subclassed. Perhaps subclassing would not
  work as expected, or subclassing would be error-prone.
* Subclassing would make code harder to understand or maintain.
  For example, you may want to prevent unnecessarily tight coupling between
  base classes and subclasses.
* You want to retain the freedom to arbitrarily change the class implementation
  in the future, and these changes might break subclasses.

An abstract class that defines at least one abstract method or
property and has ``@final`` decorator will generate an error from
mypy, since those attributes could never be implemented.

.. code-block:: python

    from abc import ABCMeta, abstractmethod
    from typing_extensions import final

    @final
    class A(metaclass=ABCMeta):  # error: Final class A has abstract attributes "f"
        @abstractmethod
        def f(self, x: int) -> None: pass
