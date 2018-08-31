Type qualifiers
===============

This section describes constructs that do not affect types of variables
and methods, but affect how they can be accessed, assigned, and overridden.

Class and instance variables
****************************

By default mypy assumes that a variable declared in the class body is
an instance variable. One can mark names intended to be used as class variables
with a special type qualifier ``ClassVar``. For example:

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


Final attributes of classes and modules
***************************************

.. note::

   This is an experimental feature. Some details might change in later
   versions of mypy. The final qualifiers are available in ``typing_extensions``
   module. When the semantics is stable, they will be added to ``typing``.

There are several situations where static guarantees about non-redefinition
of certain names (or references in general) can be useful. One such example
is module or class level constants, user might want to guard them against
unintentional modifications:

.. code-block:: python

   RATE = 3000

   class Base:
       DEFAULT_ID = 0

   # 1000 lines later

   class Derived(Base):
       DEFAULT_ID = 1  # this may be unintentional

   RATE = 300  # this too

Another example is where a user might want to protect certain instance
attributes from overriding in a subclass:

.. code-block:: python

   import uuid

   class Snowflake:
       """An absolutely unique object in the database"""
       def __init__(self) -> None:
           self.id = uuid.uuid4()

   # 1000 lines later

   class User(Snowflake):
       id = uuid.uuid4()  # This has valid type, but the meaning
                          # may be wrong

Some other use cases might be solved by using ``@property``, but note that both
above use cases can't be solved this way. For such situations, one might want
to use ``typing.Final``.

Definition syntax
-----------------

The ``typing.Final`` type qualifier indicates that a given name or attribute
should never be re-assigned, re-defined, nor overridden. It can be used in
one of these forms:

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

     ID: Final = 1
     ID: Final = 2  # Error!

     class SomeCls:
         id: Final = 1
         def __init__(self, x: int) -> None:
             self.id: Final = x  # Error!

  Note that mypy has a single namespace for a class. So there can't be two
  class-level and instance-level constants with the same name.

* There must be *exactly one* assignment to a final attribute:

  .. code-block:: python

     ID = 1
     ID: Final = 2  # Error!

     class SomeCls:
         ID = 1
         ID: Final = 2  # Error!

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
     from typing import Final

     ID: Final = 1

     # file main.py
     from typing import Final

     import mod
     mod.ID = 2  # Error, can't assign to constant.

     class SomeCls:
         ID: Final = 1

         def meth(self) -> None:
             self.ID = 2  # Error, can't assign to final attribute

     class DerivedCls(SomeCls):
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

     class Combo(One, Other):  # Error, cannot override final attribute.
         pass

.. note::

   Mypy treats re-exported final names as final. In other words, once declared,
   the final status can't be "stripped". Such behaviour is typically desired
   for larger libraries where constants are defined in a separate module and
   then re-exported.

Final methods
-------------

Like with attributes, sometimes it is useful to protect a method from
overriding. In such situations one can use a ``typing.final`` decorator:

.. code-block:: python

   from typing import final

   class Base:
       @final
       def common_name(self) -> None:  # common signature
           ...

   # 1000 lines later

   class Derived(Base):
       def common_name(self) -> None:  # Error, this overriding might break
                                       # invariants in the base class.
           ...

This ``@final`` decorator can be used with instance methods, class methods,
static methods, and properties (this includes overloaded methods).

Final classes
-------------

As a bonus, applying a ``typing.final`` decorator to a class indicates to mypy
that it can't be subclassed. Mypy doesn't provide any additional features for
final classes, but some other tools may use this information for their benefits.
Plus it serves a verifiable documentation purpose:

.. code-block:: python

   # file lib.pyi
   from typing import final

   @final
   class Leaf:
       ...

   # file main.py
   from lib import Leaf

   class MyLeaf(Leaf):  # Error, library author believes this is unsafe
       ...
