.. _cheat-sheet-py3:

Type hints cheat sheet (Python 3)
=================================

This document is a quick cheat sheet showing how the :pep:`484` type
annotation notation represents various common types in Python 3.

.. note::

   Technically many of the type annotations shown below are redundant,
   because mypy can derive them from the type of the expression.  So
   many of the examples have a dual purpose: show how to write the
   annotation, and show the inferred types.


Variables
*********

Python 3.6 introduced a syntax for annotating variables in :pep:`526`
and we use it in most examples.

.. code-block:: python

   # This is how you declare the type of a variable type in Python 3.6
   age: int = 1

   # In Python 3.5 and earlier you can use a type comment instead
   # (equivalent to the previous definition)
   age = 1  # type: int

   # You don't need to initialize a variable to annotate it
   a: int  # Ok (no value at runtime until assigned)

   # The latter is useful in conditional branches
   child: bool
   if age < 18:
       child = True
   else:
       child = False


Built-in types
**************

.. code-block:: python

   from typing import List, Set, Dict, Tuple, Optional

   # For simple built-in types, just use the name of the type
   x: int = 1
   x: float = 1.0
   x: bool = True
   x: str = "test"
   x: bytes = b"test"

   # For collections, the name of the type is capitalized, and the
   # name of the type inside the collection is in brackets
   x: List[int] = [1]
   x: Set[int] = {6, 7}

   # Same as above, but with type comment syntax
   x = [1]  # type: List[int]

   # For mappings, we need the types of both keys and values
   x: Dict[str, float] = {'field': 2.0}

   # For tuples of fixed size, we specify the types of all the elements
   x: Tuple[int, str, float] = (3, "yes", 7.5)
   
   # For tuples of variable size, we use one type and ellipsis
   x: Tuple[int, ...] = (1, 2, 3)

   # Use Optional[] for values that could be None
   x: Optional[str] = some_function()
   # Mypy understands a value can't be None in an if-statement
   if x is not None:
       print(x.upper())
   # If a value can never be None due to some invariants, use an assert
   assert x is not None
   print(x.upper())

Functions
*********

Python 3 supports an annotation syntax for function declarations.

.. code-block:: python

   from typing import Callable, Iterator, Union, Optional, List

   # This is how you annotate a function definition
   def stringify(num: int) -> str:
       return str(num)

   # And here's how you specify multiple arguments
   def plus(num1: int, num2: int) -> int:
       return num1 + num2

   # Add default value for an argument after the type annotation
   def f(num1: int, my_float: float = 3.5) -> float:
       return num1 + my_float

   # This is how you annotate a callable (function) value
   x: Callable[[int, float], float] = f

   # A generator function that yields ints is secretly just a function that
   # returns an iterator of ints, so that's how we annotate it
   def g(n: int) -> Iterator[int]:
       i = 0
       while i < n:
           yield i
           i += 1

   # You can of course split a function annotation over multiple lines
   def send_email(address: Union[str, List[str]],
                  sender: str,
                  cc: Optional[List[str]],
                  bcc: Optional[List[str]],
                  subject='',
                  body: Optional[List[str]] = None
                  ) -> bool:
       ...

   # An argument can be declared positional-only by giving it a name
   # starting with two underscores:
   def quux(__x: int) -> None:
       pass

   quux(3)  # Fine
   quux(__x=3)  # Error

When you're puzzled or when things are complicated
**************************************************

.. code-block:: python

   from typing import Union, Any, List, Optional, cast

   # To find out what type mypy infers for an expression anywhere in
   # your program, wrap it in reveal_type().  Mypy will print an error
   # message with the type; remove it again before running the code.
   reveal_type(1)  # -> Revealed type is 'builtins.int'

   # Use Union when something could be one of a few types
   x: List[Union[int, str]] = [3, 5, "test", "fun"]

   # Use Any if you don't know the type of something or it's too
   # dynamic to write a type for
   x: Any = mystery_function()

   # If you initialize a variable with an empty container or "None"
   # you may have to help mypy a bit by providing a type annotation
   x: List[str] = []
   x: Optional[str] = None

   # This makes each positional arg and each keyword arg a "str"
   def call(self, *args: str, **kwargs: str) -> str:
       request = make_request(*args, **kwargs)
       return self.do_api_query(request)

   # Use a "type: ignore" comment to suppress errors on a given line,
   # when your code confuses mypy or runs into an outright bug in mypy.
   # Good practice is to comment every "ignore" with a bug link
   # (in mypy, typeshed, or your own code) or an explanation of the issue.
   x = confusing_function()  # type: ignore  # https://github.com/python/mypy/issues/1167

   # "cast" is a helper function that lets you override the inferred
   # type of an expression. It's only for mypy -- there's no runtime check.
   a = [4]
   b = cast(List[int], a)  # Passes fine
   c = cast(List[str], a)  # Passes fine (no runtime check)
   reveal_type(c)  # -> Revealed type is 'builtins.list[builtins.str]'
   print(c)  # -> [4]; the object is not cast

   # If you want dynamic attributes on your class, have it override "__setattr__"
   # or "__getattr__" in a stub or in your source code.
   #
   # "__setattr__" allows for dynamic assignment to names
   # "__getattr__" allows for dynamic access to names
   class A:
       # This will allow assignment to any A.x, if x is the same type as "value"
       # (use "value: Any" to allow arbitrary types)
       def __setattr__(self, name: str, value: int) -> None: ...

       # This will allow access to any A.x, if x is compatible with the return type
       def __getattr__(self, name: str) -> int: ...

   a.foo = 42  # Works
   a.bar = 'Ex-parrot'  # Fails type checking


