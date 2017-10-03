.. _cheat-sheet-py3:

Mypy syntax cheat sheet (Python 3)
==================================

This document is a quick cheat sheet showing how the `PEP 484 <https://www.python.org/dev/peps/pep-0484/>`_ type
language represents various common types in Python 3. Unless otherwise noted, the syntax is valid on all versions of Python 3.

.. note::

   Technically many of the type annotations shown below are redundant,
   because mypy can derive them from the type of the expression.  So
   many of the examples have a dual purpose: show how to write the
   annotation, and show the inferred types.


Built-in types
**************

.. code-block:: python

   from typing import List, Set, Dict, Tuple, Text, Optional, AnyStr

   # For simple built-in types, just use the name of the type.
   x = 1  # type: int
   x = 1.0  # type: float
   x = True  # type: bool
   x = "test"  # type: str
   x = u"test"  # type: str
   x = b"test"  # type: bytes

   # For collections, the name of the type is capitalized, and the
   # name of the type inside the collection is in brackets.
   x = [1]  # type: List[int]
   x = {6, 7}  # type: Set[int]

   # For mappings, we need the types of both keys and values.
   x = {'field': 2.0}  # type: Dict[str, float]

   # For tuples, we specify the types of all the elements.
   x = (3, "yes", 7.5)  # type: Tuple[int, str, float]

   # For textual data, use Text.
   # This is `unicode` in Python 2 and `str` in Python 3.
   x = ["string", u"unicode"]  # type: List[Text]



   # Use Optional for values that could be None.
   input_str = f()  # type: Optional[str]
   if input_str is not None:
      print(input_str)


Functions
*********

Python 3 introduces an annotation syntax for function declarations in `PEP 3107 <https://www.python.org/dev/peps/pep-3107/>`_.

.. code-block:: python

   from typing import Callable, Iterable, Union, Optional, List

   # This is how you annotate a function definition.
   def stringify(num: int) -> str:
       return str(num)
       
   # And here's how you specify multiple arguments.
   def plus(num1: int, num2: int) -> int:
       return num1 + num2

   # Add type annotations for kwargs as though they were positional args.
   def f(num1: int, my_float: float = 3.5) -> float:
       return num1 + my_float

   # An argument can be declared positional-only by giving it a name
   # starting with two underscores:
   def quux(__x: int) -> None:
       pass
   quux(3)  # Fine
   quux(__x=3)  # Error

   # This is how you annotate a function value.
   x = f # type: Callable[[int, float], float]

   # A generator function that yields ints is secretly just a function that
   # returns an iterable (see below) of ints, so that's how we annotate it.
   def f(n: int) -> Iterable[int]:
       i = 0
       while i < n:
           yield i
           i += 1

   # For a function with many arguments, you can of course split it over multiple lines
   def send_email(address: Union[str, List[str]],
                  sender: str,
                  cc: Optional[List[str]],
                  bcc: Optional[List[str]],
                  subject='',
                  body: List[str] = None
                  ) -> bool:
       
       ...


When you're puzzled or when things are complicated
**************************************************

.. code-block:: python

   from typing import Union, Any, List, cast

   # To find out what type mypy infers for an expression anywhere in
   # your program, wrap it in reveal_type.  Mypy will print an error
   # message with the type; remove it again before running the code.
   reveal_type(1)  # -> error: Revealed type is 'builtins.int'

   # Use Union when something could be one of a few types.
   x = [3, 5, "test", "fun"]  # type: List[Union[int, str]]

   # Use Any if you don't know the type of something or it's too
   # dynamic to write a type for.
   x = mystery_function()  # type: Any

   # This is how to deal with varargs.
   # This makes each positional arg and each keyword arg a 'str'.
   def call(self, *args: str, **kwargs: str) -> str:
            request = make_request(*args, **kwargs)
            return self.do_api_query(request)

   # Use `ignore` to suppress type-checking on a given line, when your
   # code confuses mypy or runs into an outright bug in mypy.
   # Good practice is to comment every `ignore` with a bug link
   # (in mypy, typeshed, or your own code) or an explanation of the issue.
   x = confusing_function()  # type: ignore # https://github.com/python/mypy/issues/1167

   # cast is a helper function for mypy that allows for guidance of how to convert types.
   # it does not cast at runtime
   a = [4]
   b = cast(List[int], a)  # passes fine
   c = cast(List[str], a)  # passes fine (no runtime check)
   reveal_type(c)  # -> error: Revealed type is 'builtins.list[builtins.str]'
   print(c)  # -> [4] the object is not cast

   # if you want dynamic attributes on your class, have it override __setattr__ or __getattr__
   # in a stub or in your source code.
   # __setattr__ allows for dynamic assignment to names
   # __getattr__ allows for dynamic access to names
   class A:
       # this will allow assignment to any A.x, if x is the same type as `value`
       def __setattr__(self, name: str, value: int) -> None: ...
       # this will allow access to any A.x, if x is compatible with the return type
       def __getattr__(self, name: str) -> int: ...
   a.foo = 42  # works
   a.bar = 'Ex-parrot'  # fails type checking


   # TODO: explain "Need type annotation for variable" when
   # initializing with None or an empty container


