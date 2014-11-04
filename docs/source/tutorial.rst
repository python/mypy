Tutorial
========

Function Signatures
*******************

A function without a type signature is dynamically typed. You can declare the signature of a function using the Python 3 annotation syntax This makes the function statically typed (the type checker reports type errors within the function):

.. code-block:: python
   
   # Dynamically typed (identical to Python)

   def greeting(name):
       return 'Hello, {}'.format(name)

.. code-block:: python
   
   # Statically typed (still valid Python)
   
   def greeting(name: str) -> str:
       return 'Hello, {}'.format(name)

A ``None`` return type indicates a function that does not explicitly return a value. Using a ``None`` result in a statically typed context results in a type check error:

.. code-block:: python
   
   def p() -> None:
       print('hello')
   
   a = p()   # Type check error: p has None return value

The typing module
*****************

We cheated a bit in the above examples: a module is type checked only if it imports the module typing. Here is a complete statically typed example from the previous section:

.. code-block:: python
   
   import typing
   
   def greeting(name: str) -> str:
       return 'Hello, {}'.format(name)

The typing module contains many definitions that are useful in statically typed code. You can also use ``from ... import`` to import them (we'll explain Iterable later in this document):

.. code-block:: python
   
   from typing import Iterable

   def greet_all(names: Iterable[str]) -> None:
       for name in names:
           print('Hello, {}'.format(name))

For brevity, we often omit the typing import in code examples, but you should always include it in modules that contain statically typed code.

You can still have dynamically typed functions in modules that import typing:

.. code-block:: python
   
   import typing
   
   def f():
       1 + 'x'  # No static type error (dynamically typed)
   
   def g() -> None:
       1 + 'x'  # Type check error (statically typed)

Mixing dynamic and static typing within a single file is often useful. For example, if you are migrating existing Python code to static typing, it may be easiest to do this incrementally, such as by migrating a few functions at a time. Also, when prototyping a new feature, you may decide to first implement the relevant code using dynamic typing and only add type signatures later, when the code is more stable.

.. note::
   
   Currently the type checker checks the top levels and annotated functions of all modules, even those that don't import typing. However, you should not rely on this, as this will change in the future.

Type checking and running programs
**********************************

You can type check a program by using the mypy tool, which is basically a linter — it checks you program for errors without actually running it::
   
   $ mypy program.py

You can always run a mypy program as a Python program, without type checking, even it it has type errors::
   
   $ python3 program.py

All errors reported by mypy are essentially warnings that you are free to ignore, if you so wish.

The `README <https://github.com/JukkaL/mypy/blob/master/README.md>`_ explains how to download and install mypy.

.. note::
   
   Depending on how mypy is configured, you may have to explicitly use the Python interpreter to run mypy. The mypy tool is an ordinary mypy (and so also Python) program.

Built-in types
**************

These are examples of some of the most common built-in types:

.. code-block:: python
   
   int            # integer objects of arbitrary size
   float          # floating point number
   bool           # boolean value
   str            # unicode string
   bytes          # 8-bit string
   object         # the common base class
   List[str]      # list of str objects
   Dict[str, int] # dictionary from str to int
   Iterable[int]  # iterable object containing ints
   Sequence[bool] # sequence of booleans
   Any            # dynamically typed value

The type ``Any`` and type constructors ``List``, ``Dict``, ``Iterable`` and ``Sequence`` are defined in the typing module.

The type ``Dict`` is a *generic* class, signified by type arguments within ``[...]``. For example, ``Dict[int, str]`` is a dictionary from integers to strings and and ``Dict[Any, Any]`` is a dictionary of dynamically typed (arbitrary) values and keys. ``List`` is another generic class. ``Dict`` and ``List`` are aliases for the built-ins dict and list, respectively.

``Iterable`` and ``Sequence`` are generic abstract base classes that correspond to Python protocols. For example, a str object is valid when ``Iterable[str]`` or ``Sequence[str]`` is expected. Note that even though they are similar to abstract base classes defined in ``abc.collections`` (formerly collections), they are not identical, since the built-in collection type objects do not support indexing.

Type inference
**************

The initial assignment defines a variable. If you do not explicitly specify the type of the variable, mypy infers the type based on the static type of the value expression:

.. code-block:: python
   
   i = 1           # Infer type int for i
   l = [1, 2]      # Infer type List[int] for l

Type inference is bidirectional and takes context into account. For example, the following is valid:

.. code-block:: python
   
   def f(l: List[object]) -> None:
       l = [1, 2]  # Infer type List[object] for [1, 2]

In an assignment, the type context is determined by the assignment target. In this case this is ``l``, which has the type ``List[object]``. The value expression ``[1, 2]`` is type checked in this context and given the type ``List[object]``. In the previous example we introduced a new variable ``l``, and here the type context was empty.

Note that the following is not valid, since ``List[int]`` is not compatible with ``List[object]``:

.. code-block:: python
   
   def f(l: List[object], k: List[int]) -> None:
       l = k       # Type check error: incompatible types in assignment

The reason why the above assignment is disallowed is that allowing the assignment could result in non-int values stored in a list of int:

.. code-block:: python
   
   def f(l: List[object], k: List[int]) -> None:
       l = k
       l.append('x')
       print(k[-1])  # Ouch; a string in List[int]

You can still run the above program; it prints x. This illustrates the fact that static types are used during type checking, but they do not affect the runtime behavior of programs. You can run programs with type check failures, which is often very handy when performing a large refactoring. Thus you can always 'work around' the type system, and it doesn't really limit what you can do in your program.

Type inference is not used in dynamically typed functions (those without an explicit return type) — every local variable type defaults to ``Any``, which is discussed below.

Explicit types for collections
******************************

The type checker cannot always infer the type of a list or a dictionary. This often arises when creating an empty list or dictionary and assigning it to a new variable without an explicit variable type. In these cases you can give the type explicitly using the type name as a constructor:

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

The ``Undefined`` call evaluates to a special "Undefined" object that raises an exception on any operation:

.. code-block:: python
   
   s = Undefined(str)
   if s:                # Runtime error: undefined value
       print('hello')

You can also override the inferred type of a variable by using a special comment after an assignment statement:

.. code-block:: python
   
   x = [] # type: List[int]

Here the ``# type`` comment applies both to the assignment target, in this case ``x``, and also the initializer expression, via context. The above code is equivalent to this:

.. code-block:: python
   
   x = List[int]()

The type checker infers the value of a variable from the initializer, and if it is an empty collection such as ``[]``, the type is not well-defined. You can declare the collection type using one of the above syntax alternatives.

User-defined types
******************

Each class is also a type. Any instance of a subclass is also compatible with all superclasses. All values are compatible with the object type (and also the ``Any`` type).

.. code-block:: python
   
   class A:
       def f(self) -> int:        # Type of self inferred (A)
           return 2
   
   class B(A):
       def f(self) -> int:
            return 3
       def g(self) -> int:
           return 4
   
   a = B() # type: A  # OK (explicit type for a; override type inference)
   print(a.f())       # 3
   a.g()              # Type check error: A has no method g

The Any type
************

A value with the Any type is dynamically typed. Any operations are permitted on the value, and the operations are checked at runtime, similar to normal Python code. If you do not define a function return value or argument types, these default to ``Any``. Also, a function without an explicit return type is dynamically typed. The body of a dynamically typed function is not checked statically.

Any is compatible with every other type, and vice versa. No implicit type check is inserted when assigning a value of type ``Any`` to a variable with a more precise type:

.. code-block:: python
   
   a, s = Undefined(Any), Undefined(str)
   a = 2      # OK
   s = a      # OK

Declared (and inferred) types are erased at runtime (they are basically treated as comments), and thus the above code does not generate a runtime error.

Tuple types
***********

The type ``Tuple[t, ...]`` represents a tuple with the item types ``t, ...``:

.. code-block:: python
   
   def f(t: Tuple[int, str]) -> None:
       t = 1, 'foo'    # OK
       t = 'foo', 1    # Type check error

Class name forward references
*****************************

Python does not allow references to a class object before the class is defined. Thus this code is does not work as expected:

.. code-block:: python
   
   def f(x: A) -> None: # Error: Name A not defined
       ....
   
   class A:
       ...

In cases like these you can enter the type as a string literal — this is a *forward reference*:

.. code-block:: python
   
   def f(x: 'A') -> None:  # OK
       ...
   
   class A:
       ...

Of course, instead of using a string literal type, you could move the function definition after the class definition. This is not always desirable or even possible, though.

Any type can be entered as a string literal, and youn can combine string-literal types with non-string-literal types freely:

.. code-block:: python
   
   a = Undefined(List['A'])  # OK
   n = Undefined('int')      # OK, though not useful
   
   class A: pass

String literal types are never needed in ``# type`` comments.

Instance and class attributes
*****************************

Mypy type checker detects if you are trying to access a missing attribute, which is a very common programming error. For this to work correctly, instance and class attributes must be defined or initialized within the class. Mypy infers the types of attributes:

.. code-block:: python
   
   class A:
       def __init__(self, x: int) -> None:
           self.x = x     # Attribute x of type int
   
   a = A(1)
   a.x = 2       # OK
   a.y = 3       # Error: A has no attribute y

This is a bit like each class having an implicitly defined ``__slots__`` attribute. In Python semantics this is only enforced during type checking: at runtime we use standard Python semantics. You can selectively define a class as *dynamic*; dynamic classes have Python-like compile-time semantics, and they allow you to assign to arbitrary attributes anywhere in a program without the type checker complaining:

.. code-block:: python
   
   from typing import Dynamic
   
   class A(Dynamic):
       pass
   
   a = A()
   a.x = 2     # OK, no need to define x explicitly.

Mypy also lets you read arbitrary attributes of dynamic class instances. This limits type checking effectiveness, so you should only use dynamic classes when you really need them.

.. note::
   
   Dynamic classes are not implemented in the current mypy version.

You can declare variables in the class body explicitly using Undefined or a type comment:

.. code-block:: python
   
   class A:
       x = Undefined(List[int])  # Declare attribute y of type List[int]
       y = 0  # type: Any        # Declare attribute x of type Any
   
   a = A()
   a.x = [1]     # OK

As in Python, a variable defined in the class body can used as a class or an instance variable.

Similarly, you can give explicit types to instance variables defined in a method:

.. code-block:: python
   
   class A:
       def __init__(self) -> None:
           self.x = Undefined(List[int])     # OK
   
       def f(self) -> None:
           self.y = 0 # type: Any            # OK

You can only define an instance variable within a method if you assign to it explicitly using self:

.. code-block:: python
   
   class A:
       def __init__(self) -> None:
           self.y = 1   # Define y
           a = self
           a.x = 1      # Error: x not defined

Overriding statically typed methods
***********************************

When overriding a statically typed method, mypy checks that the override has a compatible signature:

.. code-block:: python
   
   class A:
       def f(self, x: int) -> None:
           ...
   
   class B(A):
       def f(self, x: str) -> None:   # Error: type of x incompatible
           ...
   
   class C(A):
       def f(self, x: int, y: int) -> None:  # Error: too many arguments
           ...
   
   class D(A):
       def f(self, x: int) -> None:   # OK
           ...

.. note::
   
   You can also vary return types **covariantly** in overriding. For example, you could override the return type ``object`` with a subtype such as ``int``.

You can also override a statically typed method with a dynamically typed one. This allows dynamically typed code to override methods defined in library classes without worrying about their type signatures, similar to Python.

There is no runtime enforcement that the method override returns a value that is compatible with the original return type, since types are erased in the Python semantics:

.. code-block:: python
   
   class A:
       def inc(self, x: int) -> int:
           return x + 1
   
   class B(A):
       def inc(self, x):       # Override, dynamically typed
           return 'hello'
   
   b = B()
   print(b.inc(1))   # hello
   a = b # type: A
   print(a.inc(1))   # hello

Declaring multiple variable types on a line
*******************************************

You can declare more than a single variable at a time. In order to nicely work with multiple assignment, you must give each variable a type separately:

.. code-block:: python
   
   n, s = Undefined(int), Undefined(str)  # Declare an integer and a string
   i, found = 0, False # type: int, bool

When using the latter form, you can optinally use parentheses around the types, assignment targets and assigned expression:

.. code-block:: python
   
   i, found = 0, False # type: (int, bool)      # OK
   (i, found) = 0, False # type: int, bool      # OK
   i, found = (0, False) # type: int, bool      # OK
   (i, found) = (0, False) # type: (int, bool)  # OK

Dynamically typed code
**********************

As mentioned earlier, bodies of functions that don't have have an explicit return type are dynamically typed (operations are checked at runtime). Code outside functions is statically typed by default, and types of variables are inferred. This does usually the right thing, but you can also make any variable dynamically typed by defining it explicitly with the type ``Any``:

.. code-block:: python
   
   from typing import Any
   
   s = 1                 # Statically typed (type int)
   d = 1  # type: Any    # Dynamically typed (type Any)
   s = 'x'               # Type check error
   d = 'x'               # OK

Alternatively, you can use the ``Undefined`` construct to define dynamically typed variables, as ``Any`` can be used anywhere any other type is valid:

.. code-block:: python
   
   from typing import Undefined, Any
   
   d = Undefined(Any)
   d = 1   # OK
   d = 'x' # OK

Additionally, if you don't import the typing module in a file, all code outside functions will be dynamically typed by default, and the file is not type checked at all. This mode makes it easy to include existing Python code that is not trivially compatible with static typing.

.. note::
   
   The current mypy version type checks all modules, even those that don't import typing. This will change in a future version.

Abstract base classes and multiple inheritance
**********************************************

Mypy uses Python abstract base classes for protocol types. There are several built-in abstract base classes types (for example, ``Sequence``, ``Iterable`` and ``Iterator``). You can define abstract base classes using the ``abc.ABCMeta`` metaclass and the ``abc.abstractmethod`` function decorator.

.. code-block:: python
   
   from abc import ABCMeta, abstractmethod
   import typing
   
   class A(metaclass=ABCMeta):
       @abstractmethod
       def foo(self, x: int) -> None: pass
   
       @abstractmethod
       def bar(self) -> str: pass
   
   class B(A):
       def foo(self, x: int) -> None: ...
       def bar(self -> str:
           return 'x'
   
   a = A() # Error: A is abstract
   b = B() # OK

Unlike most Python code, abstract base classes are likely to play a significant role in many complex mypy programs.

A class can inherit any number of classes, both abstract and concrete. As with normal overrides, a dynamically typed method can implement a statically typed abstract method defined in an abstract base class.

.. note::
   
   There are also plans to support more Python-style "duck typing" in the type system. The details are still open.

Function overloading
********************

You can define multiple instances of a function with the same name but different signatures. The first matching signature is selected at runtime when evaluating each individual call. This enables also a form of multiple dispatch.

.. code-block:: python
   
   from typing import overload
   
   @overload
   def abs(n: int) -> int:
       return n if n >= 0 else -n
   
   @overload
   def abs(n: float) -> float:
       return n if n >= 0.0 else -n
   
   abs(-2)     # 2 (int)
   abs(-1.5)   # 1.5 (float)

Overloaded function variants still define a single runtime object; the following code is valid:

.. code-block:: python
   
   my_abs = abs
   my_abs(-2)      # 2 (int)
   my_abs(-1.5)    # 1.5 (float)

The overload variants must be adjacent in the code. This makes code clearer, and otherwise there would be awkward corner cases such as partially defined overloaded functions that could surprise the unwary programmer.

.. note::
   
   As generic type variables are erased at runtime, an overloaded function cannot dispatch based on a generic type argument, e.g. ``List[int]`` versus ``List[str]``.

Callable types and lambdas
**************************

You can pass around function objects and bound methods in statically typed code. The type of a function that accepts arguments ``A1, ..., An`` and returns ``Rt`` is ``Function[[A1, ..., An], Rt]``. Example:

.. code-block:: python
   
   def twice(i: int, next: Function[[int], int]) -> int:
       return next(next(i))
   
   def add(i: int) -> int:
       return i + 1
   
   print(twice(3, add))   # 5

Lambdas are also supported. The lambda argument and return value types cannot be given explicitly; they are always inferred based on context using bidirectional type inference:

.. code-block:: python
   
   l = map(lambda x: x + 1, [1, 2, 3])   # infer x as int and l as List[int]

If you want to give the argument or return value types explicitly, use an ordinary, perhaps nested function definition.

Casts
*****

Mypy supports type casts that are usually used to coerce a statically typed value to a subtype. Unlike languages such as Java or C#, however, mypy casts are only used as hints for the type checker when using Python semantics, and they have no runtime effect. Use the function cast to perform a cast:

.. code-block:: python
   
   from typing import cast
   
   o = [1] # type: object
   x = cast(List[int], o)  # OK
   y = cast(List[str], o)  # OK (cast performs no actual runtime check)

Supporting runtime checking of casts such as the above when using Python semantics would require emulating reified generics and this would be difficult to do and would likely degrade performance and make code more difficult to read. You should not rely in your programs on casts being checked at runtime. Use an assertion if you want to perform an actual runtime check. Casts are used to silence spurious type checker warnings.

You don't need a cast for expressions with type ``Any``, of when assigning to a variable with type ``Any``, as was explained earlier.

You can cast to a dynamically typed value by just calling ``Any``:

.. code-block:: python
   
   from typing import Any
   
   def f(x: object) -> None:
       Any(x).foo()   # OK

Notes about writing statically typed code
*****************************************

Statically typed function bodies are often identical to normal Python code, but sometimes you need to do things slightly differently. This section introduces some of the most common cases which require different conventions in statically typed code.

First, you need to specify the type when creating an empty list or dict and when you assign to a new variable, as mentioned earlier:

.. code-block:: python
   
   a = List[int]()   # Explicit type required in statically typed code
   a = []            # Fine in a dynamically typed function, or if type
                     # of a has been declared or inferred before

Sometimes you can avoid the explicit list item type by using a list comprehension. Here a type annotation is needed:

.. code-block:: python
   
   l = List[int]()
   for i in range(n):
       l.append(i * i)

.. note::
   
   A future mypy version may be able to deal with cases such as the above without type annotations.

No type annotation needed if using a list comprehension:

.. code-block:: python
   
   l = [i * i for i in range(n)]

However, in more complex cases the explicit type annotation can improve the clarity of your code, whereas a complex list comprehension can make your code difficult to understand.

Second, each name within a function only has a single type. You can reuse for loop indices etc., but if you want to use a variable with multiple types within a single function, you may need to declare it with the ``Any`` type.

.. code-block:: python
   
   def f() -> None:
       n = 1
       ...
       n = x        # Type error: n has type int

.. note::
   
   This is another limitation that could be lifted in a future mypy version.

Third, sometimes the inferred type is a subtype of the desired type. The type inference uses the first assignment to infer the type of a name:

.. code-block:: python
   
   # Assume Shape is the base class of both Circle and Triangle.
   shape = Circle()    # Infer shape to be Circle
   ...
   shape = Triangle()  # Type error: Triangle is not a Circle

You can just give an explicit type for the variable in cases such the above example:

.. code-block:: python
   
   shape = Circle() # type: Shape   # The variable s can be any Shape,
                                    # not just Circle
   ...
   shape = Triangle()               # OK

Fourth, if you use isinstance tests or other kinds of runtime type tests, you may have to add casts (this is similar to instanceof tests in Java):

.. code-block:: python
   
   def f(o: object) -> None:
       if isinstance(o, int):
           n = cast(int, o)
           n += 1    # o += 1 would be an error
           ...

Note that the object type used in the above example is similar to Object in Java: it only supports operations defined for all objects, such as equality and ``isinstance()``. The type ``Any``, in contrast, supports all operations, even if they may fail at runtime. The cast above would have been unnecessary if the type of ``o`` was ``Any``.

Some consider casual use of isinstance tests a sign of bad programming style. Often a method override or an overloaded function is a cleaner way of implementing functionality that depends on the runtime types of values. However, use whatever techniques that work for you. Sometimes isinstance tests *are* the cleanest way of implementing a piece of functionality.

Type inference in mypy is designed to work well in common cases, to be predictable and to let the type checker give useful error messages. More powerful type inference strategies often have complex and difficult-to-prefict failure modes and could result in very confusing error messages.

Defining generic classes
************************

The built-in collection classes are generic classes. Generic types have one or more type parameters, which can be arbitrary types. For example, ``Dict[int, str]`` has the type parameters int and str, and ``List[int]`` has a type parameter int.

Programs can also define new generic classes. Here is a very simple generic class that represents a stack:

.. code-block:: python
   
   from typing import typevar, Generic
   
   T = typevar('T')
   
   class Stack(Generic[T]):
       def __init__(self) -> None:
           self.items = List[T]()  # Create an empty list with items of type T
   
       def push(self, item: T) -> None:
           self.items.append(item)
   
       def pop(self) -> T:
           return self.items.pop()
   
       def empty(self) -> bool:
           return not self.items

The ``Stack`` class can be used to represent a stack of any type: ``Stack[int]``, ``Stack[Tuple[int, str]]``, etc.

Using Stack is similar to built-in container types:

.. code-block:: python
   
   stack = Stack[int]()   # Construct an empty Stack[int] instance
   stack.push(2)
   stack.pop()
   stack.push('x')        # Type error

Type inference works for user-defined generic types as well:

.. code-block:: python
   
   def process(stack: Stack[int]) -> None: ...
   
   process(Stack())   # Argument has inferred type Stack[int]

Generic class internals
***********************

You may wonder what happens at runtime when you index ``Stack``. Actually, indexing ``Stack`` just returns ``Stack``:

>>> print(Stack)
<class '__main__.Stack'>
>>> print(Stack[int])
<class '__main__.Stack'>

Note that built-in types ``list``, ``dict`` and so on do not support indexing in Python. This is why we have the aliases ``List``, ``Dict`` and so on in the typing module. Indexing these aliases just gives you the target class in Python, similar to ``Stack``:

>>> from typing import List
>>> List[int]
<class 'list'>

The above examples illustrate that type variables are erased at runtime when running in a Python VM. Generic ``Stack`` or ``list`` instances are just ordinary Python objects, and they have no extra runtime overhead or magic due to being generic, other than a metaclass that overloads the indexing operator. If you worry about the overhead introduced by the type indexing operation when constructing instances, you can often rewrite such code using a ``# type`` annotation, which has no runtime impact:

.. code-block:: python
   
   x = List[int]()
   x = [] # type: List[int]   # Like the above but faster.

The savings are rarely significant, but it could make a difference in a performance-critical loop or function. Function annotations, on the other hand, are only evaluated during the defintion of the function, not during every call. Constructing type objects in function signatures rarely has any noticeable performance impact.

Generic functions
*****************

Generic type variables can also be used to define generic functions:

.. code-block:: python
   
   from typing import typevar, Sequence
   
   T = typevar('T')      # Declare type variable
   
   def first(seq: Sequence[T]) -> T:   # Generic function
       return seq[0]

As with generic classes, the type variable can be replaced with any type. That means first can we used with any sequence type, and the return type is derived from the sequence item type. For example:

.. code-block:: python
   
   # Assume first defined as above.
   
   s = first('foo')      # s has type str.
   n = first([1, 2, 3])  # n has type int.

Note also that a single definition of a type variable (such as ``T`` above) can be used in multiple generic functions or classes. In this example we use the same type variable in two generic functions:

.. code-block:: python
   
   from typing typevar, Sequence
   
   T = typevar('T')      # Declare type variable
   
   def first(seq: Sequence[T]) -> T:
       return seq[0]
   
   def last(seq: Sequence[T]) -> T:
       return seq[-1]

You can also define generic methods — just use a type variable in the method signature that is different from class type variables.

Supported Python features and modules
*************************************

Lists of supported Python features and standard library modules are maintained in the mypy wiki:

- `Supported Python features <http://www.mypy-lang.org/wiki/SupportedPythonFeatures>`_
- `Supported Python modules <http://www.mypy-lang.org/wiki/SupportedPythonModules>`_

Runtime definition of methods and functions
*******************************************

By default, mypy will not let you redefine functions or methods, and you can't add functions to a class or module outside its definition -- but only if this is visible to the type checker. This only affects static checking, as mypy performs no additional type checking at runtime. You can easily work around this. For example, you can use dynamically typed code or values with Any types, or you can use setattr or other introspection features. However, you need to be careful if you decide to do this. If used indiscriminately, you may have difficulty using static typing effectively, since the type checker cannot see functions defined at runtime.

Additional features

Several mypy features are not currently covered by this tutorial, including the following:

- inheritance between generic classes

- compatibility and subtyping of generic types, including covariance of generic types

- super()

Planned features
****************

This section introduces some language features that are still work in progress.

None
----

Currently, ``None`` is a valid value for each type, similar to null or NULL in many languages. However, it is likely that this decision will be reversed, and types do not include ``None`` default. The ``Optional`` type modifier can be used to define a type variant that includes ``None``, such as ``Optional(int)``:

.. code-block:: python
   
   def f() -> Optional[int]:
       return None # OK
   
   def g() -> int:
       ...
       return None # Error: None not compatible with int

Also, most operations would not be supported on ``None`` values:

.. code-block:: python
   
   def f(x: Optional[int]) -> int:
       return x + 1  # Error: Cannot add None and int

Instead, an explicit ``None`` check would be required. This would benefit from more powerful type inference:

.. code-block:: python
   
   def f(x: Optional[int]) -> int:
       if x is None:
           return 0
       else:
           # The inferred type of x is just int here.
           return x + 1

We would infer the type of ``x`` to be ``int`` in the else block due to the check against ``None`` in the if condition.

Union types
-----------

Python functions often accept values of two or more different types. You can use overloading to model this in statically typed code, but union types can make code like this easier to write.

Use the ``Union[...]`` type constructor to construct a union type. For example, the type ``Union[int, str]`` is compatible with both integers and strings. You can use an ``isinstance`` check to narrow down the type to a specific type:

.. code-block:: python
   
   from typing import Union
   
   def f(x: Union[int, str]) -> None:
       x + 1     # Error: str + int is not valid
       if isinstance(x, int):
           # Here type of x is int.
           x + 1      # OK
       else:
           # Here type of x is str.
           x + 'a'    # OK
   
   f(1)    # OK
   f('x')  # OK
   f(1.1)  # Error

More general type inference
---------------------------

It may be useful to support type inference also for variables defined in multiple locations in an if/else statement, even if the initializer types are different:

.. code-block:: python
   
   if x:
       y = None     # First definition of y
   else:
       y = 'a'      # Second definition of y

In the above example, both of the assignments would be used in type inference, and the type of ``y`` would be ``str``. However, it is not obvious whether this would be generally desirable in more complex cases.

Revision history
****************

List of major changes to this document:

- Sep 15 2014: Migrated docs to Sphinx

- Aug 25 2014: Don't discuss native semantics. There is only Python semantics.

- Jul 2 2013: Rewrite to use new syntax. Shift focus to discussing Python semantics. Add more content, including short discussions of `generic functions <http://www.mypy-lang.org/tutorial.html#genericfunctions>`_ and `union types <http://www.mypy-lang.org/tutorial.html#uniontypes>`_.

- Dec 20 2012: Add new sections on explicit types for collections, declaring multiple variables, callable types, casts, generic classes and translation to Python. Add notes about writing statically typed code and links to the wiki. Also add a table of contents. Various other, more minor updates.

- Dec 2 2012: Use new syntax for `list types <http://www.mypy-lang.org/tutorial.html#builtintypes>`_ and `interfaces <http://www.mypy-lang.org/tutorial.html#interfaces>`_. Discuss `runtime redefinition of methods and functions <http://www.mypy-lang.org/tutorial.html#redef>`. Also did minor restructuring.