Standard "duck types"
*********************

In typical Python code, many functions that can take a list or a dict
as an argument only need their argument to be somehow "list-like" or
"dict-like".  A specific meaning of "list-like" or "dict-like" (or
something-else-like) is called a "duck type", and several duck types
that are common in idiomatic Python are standardized.

.. code-block:: python

   from typing import Mapping, MutableMapping, Sequence, Iterable, List, Set

   # Use Iterable for generic iterables (anything usable in "for"),
   # and Sequence where a sequence (supporting "len" and "__getitem__") is
   # required
   def f(ints: Iterable[int]) -> List[str]:
       return [str(x) for x in ints]

   f(range(1, 3))

   # Mapping describes a dict-like object (with "__getitem__") that we won't
   # mutate, and MutableMapping one (with "__setitem__") that we might
   def f(my_dict: Mapping[int, str]) -> List[int]:
       my_mapping[5] = 'maybe'  # if we try this, mypy will throw an error...
       return list(my_dict.keys())

   f({3: 'yes', 4: 'no'})

   def f(my_mapping: MutableMapping[int, str]) -> Set[str]:
       my_mapping[5] = 'maybe'  # ...but mypy is OK with this.
       return set(my_mapping.values())

   f({3: 'yes', 4: 'no'})


Classes
*******

.. code-block:: python

   class MyClass:
       # You can optionally declare instance variables in the class body
       attr: int
       # This is an instance variable with a default value
       charge_percent: int = 100

       # The "__init__" method doesn't return anything, so it gets return
       # type "None" just like any other method that doesn't return anything
       def __init__(self) -> None:
           ...

       # For instance methods, omit type for "self"
       def my_method(self, num: int, str1: str) -> str:
           return num * str1

   # User-defined classes are valid as types in annotations
   x: MyClass = MyClass()

   # You can use the ClassVar annotation to declare a class variable
   class Car:
       seats: ClassVar[int] = 4
       passengers: ClassVar[List[str]]

   # You can also declare the type of an attribute in "__init__"
   class Box:
       def __init__(self) -> None:
           self.items: List[str] = []


Coroutines and asyncio
**********************

See :ref:`async-and-await` for the full detail on typing coroutines and asynchronous code.

.. code-block:: python

   import asyncio

   # A coroutine is typed like a normal function
   async def countdown35(tag: str, count: int) -> str:
       while count > 0:
           print('T-minus {} ({})'.format(count, tag))
           await asyncio.sleep(0.1)
           count -= 1
       return "Blastoff!"


Miscellaneous
*************

.. code-block:: python

   import sys
   import re
   from typing import Match, AnyStr, IO

   # "typing.Match" describes regex matches from the re module
   x: Match[str] = re.match(r'[0-9]+', "15")

   # Use IO[] for functions that should accept or return any
   # object that comes from an open() call (IO[] does not
   # distinguish between reading, writing or other modes)
   def get_sys_IO(mode: str = 'w') -> IO[str]:
       if mode == 'w':
           return sys.stdout
       elif mode == 'r':
           return sys.stdin
       else:
           return sys.stdout

   # Forward references are useful if you want to reference a class before
   # it is defined
   def f(foo: A) -> int:  # This will fail
       ...

   class A:
       ...

   # If you use the string literal 'A', it will pass as long as there is a
   # class of that name later on in the file
   def f(foo: 'A') -> int:  # Ok
       ...


Decorators
**********

Decorator functions can be expressed via generics. See
:ref:`declaring-decorators` for the more details.

.. code-block:: python

    from typing import Any, Callable, TypeVar

    F = TypeVar('F', bound=Callable[..., Any])

    def bare_decorator(func: F) -> F:
        ...

    def decorator_args(url: str) -> Callable[[F], F]:
        ...
