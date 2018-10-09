Final names, methods and classes
================================

You can declare a variable or attribute as final, which means that the variable
must not be assigned a new value after initialization. This is often useful for
module and class level constants as a way to prevent unintended modification.
Mypy will prevent further assignments to final names in type-checked code:

.. code-block:: python

   from typing_extensions import Final

   RATE: Final = 3000
   class Base:
       DEFAULT_ID: Final = 0

   # 1000 lines later

   RATE = 300  # Error: can't assign to final attribute
   Base.DEFAULT_ID = 1  # Error: can't override a final attribute

Another use case for final attributes is where a user wants to protect certain
instance attributes from overriding in a subclass:

.. code-block:: python

   import uuid
   from typing_extensions import Final

   class Snowflake:
       """An absolutely unique object in the database"""
       def __init__(self) -> None:
           self.id: Final = uuid.uuid4()

   # 1000 lines later

   class User(Snowflake):
       id = uuid.uuid4()  # Error: can't override a final attribute

Some other use cases might be solved by using ``@property``, but note that
neither of the above use cases can be solved with it.

.. note::

   This is an experimental feature. Some details might change in later
   versions of mypy. The final qualifiers are available in the
   ``typing_extensions`` package available on PyPI.

Syntax variants
***************

The ``typing_extensions.Final`` qualifier indicates that a given name or
attribute should never be re-assigned, re-defined, nor overridden. It can be
used in one of these forms:


* You can provide an explicit type using the syntax ``Final[<type>]``. Example:

  .. code-block:: python

     ID: Final[float] = 1

* You can omit the type: ``ID: Final = 1``. Note that unlike for generic
  classes this is *not* the same as ``Final[Any]``. Here mypy will infer
  type ``int``.

* In stub files you can omit the right hand side and just write
  ``ID: Final[float]``.

* Finally, you can define ``self.id: Final = 1`` (also with a type argument),
  but this is allowed *only* in ``__init__`` methods.

Definition rules
****************

The are two rules that should be always followed when defining a final name:

* There can be *at most one* final declaration per module or class for
  a given attribute:

  .. code-block:: python

     from typing_extensions import Final

     ID: Final = 1
     ID: Final = 2  # Error: "ID" already declared as final

     class SomeCls:
         id: Final = 1
         def __init__(self, x: int) -> None:
             self.id: Final = x  # Error: "id" already declared in class body

  Note that mypy has a single namespace for a class. So there can't be two
  class-level and instance-level constants with the same name.

* There must be *exactly one* assignment to a final attribute:

  .. code-block:: python

     ID = 1
     ID: Final = 2  # Error!

     class SomeCls:
         ID = 1
         ID: Final = 2  # Error!

* A final attribute declared in class body without an initializer must
  be initialized in the ``__init__`` method (you can skip the initializer
  in stub files):

  .. code-block:: python

     class SomeCls:
         x: Final[int]
         y: Final[int]  # Error: final attribute without an initializer
         def __init__(self) -> None:
             self.x = 1  # Good

* ``Final`` can be only used as an outermost type in assignments or variable
  annotations. using it in any other position is an error. In particular,
  ``Final`` can't be used in annotations for function arguments:

  .. code-block:: python

     x: List[Final[int]] = []  # Error!
     def fun(x: Final[List[int]]) ->  None:  # Error!
         ...

* ``Final`` and ``ClassVar`` should not be used together. Mypy will infer
  the scope of a final declaration automatically depending on whether it was
  initialized in the class body or in ``__init__``.

Using final attributes
**********************

As a result of a final declaration mypy strives to provide the
two following guarantees:

* A final attribute can't be re-assigned (or otherwise re-defined), both
  internally and externally:

  .. code-block:: python

     # file mod.py
     from typing_extensions import Final

     ID: Final = 1

     class SomeCls:
         ID: Final = 1

         def meth(self) -> None:
             self.ID = 2  # Error: can't assign to final attribute

     # file main.py
     import mod
     mod.ID = 2  # Error: can't assign to constant.

     from mod import ID
     ID = 2  # Also an error, see note below.

     class DerivedCls(mod.SomeCls):
         ...

     DerivedCls.ID = 2  # Error!
     obj: DerivedCls
     obj.ID = 2  # Error!

* A final attribute can't be overridden by a subclass (even with another
  explicit final declaration). Note however, that final attributes can
  override read-only properties. This also applies to multiple inheritance:

  .. code-block:: python

     class Base:
         @property
         def ID(self) -> int: ...

     class One(Base):
         ID: Final = 1  # OK

     class Other(Base):
         ID: Final = 2  # OK

     class Combo(One, Other):  # Error: cannot override final attribute.
         pass

* Declaring a name as final only guarantees that the name wll not be re-bound
  to other value, it doesn't make the value immutable. One can use immutable ABCs
  and containers to prevent mutating such values:

  .. code-block:: python

     x: Final = ['a', 'b']
     x.append('c')  # OK

     y: Final[Sequance[str]] = ['a', 'b']
     y.append('x')  # Error: Sequance is immutable
     z: Final = ('a', 'b')  # Also an option

Final methods
*************

Like with attributes, sometimes it is useful to protect a method from
overriding. In such situations one can use the ``typing_extensions.final``
decorator:

.. code-block:: python

   from typing_extensions import final

   class Base:
       @final
       def common_name(self) -> None:
           ...

   # 1000 lines later

   class Derived(Base):
       def common_name(self) -> None:  # Error: cannot override a final method
           ...

This ``@final`` decorator can be used with instance methods, class methods,
static methods, and properties (this includes overloaded methods). For
overloaded methods one should add ``@final`` on the implementation to make
it final (or on the first overload in stubs):

.. code-block:: python
   from typing import Any, overload

   class Base:
       @overload
       def meth(self) -> None: ...
       @overload
       def meth(self, arg: int) -> int: ...
       @final
       def meth(self, x=None):
           ...

Final classes
*************

You can apply a ``typing_extensions.final`` decorator to a class to indicate
to mypy that it can't be subclassed. The decorator acts as a declaration
for mypy (and as documentation for humans), but it doesn't prevent subclassing
at runtime:

.. code-block:: python

   from typing_extensions import final

   @final
   class Leaf:
       ...

   class MyLeaf(Leaf):  # Error: Leaf can't be subclassed
       ...

Here are some situations where using a final class may be useful:

* A class wasn't designed to be subclassed. Perhaps subclassing does not
  work as expected, or it's error-prone.
* You want to retain the freedom to arbitrarily change the class implementation
  in the future, and these changes might break subclasses.
* You believe that subclassing would make code harder to understand or maintain.
  For example, you may want to prevent unnecessarily tight coupling between
  base classes and subclasses.
