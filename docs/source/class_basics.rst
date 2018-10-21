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
as a class or an instance variable.

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

Class attribute annotations
***************************

Mypy supports annotations for class and instance
variables in class bodies and methods. Use ``ClassVar`` to
indicate to the static type checker that this variable
should not be set on instances.

A class attribute without the ``ClassVar`` annotation can be used as
a class variable. Mypy won't prevent it from being used as an
instance variable.

.. code-block:: python

  class A:
      y: ClassVar[Dict[str, int]] = {}  # class variable
      z: int = 10                       # instance variable

The following are worth noting about ``ClassVar``:

- It accepts only types and cannot be further subscribed.

- It is not a class itself, and should not be used with
  isinstance() or issubclass().

- It does not change Python runtime behavior, but it can
  be used by third-party type checkers. For example, a type checker
  might flag the following code as an error:

.. code-block:: python

  a = A(3000)
  a.y = {}                # Error, setting class variable on instance
  a.z = {}                # This is OK


Also `` y: ClassVar = 0 `` is valid (without square brackets). The type of
the variable will be implicitly ``Any``. This behavior will change in the future.

.. note::
   A ``ClassVar`` parameter cannot include any type variables,
   regardless of the level of nesting: ``ClassVar[T]`` and ``ClassVar[List[Set[T]]]``
   are both invalid if ``T`` is a type variable.

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
