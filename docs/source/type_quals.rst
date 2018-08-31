Type qualifiers
===============

This section describes constructs that do not affect types of variables
and methods, but affect how they can be accessed, assigned, and overridden.

Class and instance variables
****************************

By default mypy assumes that a variable declared in the class body is
an instance variable. One can mark names intended to be used as class variables
with a special type qualifier ``typing.ClassVar``. For example:

.. code-block:: python

   from typing import ClassVar

   class Base:
       attr: int  # This is an instance variable
       num_subclasses: ClassVar[int]  # This is a class variable

       def foo(self) -> None:
           self.attr = 0  # OK
           self.num_subclasses = 0  # Error: Cannot assign to class variable via instance

   Base.num_subclasses = 0  # OK
   Base.attr = 0  # Also OK, sets default value for an instance variable

Note that ``ClassVar`` is not valid as a nested type, and in any position
other than assignment in class body. For example:

.. code-block:: python

   x: ClassVar[int]  # Error: ClassVar can't be used at module scope

   class C:
       y: List[ClassVar[int]]  # Error: can't use ClassVar as nested type

Instance variable can not override a class variable in a subclass
and vice-versa:

.. code-block:: python

   class Base:
       x: int
       y: ClassVar[int]

   class Derived(Base):
        x: ClassVar[int]  # Error!
        y: int  # Error!

.. note::

   Assigning a value to a variable in the class body doesn't make it a class
   variable, it just sets a default value for an instance variable, *only*
   names explicitly declared with ``ClassVar`` are class variables.

Final attributes of classes and modules
***************************************

.. note::

   This is an experimental feature. Some details might change in later
   versions of mypy. The final qualifiers are available in ``typing_extensions``
   module. When the semantics is stable, they will be added to ``typing``.

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

Some other use cases might be solved by using ``@property``, but note that both
above use cases can't be solved this way. For such situations, one might want
to use ``typing_extensions.Final``.

Definition syntax
-----------------

The ``typing_extensions.Final`` type qualifier indicates that a given name or
attribute should never be re-assigned, re-defined, nor overridden. It can be
used in one of these forms:

* The simplest one is ``ID: Final = 1``. Note that unlike gor generic classes
  this is *not* the same as ``Final[Any]``. Here mypy will infer type ``int``.

* An explicit type ``ID: Final[float] = 1`` can be used as in any
  normal assignment.

* In stub files one can omit the right hand side and just write
  ``ID: Final[float]``.

* Finally, one can define ``self.id: Final = 1`` (also with a type argument),
  but this is allowed *only* in ``__init__`` methods.

Definition rules
----------------

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

* A final attribute declared in class body without r.h.s. must be initialized
  in the ``__init__`` method (one can skip initializer in stub files):

  .. code-block:: python

     class SomeCls:
         x: Final
         y: Final  # Error: final attribute without an initializer
         def __init__(self) -> None:
             self.x = 1  # Good

* ``Final`` can be only used as an outermost type in assignments, using it in
  any other position is an error. In particular, ``Final`` can't be used in
  annotations for function arguments because this may cause confusions about
  what are the guarantees in this case:

  .. code-block:: python

     x: List[Final[int]] = []  # Error!
     def fun(x: Final[List[int]]) ->  None:  # Error!
         ...

* ``Final`` and ``ClassVar`` should not be used together, mypy will infer
  the scope of a final declaration automatically depending on whether it was
  initialized in class body or in ``__init__``.

.. note::
   Conditional final declarations and final declarations within loops are
   not supported.

Using final attributes
----------------------

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
  override normal attributes. This also applies to multiple inheritance:

  .. code-block:: python

     class Base:
         ID = 0

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

.. note::

   Mypy treats re-exported final names as final. In other words, once declared,
   the final status can't be "stripped". Such behaviour is typically desired
   for larger libraries where constants are defined in a separate module and
   then re-exported.

Final methods
-------------

Like with attributes, sometimes it is useful to protect a method from
overriding. In such situations one can use a ``typing_extensions.final``
decorator:

.. code-block:: python

   from typing_extensions import final

   class Base:
       @final
       def common_name(self) -> None:
           ...

   # 1000 lines later

   class Derived(Base):
       def common_name(self) -> None:  # Error: this overriding might break
                                       # invariants in the base class.
           ...

This ``@final`` decorator can be used with instance methods, class methods,
static methods, and properties (this includes overloaded methods). For overloaded
methods it is enough to add ``@final`` on at leats one of overloads (or on
the implementation) to make it final:

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

    class Derived(Base):
        def meth(self, x: Any = None) -> Any:  # Error: can't override final method
            ...

Final classes
-------------

As a bonus, applying a ``typing_extensions.final`` decorator to a class indicates to mypy
that it can't be subclassed. Mypy doesn't provide any additional features for
final classes, but some other tools may use this information for their benefits.
Plus it serves a verifiable documentation purpose:

.. code-block:: python

   # file lib.pyi
   from typing_extensions import final

   @final
   class Leaf:
       ...

   # file main.py
   from lib import Leaf

   class MyLeaf(Leaf):  # Error: library author believes this is unsafe
       ...

Some situations where this may be useful include:

* A class wasn't designed to be subclassed. Perhaps subclassing does not
  work as expected, or it's error-prone.
* You want to retain the freedom to arbitrarily change the class implementation
  in the future, and these changes might break subclasses.
* You believe that subclassing would make code harder to understand or maintain.
  For example, you may want to prevent unnecessarily tight coupling between
  base classes and subclasses.
