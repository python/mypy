.. _literal_types:

Literal types
=============

.. note::

   ``Literal`` is an officially supported feature, but is highly experimental
   and should be considered to be in alpha stage. It is very likely that future
   releases of mypy will modify the behavior of literal types, either by adding
   new features or by tuning or removing problematic ones.

Literal types let you indicate that an expression is equal to some specific
primitive value. For example, if we annotate a variable with type ``Literal["foo"]``,
mypy will understand that variable is not only of type ``str``, but is also
equal to specifically the string ``"foo"``.

This feature is primarily useful when annotating functions that behave
differently based on the exact value the caller provides. For example,
suppose we have a function ``fetch_data(...)`` that returns ``bytes`` if the
first argument is ``True``, and ``str`` if it's ``False``. We can construct a
precise type signature for this function using ``Literal[...]`` and overloads:

.. code-block:: python

    from typing import overload, Union
    from typing_extensions import Literal

    # The first two overloads use Literal[...] so we can
    # have precise return types:

    @overload
    def fetch_data(raw: Literal[True]) -> bytes: ...
    @overload
    def fetch_data(raw: Literal[False]) -> str: ...

    # The last overload is a fallback in case the caller
    # provides a regular bool:

    @overload
    def fetch_data(raw: bool) -> Union[bytes, str]: ...

    def fetch_data(raw: bool) -> Union[bytes, str]:
        # Implementation is omitted
        ...

    reveal_type(fetch_data(True))        # Revealed type is 'bytes'
    reveal_type(fetch_data(False))       # Revealed type is 'str'

    # Variables declared without annotations will continue to have an
    # inferred type of 'bool'.

    variable = True
    reveal_type(fetch_data(variable))    # Revealed type is 'Union[bytes, str]'

Parameterizing Literals
***********************

Literal types may contain one or more literal bools, ints, strs, and bytes.
However, literal types **cannot** contain arbitrary expressions:
types like ``Literal[my_string.trim()]``, ``Literal[x > 3]``, or ``Literal[3j + 4]``
are all illegal.

Literals containing two or more values are equivalent to the union of those values.
So, ``Literal[-3, b"foo", True]`` is equivalent to
``Union[Literal[-3], Literal[b"foo"], Literal[True]]``. This makes writing
more complex types involving literals a little more convenient.

Literal types may also contain ``None``. Mypy will treat ``Literal[None]`` as being
equivalent to just ``None``. This means that ``Literal[4, None]``,
``Union[Literal[4], None]``, and ``Optional[Literal[4]]`` are all equivalent.

Literals may also contain aliases to other literal types. For example, the
following program is legal:

.. code-block:: python

    PrimaryColors = Literal["red", "blue", "yellow"]
    SecondaryColors = Literal["purple", "green", "orange"]
    AllowedColors = Literal[PrimaryColors, SecondaryColors]

    def paint(color: AllowedColors) -> None: ...

    paint("red")        # Type checks!
    paint("turquoise")  # Does not type check

Literals may not contain any other kind of type or expression. This means doing
``Literal[my_instance]``, ``Literal[Any]``, ``Literal[3.14]``, or
``Literal[{"foo": 2, "bar": 5}]`` are all illegal.

Future versions of mypy may relax some of these restrictions. For example, we
plan on adding support for using enum values inside ``Literal[...]`` in an upcoming release.

Declaring literal variables
***************************

You must explicitly add an annotation to a variable to declare that it has
a literal type:

.. code-block:: python

    a: Literal[19] = 19
    reveal_type(a)          # Revealed type is 'Literal[19]'

In order to preserve backwards-compatibility, variables without this annotation
are **not** assumed to be literals:

.. code-block:: python

    b = 19
    reveal_type(b)          # Revealed type is 'int'

If you find repeating the value of the variable in the type hint to be tedious,
you can instead change the variable to be ``Final`` (see :ref:`final_attrs`):

.. code-block:: python

    from typing_extensions import Final, Literal

    def expects_literal(x: Literal[19]) -> None: pass

    c: Final = 19

    reveal_type(c)          # Revealed type is 'Literal[19]?'
    expects_literal(c)      # ...and this type checks!

If you do not provide an explicit type in the ``Final``, the type of ``c`` becomes
*context-sensitive*: mypy will basically try "substituting" the original assigned
value whenever it's used before performing type checking. This is why the revealed
type of ``c`` is ``Literal[19]?``: the question mark at the end reflects this
context-sensitive nature.

For example, mypy will type check the above program almost as if it were written like so:

.. code-block:: python

    from typing_extensions import Final, Literal

    def expects_literal(x: Literal[19]) -> None: pass

    reveal_type(19)
    expects_literal(19)

This means that while changing a variable to be ``Final`` is not quite the same thing
as adding an explicit ``Literal[...]`` annotation, it often leads to the same effect
in practice.

The main cases where the behavior of context-sensitive vs true literal types differ are
when you try using those types in places that are not explicitly expecting a ``Literal[...]``. 
For example, compare and contrast what happens when you try appending these types to a list:

.. code-block:: python

    from typing_extensions import Final, Literal

    a: Final = 19
    b: Literal[19] = 19

    # Mypy will chose to infer List[int] here.
    list_of_ints = []
    list_of_ints.append(a)
    reveal_type(list_of_ints)  # Revealed type is 'List[int]'

    # But if the variable you're appending is an explicit Literal, mypy
    # will infer List[Literal[19]].
    list_of_lits = []
    list_of_lits.append(b)
    reveal_type(list_of_lits)  # Revealed type is 'List[Literal[19]]'


Limitations
***********

Mypy will not understand expressions that use variables of type ``Literal[..]``
on a deep level. For example, if you have a variable ``a`` of type ``Literal[3]``
and another variable ``b`` of type ``Literal[5]``, mypy will infer that
``a + b`` has type ``int``, **not** type ``Literal[8]``.

The basic rule is that literal types are treated as just regular subtypes of
whatever type the parameter has. For example, ``Literal[3]`` is treated as a
subtype of ``int`` and so will inherit all of ``int``'s methods directly. This
means that ``Literal[3].__add__`` accepts the same arguments and has the same
return type as ``int.__add__``.
