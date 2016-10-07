.. _common_issues:

Dealing with common issues
==========================

Statically typed function bodies are often identical to normal Python
code, but sometimes you need to do things slightly differently. This
section has examples of cases when you need to update your code
to use static typing, and ideas for working
around issues if the type checker gets confused about your code.

.. _silencing_checker:

Spurious errors and locally silencing the checker
-------------------------------------------------

You can use a ``# type: ignore`` comment to silence the type checker
on a particular line. For example, let's say our code is using
the C extension module ``frobnicate``, and there's no stub available.
Mypy will complain about this, as it has no information about the
module:

.. code-block:: python

    import frobnicate  # Error: No module "frobnicate"
    frobnicate.start()

You can add a ``# type: ignore`` comment to tell mypy to ignore this
error:

.. code-block:: python

    import frobnicate  # type: ignore
    frobnicate.start()  # Okay!

The second line is now fine, since the ignore comment causes the name
``frobnicate`` to get an implicit ``Any`` type.

.. note::

    The ``# type: ignore`` comment will only assign the implicit ``Any``
    type if mypy cannot find information about that particular module. So,
    if we did have a stub available for ``frobnicate`` then mypy would
    ignore the ``# type: ignore`` comment and typecheck the stub as usual.

Types of empty collections
--------------------------

You often need to specify the type when you assign an empty list or
dict to a new variable, as mentioned earlier:

.. code-block:: python

   a = []  # type: List[int]

Without the annotation mypy can't always figure out the
precise type of ``a``.

You can use a simple empty list literal in a dynamically typed function (as the
type of ``a`` would be implicitly ``Any`` and need not be inferred), if type
of the variable has been declared or inferred before, or if you perform a simple
modification operation in the same scope (such as ``append`` for a list):

.. code-block:: python

   a = []  # Okay because followed by append, inferred type List[int]
   for i in range(n):
       a.append(i * i)

However, in more complex cases an explicit type annotation can be
required (mypy will tell you this). Often the annotation can
make your code easier to understand, so it doesn't only help mypy but
everybody who is reading the code!

Redefinitions with incompatible types
-------------------------------------

Each name within a function only has a single 'declared' type. You can
reuse for loop indices etc., but if you want to use a variable with
multiple types within a single function, you may need to declare it
with the ``Any`` type.

.. code-block:: python

   def f() -> None:
       n = 1
       ...
       n = 'x'        # Type error: n has type int

.. note::

   This limitation could be lifted in a future mypy
   release.

Note that you can redefine a variable with a more *precise* or a more
concrete type. For example, you can redefine a sequence (which does
not support ``sort()``) as a list and sort it in-place:

.. code-block:: python

    def f(x: Sequence[int]) -> None:
        # Type of x is Sequence[int] here; we don't know the concrete type.
        x = list(x)
        # Type of x is List[int] here.
        x.sort()  # Okay!

Declaring a supertype as variable type
--------------------------------------

Sometimes the inferred type is a subtype (subclass) of the desired
type. The type inference uses the first assignment to infer the type
of a name (assume here that ``Shape`` is the base class of both
``Circle`` and ``Triangle``):

.. code-block:: python

   shape = Circle()    # Infer shape to be Circle
   ...
   shape = Triangle()  # Type error: Triangle is not a Circle

You can just give an explicit type for the variable in cases such the
above example:

.. code-block:: python

   shape = Circle() # type: Shape   # The variable s can be any Shape,
                                    # not just Circle
   ...
   shape = Triangle()               # OK

Complex type tests
------------------

Mypy can usually infer the types correctly when using ``isinstance()``
type tests, but for other kinds of checks you may need to add an
explicit type cast:

.. code-block:: python

   def f(o: object) -> None:
       if type(o) is int:
           o = cast(int, o)
           g(o + 1)    # This would be an error without the cast
           ...
       else:
           ...

.. note::

    Note that the ``object`` type used in the above example is similar
    to ``Object`` in Java: it only supports operations defined for *all*
    objects, such as equality and ``isinstance()``. The type ``Any``,
    in contrast, supports all operations, even if they may fail at
    runtime. The cast above would have been unnecessary if the type of
    ``o`` was ``Any``.

