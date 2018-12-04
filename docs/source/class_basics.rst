Class basics
============

This section will help get you started annotating your
classes. Built-in classes such as ``int`` also follow these same
rules.

Instance and class attributes
*****************************

The mypy type checker detects if you are trying to access a missing
attribute, which is a very common programming error. For this to work
correctly, instance and class attributes must be defined or
initialized within the class. Mypy infers the types of attributes:

.. code-block:: python

   class A:
       def __init__(self, x: int) -> None:
           self.x = x  # Aha, attribute 'x' of type 'int'

   a = A(1)
   a.x = 2  # OK!
   a.y = 3  # Error: 'A' has no attribute 'y'

This is a bit like each class having an implicitly defined
``__slots__`` attribute. This is only enforced during type
checking and not when your program is running.

You can declare types of variables in the class body explicitly using
a type annotation:

.. code-block:: python

   class A:
       x: List[int]  # Declare attribute 'x' of type List[int]

   a = A()
   a.x = [1]     # OK

As in Python generally, a variable defined in the class body can be used
as a class or an instance variable. (As discussed in the next section, you
can override this with a ``ClassVar`` annotation.)

Type comments work as well, if you need to support Python versions earlier
than 3.6:

.. code-block:: python

   class A:
       x = None  # type: List[int]  # Declare attribute 'x' of type List[int]

Note that attribute definitions in the class body that use a type comment
are special: a ``None`` value is valid as the initializer, even though
the declared type is not optional. This should be used sparingly, as this can
result in ``None``-related runtime errors that mypy can't detect.

Similarly, you can give explicit types to instance variables defined
in a method:

.. code-block:: python

   class A:
       def __init__(self) -> None:
           self.x: List[int] = []

       def f(self) -> None:
           self.y: Any = 0

You can only define an instance variable within a method if you assign
to it explicitly using ``self``:

.. code-block:: python

   class A:
       def __init__(self) -> None:
           self.y = 1   # Define 'y'
           a = self
           a.x = 1      # Error: 'x' not defined

Annotating `__init__` methods
*****************************

The ``__init__`` method is somewhat special -- it doesn't return a
value.  This is best expressed as ``-> None``.  However, since many feel
this is redundant, it is allowed to omit the return type declaration
on ``__init__`` methods **if at least one argument is annotated**.  For
example, in the following classes ``__init__`` is considered fully
annotated:

.. code-block:: python

   class C1:
       def __init__(self) -> None:
           self.var = 42

   class C2:
       def __init__(self, arg: int):
           self.var = arg

However, if ``__init__`` has no annotated arguments and no return type
annotation, it is considered an untyped method:

.. code-block:: python

   class C3:
       def __init__(self):
           # This body is not type checked
           self.var = 42 + 'abc'

Class attribute annotations
***************************

You can use a ``ClassVar[t]`` annotation to explicitly declare that a
particular attribute should not be set on instances:

.. code-block:: python

  from typing import ClassVar

  class A:
      x: ClassVar[int] = 0  # Class variable only

  A.x += 1  # OK

  a = A()
  a.x = 1  # Error: Cannot assign to class variable "x" via instance
  print(a.x)  # OK -- can be read through an instance

.. note::

   If you need to support Python 3 versions 3.5.2 or earlier, you have
   to import ``ClassVar`` from ``typing_extensions`` instead (available on
   PyPI). If you use Python 2.7, you can import it from ``typing``.

It's not necessary to annotate all class variables using
``ClassVar``. An attribute without the ``ClassVar`` annotation can
still be used as a class variable. However, mypy won't prevent it from
being used as an instance variable, as discussed previously:

.. code-block:: python

  class A:
      x = 0  # Can be used as a class or instance variable

  A.x += 1  # OK

  a = A()
  a.x = 1  # Also OK

Note that ``ClassVar`` is not a class, and you can't use it with
``isinstance()`` or ``issubclass()``. It does not change Python
runtime behavior -- it's only for type checkers such as mypy (and
also helpful for human readers).

You can also omit the square brackets and the variable type in
a ``ClassVar`` annotation, but this might not do what you'd expect:

.. code-block:: python

   class A:
       y: ClassVar = 0  # Type implicitly Any!

In this case the type of the attribute will be implicitly ``Any``.
This behavior will change in the future, since it's surprising.

.. note::
   A ``ClassVar`` type parameter cannot include type variables:
   ``ClassVar[T]`` and ``ClassVar[List[T]]``
   are both invalid if ``T`` is a type variable (see :ref:`generic-classes`
   for more about type variables).

Overriding statically typed methods
***********************************

When overriding a statically typed method, mypy checks that the
override has a compatible signature:

.. code-block:: python

   class A:
       def f(self, x: int) -> None:
           ...

   class B(A):
       def f(self, x: str) -> None:   # Error: type of 'x' incompatible
           ...

   class C(A):
       def f(self, x: int, y: int) -> None:  # Error: too many arguments
           ...

   class D(A):
       def f(self, x: int) -> None:   # OK
           ...

.. note::

   You can also vary return types **covariantly** in overriding. For
   example, you could override the return type ``object`` with a subtype
   such as ``int``. Similarly, you can vary argument types
   **contravariantly** -- subclasses can have more general argument types.

You can also override a statically typed method with a dynamically
typed one. This allows dynamically typed code to override methods
defined in library classes without worrying about their type
signatures.

As always, relying on dynamically typed code can be unsafe. There is no
runtime enforcement that the method override returns a value that is
compatible with the original return type, since annotations have no
effect at runtime:

.. code-block:: python

   class A:
       def inc(self, x: int) -> int:
           return x + 1

   class B(A):
       def inc(self, x):   # Override, dynamically typed
           return 'hello'  # Incompatible with 'A', but no mypy error

Abstract base classes and multiple inheritance
**********************************************

Mypy supports Python abstract base classes (ABCs). Abstract classes
have at least one abstract method or property that must be implemented
by a subclass. You can define abstract base classes using the
``abc.ABCMeta`` metaclass, and the ``abc.abstractmethod`` and
``abc.abstractproperty`` function decorators. Example:

.. code-block:: python

   from abc import ABCMeta, abstractmethod

   class A(metaclass=ABCMeta):
       @abstractmethod
       def foo(self, x: int) -> None: pass

       @abstractmethod
       def bar(self) -> str: pass

   class B(A):
       def foo(self, x: int) -> None: ...
       def bar(self) -> str:
           return 'x'

   a = A()  # Error: 'A' is abstract
   b = B()  # OK

Note that mypy performs checking for unimplemented abstract methods
even if you omit the ``ABCMeta`` metaclass. This can be useful if the
metaclass would cause runtime metaclass conflicts.

A class can inherit any number of classes, both abstract and
concrete. As with normal overrides, a dynamically typed method can
implement a statically typed method defined in any base class,
including an abstract method defined in an abstract base class.

You can implement an abstract property using either a normal
property or an instance variable.
