.. _casts:

Casts and type assertions
=========================

Mypy supports type casts that are usually used to coerce a statically
typed value to a subtype. Unlike languages such as Java or C#,
however, mypy casts are only used as hints for the type checker, and they
don't perform a runtime type check. Use the function :py:func:`~typing.cast` to perform a
cast:

.. code-block:: python

   from typing import cast, List

   o: object = [1]
   x = cast(List[int], o)  # OK
   y = cast(List[str], o)  # OK (cast performs no actual runtime check)

To support runtime checking of casts such as the above, we'd have to check
the types of all list items, which would be very inefficient for large lists.
Casts are used to silence spurious
type checker warnings and give the type checker a little help when it can't
quite understand what is going on.

.. note::

   You can use an assertion if you want to perform an actual runtime check:

   .. code-block:: python

      def foo(o: object) -> None:
          print(o + 5)  # Error: can't add 'object' and 'int'
          assert isinstance(o, int)
          print(o + 5)  # OK: type of 'o' is 'int' here

You don't need a cast for expressions with type ``Any``, or when
assigning to a variable with type ``Any``, as was explained earlier.
You can also use ``Any`` as the cast target type -- this lets you perform
any operations on the result. For example:

.. code-block:: python

    from typing import cast, Any

    x = 1
    x.whatever()  # Type check error
    y = cast(Any, x)
    y.whatever()  # Type check OK (runtime error)


User-Defined Type Guards
************************

MyPy supports User-Defined Type Guards
(`PEP-647 <https://www.python.org/dev/peps/pep-0647/>`_).

What's a type guard?
It is a way for programs to influence conditional
type narrowing employed by a type checker based on runtime checks.

Basically, a ``TypeGuard`` is a "smart" alias for a ``bool`` type.
Let's have a look at the regular ``bool`` example:

.. code-block:: python

  from typing import List

  def is_str_list(val: List[object]) -> bool:
    """Determines whether all objects in the list are strings"""
    return all(isinstance(x, str) for x in val)

  def func1(val: List[object]) -> None:
      if is_str_list(val):
          reveal_type(val)  # List[object]
          print(" ".join(val)) # Error: invalid type

The same example with ``TypeGuard``:

.. code-block:: python

  from typing import List
  from typing import TypeGuard  # use `typing_extensions` for `python<3.10`

  def is_str_list(val: List[object]) -> TypeGuard[List[str]]:
      """Determines whether all objects in the list are strings"""
      return all(isinstance(x, str) for x in val)

  def func1(val: List[object]) -> None:
      if is_str_list(val):
          reveal_type(val)  # List[str]
          print(" ".join(val)) # ok

How does it work? ``TypeGuard`` narrows the first function argument (``val``)
to the type specified as the first type parameter (``List[str]``).

.. note::

  Narrowing is
  `not strict <https://www.python.org/dev/peps/pep-0647/#enforcing-strict-narrowing>`_.
  For example, you can narrow ``str`` to ``int``:

  .. code-block:: python

    def f(value: str) -> TypeGuard[int]:
        return True

  It was noted that without enforcing strict narrowing,
  it would be possible to break type safety.

  However, there are many ways a determined or uninformed developer can
  subvert type safety -- most commonly by using cast or Any.
  If a Python developer takes the time to learn about and implement
  user-defined type guards within their code,
  it is safe to assume that they are interested in type safety
  and will not write their type guard functions in a way
  that will undermine type safety or produce nonsensical results.

Generic TypeGuards
------------------

``TypeGuard`` can also work with generic types:

.. code-block:: python

  from typing import Tuple, TypeVar
  from typing import TypeGuard  # use `typing_extensions` for `python<3.10`

  _T = TypeVar("_T")

  def is_two_element_tuple(val: Tuple[_T, ...]) -> TypeGuard[Tuple[_T, _T]]:
      return len(val) == 2

  def func(names: Tuple[str, ...]):
      if is_two_element_tuple(names):
          reveal_type(names)  # Tuple[str, str]
      else:
          reveal_type(names)  # Tuple[str, ...]

Typeguards with parameters
--------------------------

Type guard functions can accept extra arguments:

.. code-block:: python

  from typing import Type, Set, TypeVar
  from typing import TypeGuard  # use `typing_extensions` for `python<3.10`

  _T = TypeVar("_T")

  def is_set_of(val: Set[Any], type: Type[_T]) -> TypeGuard[Set[_T]]:
      return all(isinstance(x, type) for x in val)

  items: Set[Any]
  if is_set_of(items, str):
      reveal_type(items)  # Set[str]

TypeGuards as methods
---------------------

Method can also serve as the ``TypeGuard``:

.. code-block:: python

  class StrValidator:
      def is_valid(self, instance: object) -> TypeGuard[str]:
          return isinstance(instance, str)

  def func(to_validate: object):
      if StrValidator().is_valid(to_validate):
          reveal_type(to_validate)  # Revealed type is "builtins.str"

.. note::

  Note, that ``TypeGuard``
  `does not narrow <https://www.python.org/dev/peps/pep-0647/#narrowing-of-implicit-self-and-cls-parameters>`_
  types of ``self`` or ``cls`` implicit arguments.

  If narrowing of ``self`` or ``cls`` is required,
  the value can be passed as an explicit argument to a type guard function:

  .. code-block:: python

    class Parent:
        def method(self) -> None:
            reveal_type(self)  # Revealed type is "Parent"
            if is_child(self):
                reveal_type(self)  # Revealed type is "Child"

    class Child(Parent):
        ...

    def is_child(instance: Parent) -> TypeGuard[Child]:
        return isinstance(instance, Child)