Mypy can't infer the type of ``o`` after the ``type()`` check
because it only knows about ``isinstance()`` (and the latter is better
style anyway).  We can write the above code without a cast by using
``isinstance()``:

.. code-block:: python

   def f(o: object) -> None:
       if isinstance(o, int):  # Mypy understands isinstance checks
           g(o + 1)        # Okay; type of o is inferred as int here
           ...

Type inference in mypy is designed to work well in common cases, to be
predictable and to let the type checker give useful error
messages. More powerful type inference strategies often have complex
and difficult-to-predict failure modes and could result in very
confusing error messages. The tradeoff is that you as a programmer
sometimes have to give the type checker a little help.

.. _version_and_platform_checks:

Python version and system platform checks
-----------------------------------------

Mypy supports the ability to perform Python version checks and platform
checks (e.g. Windows vs Posix), ignoring code paths that won't be run on
the targeted Python version or platform. This allows you to more effectively
typecheck code that supports multiple versions of Python or multiple operating
systems.

More specifically, mypy will understand the use of ``sys.version_info`` and
``sys.platform`` checks within ``if/elif/else`` statements. For example:

.. code-block:: python

   import sys

   # Distinguishing between different versions of Python:
   if sys.version_info >= (3, 5):
       # Python 3.5+ specific definitions and imports
   elif sys.version_info[0] >= 3:
       # Python 3 specific definitions and imports
   else:
       # Python 2 specific definitions and imports

   # Distinguishing between different operating systems:
   if sys.platform.startswith("linux"):
       # Linux-specific code
   elif sys.platform == "darwin":
       # Mac-specific code
   elif sys.platform == "win32":
       # Windows-specific code
   else:
       # Other systems

.. note::

   Mypy currently does not support more complex checks, and does not assign
   any special meaning when assigning a ``sys.version_info`` or ``sys.platform``
   check to a variable. This may change in future versions of mypy.

By default, mypy will use your current version of Python and your current
operating system as default values for ``sys.version_info`` and
``sys.platform``.

To target a different Python version, use the ``--python-version X.Y`` flag.
For example, to verify your code typechecks if were run using Python 2, pass
in ``--python-version 2.7`` from the command line. Note that you do not need
to have Python 2.7 installed to perform this check.

To target a different operating system, use the ``--platform PLATFORM`` flag.
For example, to verify your code typechecks if it were run in Windows, pass
in ``--platform win32``. See the documentation for
`sys.platform <https://docs.python.org/3/library/sys.html#sys.platform>`_
for examples of valid platform parameters.

.. _reveal-type:

Displaying the type of an expression
------------------------------------

You can use ``reveal_type(expr)`` to ask mypy to display the inferred
static type of an expression. This can be useful when you don't quite
understand how mypy handles a particlar piece of code. Example:

.. code-block:: python

   reveal_type((1, 'hello'))  # Revealed type is 'Tuple[builtins.int, builtins.str]'

.. note::

   ``reveal_type`` is only understood by mypy and doesn't exist
   in Python, if you try to run your program. You'll have to remove
   any ``reveal_type`` calls before you can run your code.
   ``reveal_type`` is always available and you don't need to import it.

.. _import-cycles:

Import cycles
-------------

An import cycle occurs where module A imports module B and module B
imports module A (perhaps indirectly, e.g. ``A -> B -> C -> A``).
Sometimes in order to add type annotations you have to add extra
imports to a module and those imports cause cycles that didn't exist
before.  If those cycles become a problem when running your program,
there's a trick: if the import is only needed for type annotations in
forward references (string literals) or comments, you can write the
imports inside ``if TYPE_CHECKING:`` so that they are not executed at runtime.
Example:

File ``foo.py``:

.. code-block:: python

   from typing import List, TYPE_CHECKING

   if TYPE_CHECKING:
       import bar

   def listify(arg: 'bar.BarClass') -> 'List[bar.BarClass]':
       return [arg]

File ``bar.py``:

.. code-block:: python

   from typing import List
   from foo import listify

   class BarClass:
       def listifyme(self) -> 'List[BarClass]':
           return listify(self)

.. note::

   The ``TYPE_CHECKING`` constant defined by the ``typing`` module
   is ``False`` at runtime but ``True`` while type checking.
