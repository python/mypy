.. _literal_types:

Literal types
=============

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

    from typing import overload, Union, Literal

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

.. note::

    The examples in this page import ``Literal`` as well as ``Final`` and
    ``TypedDict`` from the ``typing`` module. These types were added to
    ``typing`` in Python 3.8, but are also available for use in Python 2.7
    and 3.4 - 3.7 via the ``typing_extensions`` package.

Parameterizing Literals
***********************

Literal types may contain one or more literal bools, ints, strs, bytes, and
enum values. However, literal types **cannot** contain arbitrary expressions:
types like ``Literal[my_string.trim()]``, ``Literal[x > 3]``, or ``Literal[3j + 4]``
are all illegal.

Literals containing two or more values are equivalent to the union of those values.
So, ``Literal[-3, b"foo", MyEnum.A]`` is equivalent to
``Union[Literal[-3], Literal[b"foo"], Literal[MyEnum.A]]``. This makes writing more
complex types involving literals a little more convenient.

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

    from typing import Final, Literal

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

    from typing import Final, Literal

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

    from typing import Final, Literal

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


Intelligent indexing
********************

We can use Literal types to more precisely index into structured heterogeneous
types such as tuples, NamedTuples, and TypedDicts. This feature is known as
*intelligent indexing*.

For example, when we index into a tuple using some int, the inferred type is
normally the union of the tuple item types. However, if we want just the type
corresponding to some particular index, we can use Literal types like so:

.. code-block:: python

    from typing import TypedDict

    tup = ("foo", 3.4)

    # Indexing with an int literal gives us the exact type for that index
    reveal_type(tup[0])  # Revealed type is 'str'

    # But what if we want the index to be a variable? Normally mypy won't
    # know exactly what the index is and so will return a less precise type:
    int_index = 1
    reveal_type(tup[int_index])  # Revealed type is 'Union[str, float]'

    # But if we use either Literal types or a Final int, we can gain back
    # the precision we originally had:
    lit_index: Literal[1] = 1
    fin_index: Final = 1
    reveal_type(tup[lit_index])  # Revealed type is 'str'
    reveal_type(tup[fin_index])  # Revealed type is 'str'

    # We can do the same thing with with TypedDict and str keys:
    class MyDict(TypedDict):
        name: str
        main_id: int
        backup_id: int

    d: MyDict = {"name": "Saanvi", "main_id": 111, "backup_id": 222}
    name_key: Final = "name"
    reveal_type(d[name_key])  # Revealed type is 'str'

    # You can also index using unions of literals
    id_key: Literal["main_id", "backup_id"]
    reveal_type(d[id_key])    # Revealed type is 'int' 

.. _tagged_unions:

Tagged unions
*************

When you have a union of types, you can normally discriminate between each type
in the union by using ``isinstance`` checks. For example, if you had a variable ``x`` of
type ``Union[int, str]``, you could write some code that runs only if ``x`` is an int
by doing ``if isinstance(x, int): ...``.

However, it is not always possible or convenient to do this. For example, it is not
possible to use ``isinstance`` to distinguish between two different TypedDicts since
at runtime, your variable will simply be just a dict.

Instead, what you can do is *label* or *tag* your TypedDicts with a distinct Literal
type. Then, you can discriminate between each kind of TypedDict by checking the label:

.. code-block:: python

    from typing import Literal, TypedDict, Union

    class NewJobEvent(TypedDict):
        tag: Literal["new-job"]
        job_name: str
        config_file_path: str

    class CancelJobEvent(TypedDict):
        tag: Literal["cancel-job"]
        job_id: int

    Event = Union[NewJobEvent, CancelJobEvent]

    def process_event(event: Event) -> None:
        # Since we made sure both TypedDicts have a key named 'tag', it's
        # safe to do 'event["tag"]'. This expression normally has the type
        # Literal["new-job", "cancel-job"], but the check below will narrow
        # the type to either Literal["new-job"] or Literal["cancel-job"].
        #
        # This in turns narrows the type of 'event' to either NewJobEvent 
        # or CancelJobEvent.
        if event["tag"] == "new-job":
            print(event["job_name"])
        else:
            print(event["job_id"])

While this feature is mostly useful when working with TypedDicts, you can also
use the same technique wih regular objects, tuples, or namedtuples.

Similarly, tags do not need to be specifically str Literals: they can be any type
you can normally narrow within ``if`` statements and the like. For example, you
could have your tags be int or Enum Literals or even regular classes you narrow
using ``isinstance()``:

.. code-block:: python

    from typing import Generic, TypeVar, Union

    T = TypeVar('T')

    class Wrapper(Generic[T]):
        def __init__(self, inner: T) -> None:
            self.inner = inner

    def process(w: Union[Wrapper[int], Wrapper[str]]) -> None:
        # Doing `if isinstance(w, Wrapper[int])` does not work: isinstance requires
        # that the second argument always be an *erased* type, with no generics.
        # This is because generics are a typing-only concept and do not exist at
        # runtime in a way `isinstance` can always check.
        #
        # However, we can side-step this by checking the type of `w.inner` to
        # narrow `w` itself:
        if isinstance(w.inner, int):
            reveal_type(w)  # Revealed type is 'Wrapper[int]'
        else:
            reveal_type(w)  # Revealed type is 'Wrapper[str]'

This feature is sometimes called "sum types" or "discriminated union types"
in other programming languages.

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