Standard duck types
*******************

In typical Python code, many functions that can take a list or a dict
as an argument only need their argument to be somehow "list-like" or
"dict-like".  A specific meaning of "list-like" or "dict-like" (or
something-else-like) is called a "duck type", and several duck types
that are common in idiomatic Python are standardized.

.. code-block:: python

   from typing import Mapping, MutableMapping, Sequence, Iterable, List, Set

   # Use Iterable for generic iterables (anything usable in `for`),
   # and Sequence where a sequence (supporting `len` and `__getitem__`) is required.
   def f(iterable_of_ints: Iterable[int]) -> List[str]:
       return [str(x) for x in iterable_of_ints]
   f(range(1, 3))

   # Mapping describes a dict-like object (with `__getitem__`) that we won't mutate,
   # and MutableMapping one (with `__setitem__`) that we might.
   def f(my_dict: Mapping[int, str])-> List[int]:
       return list(my_dict.keys())
   f({3: 'yes', 4: 'no'})
   def f(my_mapping: MutableMapping[int, str]) -> Set[str]:
       my_mapping[5] = 'maybe'
       return set(my_mapping.values())
   f({3: 'yes', 4: 'no'})


Classes
*******

.. code-block:: python

   class MyClass:
       # The __init__ method doesn't return anything, so it gets return
       # type None just like any other method that doesn't return anything.
       def __init__(self) -> None:
           ...
       # For instance methods, omit `self`.
       def my_method(self, num: int, str1: str) -> str:
           return num * str1



   # User-defined classes are written with just their own names.
   x = MyClass() # type: MyClass


Other stuff
***********

.. code-block:: python

   import sys
   import re
   # typing.Match describes regex matches from the re module.
   from typing import Match, AnyStr, IO
   x = re.match(r'[0-9]+', "15")  # type: Match[str]

   # You can use AnyStr to indicate that any string type will work
   # but not to mix types
   def full_name(first: AnyStr, last: AnyStr) -> AnyStr:
       return first+last
   full_name('Jon','Doe')  # same str ok
   full_name(b'Bill', b'Bit')  # same binary ok
   full_name(b'Terry', 'Trouble')  # different str types, fails

   # Use IO[] for functions that should accept or return any
   # object that comes from an open() call. The IO[] does not
   # distinguish between reading, writing or other modes.
   def get_sys_IO(mode='w') -> IO[str]:
       if mode == 'w':
           return sys.stdout
       elif mode == 'r':
           return sys.stdin
       else:
           return sys.stdout

   # forward references are useful if you want to reference a class before it is designed
   
   def f(foo: A) -> int:  # this will fail
       ...
   
   class A:
       ...
       
   # however, using the string 'A', it will pass as long as there is a class of that name later on
   def f(foo: 'A') -> int:
       ...

   # TODO: add TypeVar and a simple generic function

Variable Annotation in Python 3.6 with PEP 526
**********************************************

Python 3.6 brings new syntax for annotating variables with `PEP 526 <https://www.python.org/dev/peps/pep-0526/>`_.
Mypy brings limited support for PEP 526 annotations.


.. code-block:: python

   # annotation is similar to arguments to functions
   name: str = "Eric Idle"
   
   # class instances can be annotated as follows
   mc : MyClass = MyClass()
   
   # tuple packing can be done as follows
   tu: Tuple[str, ...] = ('a', 'b', 'c')
   
   # annotations are not checked at runtime
   year: int = '1972'  # error in type checking, but works at runtime
   
   # these are all equivalent
   hour = 24 # type: int
   hour: int; hour = 24
   hour: int = 24
   
   # you do not (!) need to initialize a variable to annotate it
   a: int # ok for type checking and runtime
   
   # which is useful in conditional branches
   child: bool
   if age < 18:
       child = True
   else:
       child = False
   
   # annotations for classes are for instance variables (those created in __init__ or __new__)
   class Battery:
       charge_percent: int = 100  # this is an instance variable with a default value
       capacity: int  # an instance variable without a default
       
   # you can use the ClassVar annotation to make the variable a class variable instead of an instance variable.
   class Car:
       seats: ClassVar[int] = 4
       passengers: ClassVar[List[str]]
       
    # You can also declare the type of an attribute in __init__
    class Box:
        def __init__(self) -> None:
            self.items: List[str] = []
   
Please see :ref:`python-36` for more on mypy's compatibility with Python 3.6's new features.
