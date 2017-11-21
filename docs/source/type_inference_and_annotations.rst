Type inference and type annotations
===================================

Type inference
**************

The initial assignment defines a variable. If you do not explicitly
specify the type of the variable, mypy infers the type based on the
static type of the value expression:

.. code-block:: python

   i = 1           # Infer type int for i
   l = [1, 2]      # Infer type List[int] for l

Type inference is bidirectional and takes context into account. For
example, the following is valid:

.. code-block:: python

   def f(l: List[object]) -> None:
       l = [1, 2]  # Infer type List[object] for [1, 2]

In an assignment, the type context is determined by the assignment
target. In this case this is ``l``, which has the type
``List[object]``. The value expression ``[1, 2]`` is type checked in
this context and given the type ``List[object]``. In the previous
example we introduced a new variable ``l``, and here the type context
was empty.

Note that the following is not valid, since ``List[int]`` is not
compatible with ``List[object]``:

.. code-block:: python

   def f(l: List[object], k: List[int]) -> None:
       l = k       # Type check error: incompatible types in assignment

The reason why the above assignment is disallowed is that allowing the
assignment could result in non-int values stored in a list of ``int``:

.. code-block:: python

   def f(l: List[object], k: List[int]) -> None:
       l = k
       l.append('x')
       print(k[-1])  # Ouch; a string in List[int]

You can still run the above program; it prints ``x``. This illustrates
the fact that static types are used during type checking, but they do
not affect the runtime behavior of programs. You can run programs with
type check failures, which is often very handy when performing a large
refactoring. Thus you can always 'work around' the type system, and it
doesn't really limit what you can do in your program.

Type inference is not used in dynamically typed functions (those
without an explicit return type) — every local variable type defaults
to ``Any``, which is discussed later.

Explicit types for variables
****************************

You can override the inferred type of a variable by using a
special type comment after an assignment statement:

.. code-block:: python

   x = 1  # type: Union[int, str]

Without the type comment, the type of ``x`` would be just ``int``. We
use an annotation to give it a more general type ``Union[int, str]``.
Mypy checks that the type of the initializer is compatible with the
declared type. The following example is not valid, since the initializer is
a floating point number, and this is incompatible with the declared
type:

.. code-block:: python

   x = 1.1  # type: Union[int, str]  # Error!

Python 3.6 introduced a new syntax for variable annotations, which
resembles function annotations:

.. code-block:: python

   x: Union[int, str] = 1

We'll use both syntax variants in examples. The syntax variants are
mostly interchangeable, but the Python 3.6 syntax allows defining the
type of a variable without initialization, which is not possible with
the comment-based syntax:

.. code-block:: python

   x: str  # Declare type of 'x' without initialization

.. note::

   The best way to think about this is that the type comment sets the
   type of the variable, not the type of the expression. To force the
   type of an expression you can use ``cast(<type>, <expression>)``.

Explicit types for collections
******************************

The type checker cannot always infer the type of a list or a
dictionary. This often arises when creating an empty list or
dictionary and assigning it to a new variable that doesn't have an explicit
variable type. In these cases you can give the type explicitly using
a type annotation comment:

.. code-block:: python

   l = []  # type: List[int]       # Create empty list with type List[int]
   d = {}  # type: Dict[str, int]  # Create empty dictionary (str -> int)

Similarly, you can also give an explicit type when creating an empty set:

.. code-block:: python

   s = set()  # type: Set[int]

Declaring multiple variable types at a time
*******************************************

You can declare more than a single variable at a time. In order to
nicely work with multiple assignment, you must give each variable a
type separately:

.. code-block:: python

   i, found = 0, False # type: int, bool

You can optionally use parentheses around the types, assignment targets
and assigned expression:

.. code-block:: python

   i, found = 0, False # type: (int, bool)      # OK
   (i, found) = 0, False # type: int, bool      # OK
   i, found = (0, False) # type: int, bool      # OK
   (i, found) = (0, False) # type: (int, bool)  # OK

Starred expressions
*******************

In most cases, mypy can infer the type of starred expressions from the
right-hand side of an assignment, but not always:

.. code-block:: python

    a, *bs = 1, 2, 3   # OK
    p, q, *rs = 1, 2   # Error: Type of rs cannot be inferred

On first line, the type of ``bs`` is inferred to be
``List[int]``. However, on the second line, mypy cannot infer the type
of ``rs``, because there is no right-hand side value for ``rs`` to
infer the type from. In cases like these, the starred expression needs
to be annotated with a starred type:

.. code-block:: python

    p, q, *rs = 1, 2  # type: int, int, *List[int]

Here, the type of ``rs`` is set to ``List[int]``.

Types in stub files
*******************

:ref:`Stub files <library-stubs>` are written in normal Python 3
syntax, but generally leaving out runtime logic like variable
initializers, function bodies, and default arguments, replacing them
with ellipses.

In this example, each ellipsis ``...`` is literally written in the
stub file as three dots:

.. code-block:: python

    x = ...  # type: int
    def afunc(code: str) -> int: ...
    def afunc(a: int, b: int=...) -> int: ...

.. note::

    The ellipsis ``...`` is also used with a different meaning in
    :ref:`callable types <callable-types>` and :ref:`tuple types
    <tuple-types>`.
