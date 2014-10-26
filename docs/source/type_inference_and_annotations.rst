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
target. In this case this is l, which has the type List[object]. The
value expression [1, 2] is type checked in this context and given the
type List[object]. In the previous example we introduced a new
variable l, and here the type context was empty.

Note that the following is not valid, since List[int] is not
compatible with List[object]:

.. code-block:: python

   def f(l: List[object], k: List[int]) -> None:
       l = k       # Type check error: incompatible types in assignment

The reason why the above assignment is disallowed is that allowing the
assignment could result in non-int values stored in a list of int:

.. code-block:: python

   def f(l: List[object], k: List[int]) -> None:
       l = k
       l.append('x')
       print(k[-1])  # Ouch; a string in List[int]

You can still run the above program; it prints x. This illustrates the
fact that static types are used during type checking, but they do not
affect the runtime behavior of programs. You can run programs with
type check failures, which is often very handy when performing a large
refactoring. Thus you can always 'work around' the type system, and it
doesn't really limit what you can do in your program.

Type inference is not used in dynamically typed functions (those
without an explicit return type) — every local variable type defaults
to Any, which is discussed below.

Explicit types for collections
******************************

The type checker cannot always infer the type of a list or a
dictionary. This often arises when creating an empty list or
dictionary and assigning it to a new variable without an explicit
variable type. In these cases you can give the type explicitly using
the type name as a constructor:

.. code-block:: python

   l = List[int]()       # Create empty list with type List[int]
   d = Dict[str, int]()  # Create empty dictionary (str -> int)

Similarly, you can also give an explicit type when creating an empty set:

.. code-block:: python

   s = Set[int]()

Explicit types for variables
****************************

.. code-block:: python

   s = Undefined(str)   # Declare type of x to be str.
   s = 'x'              # OK
   s = 1                # Type check error

The Undefined call evaluates to a special "Undefined" object that
raises an exception on any operation:

.. code-block:: python

   s = Undefined(str)
   if s:                # Runtime error: undefined value
       print('hello')

You can also override the inferred type of a variable by using a
special comment after an assignment statement:

.. code-block:: python

   x = [] # type: List[int]

Here the # type comment applies both to the assignment target, in this
case x, and also the initializer expression, via context. The above
code is equivalent to this:

.. code-block:: python

   x = List[int]()

The type checker infers the value of a variable from the initializer,
and if it is an empty collection such as [], the type is not
well-defined. You can declare the collection type using one of the
above syntax alternatives.

Declaring multiple variable types on a line
*******************************************

You can declare more than a single variable at a time. In order to
nicely work with multiple assignment, you must give each variable a
type separately:

.. code-block:: python

   n, s = Undefined(int), Undefined(str)  # Declare an integer and a string
   i, found = 0, False # type: int, bool

When using the latter form, you can optinally use parentheses around
the types, assignment targets and assigned expression:

.. code-block:: python

   i, found = 0, False # type: (int, bool)      # OK
   (i, found) = 0, False # type: int, bool      # OK
   i, found = (0, False) # type: int, bool      # OK
   (i, found) = (0, False) # type: (int, bool)  # OK
