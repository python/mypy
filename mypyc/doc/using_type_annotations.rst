Using type annotations
======================

You will get most out of mypyc when compiling code that has precise
type annotations. Not all type annotations will help code performance
as much. Using primitive types, native classes, trait types, and tuple
types as much as possible is the key to major performance gains over
CPython.

In contrast, other types, including ``Any``, are treated as *erased
types*.  Operations on erased types use generic operations that work
with arbitrary objects, similar to how the CPython interpreter works. If
you only use erased types, the only notable performance benefit over
CPython will be the removal of interpreter overhead (from
compilation), which will usually only give minor performance gains.

Primitive types
---------------

The following built-in types are treated as *primitive types* by
mypyc, and many operations on these types have efficient
implementations:

* ``int``
* ``float``
* ``bool``
* ``str``
* ``List[T]``
* ``Dict[K, V]``
* ``Set[T]``
* ``Tuple[T, ...]`` (variable-length tuple)
* ``None``

Elsewhere in this document we will list all supported native,
optimized operations for these primitive types. You can use all
operations supported by Python, but only *native operations* will have
custom, optimized implementations.

Integers
********

TODO: integers

Booleans
********

TODO: booleans

Primitive containers
********************

TODO: talk about boxing/unboxing story

Native classes
--------------

Classes that get compiled to C extensions are called native
classes. Most operations on instances of these classes are optimized,
including construction, attribute access and method calls.

Native class definitions look exactly like normal Python class
definitions.  A class is usually native if it's in a compiled module
(though there are some exceptions).

Consider this example:

.. code-block::

   class Point:
       def __init__(self, x: int, y: int) -> int:
           self.x = x
           self.y = y

   def shift(p: Point) -> Point:
       return Point(p.x + 1, p.y + 1)

All operations in the above example use native operations, if the file
is compiled.

Native classes have some notable different from Python classes:

* Only attributes and methods defined in the class body or methods are
  supported.  If you try to assign to an undefined attribute outside
  the class definition, ``AttributeError`` will be raised. This enables
  an efficient memory layout and fast method calls for native classes.

* Native classes usually don't define the ``__dict__`` attribute (they
  don't have an attribute dictionary). This follows from only having
  a specific set of attributes.

* Native classes can't have a metaclass or use most class decorators.

Native classes only support single inheritance. A limited form of
multiple inheritance is supported through *trait types*. You generally
must inherit from another native class (or ``object``).

Tuple types
-----------

Fixed-length tuple types such as ``Tuple[int, str]`` are represented
as *value types* when stored in variables, passed as arguments, or
returned from functions. Value types are allocated in the low-level
machine stack or in CPU registers, as opposed to *heap types*, which
are allocated dynamically from the heap.

Like all value types, tuples will be *boxed*, i.e. converted to
corresponding heap types, when stored in Python containers, or passed
to non-native code. A boxed tuple value will be a regular Python tuple
object.

Union types
-----------

Union types that contain primitive types, native class types and
trait types are also efficient. If a union type has erased items
(see below for more), accessing items with non-erased types is often
still quite efficient.

A value with a union types is always boxed, even if it contains a
value that also has an unboxed representation, such as an integer or a
boolean.

For example, using ``Optional[int]`` is quite efficient, but the value
will always be boxed. A plain ``int`` value will usually be faster, since
it has an unboxed representation.

Trait types
-----------

Trait types enable a form of multiple inheritance for native classes.

TODO: explain

Erased types
------------

Mypyc supports many other kinds of types as well, beyond those
describes above.  However, these types don't have efficient customized
operations, and they are implemented using *type erasure*.  Type
erasure means that all other types are equivalent to untyped values at
runtime, i.e. they have the equivalent of the type ``Any``. Erased
types include these:

* Python classes (including built-in types that are not primitives, and ABCs)
* Callable types
* Type variable types
* The type ``Any``

Using erased types can still improve performance, since they can enable
effective types to be inferred for expressions involving these types.
For example, a value with type `Callable[[], int]` will not allow efficient
call operations. However, the return is a primitive type, and the callable
type allows fast operations to be used on the return values:

.. code-block::

    from typing import Callable

    def call_and_inc(f: Callable[[], int]) -> int:
        n = f()  # Slow call, since f has an erased type
        n += 1  # Fast increment, since n has type int (primitive type)
        return n
