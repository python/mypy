Mypy syntax cheat sheet (Python 2)
==================================

This document is a quick cheat sheet showing how the PEP-484 type
language represents various common types in Python 2.

.. note::

   Technically many of the type annotations shown below are redundant,
   because mypy can derive them from the type of the expression.  So
   many of the examples have a dual purpose: show how to write the
   annotation, and show the inferred types.

.. code-block:: python

   from typing import List, Dict, Set, Tuple, Union, Optional, Callable, Match
   from six import text_type

   # For builtin types, just use the name of the type
   x = 1 # type: int
   x = 1.0 # type: float
   x = "test" # type: str
   x = u"test" # type: unicode

   # Print an error message giving the type of x (it's also a runtime
   # error, so don't leave it in)
   reveal_type(x)

   # For collections, the name of the type is capitalized, and the
   # name of the type in the collection is in brackets.
   x = [1] # type: List[int]
   x = set([6, 7]) # type: Set[int]
   # For mappings, we need the types of both keys and values
   x = dict(field=2.0) # type: Dict[str, float]
   # For tuples, we specify the types of all the elements
   x = (3, "yes", 7.5) # type: Tuple[int, str, float]

   # six.text_type is str/unicode in Python 2 and string but not bytes in Python 3
   x = ["string", u"unicode"] # type: List[text_type]
   # If something could be one of a few types, use Union
   x = [3, 5, "test", "fun"] # type: List[Union[int, str]]
   x = re.match(r'[0-9]+', "15") # type: Match[str]

   # If you don't know the type of something, you can use Any
   x = mystery_function() # type: Any
   # And if you want to have something not be type-checked, you can
   # use ignore to suppress mypy warnings for a given line
   # Ideally, one would never use this
   x = confusing_function() # type: ignore

   # This is how you annotate a function definition
   def stringify(num):
       # type: (int) -> str
       """Your function docstring goes here after the type definition."""
       return str(num)

   # And here's how you specify multiple arguments
   def plus(num1, num2):
       # type: (int, int) -> int
       return num1 + num2

   # Add type annotations for kwargs as though they were positional args
   def f(num1, my_float=3.5):
       # type: (int, float) -> float
       return num1 + my_float
   # This is how you annotate a function value
   x = f # type: Callable[[int, float], float]

   # Use Optional[Type] for objects that could be None
   def f(input_str=None):
       # type: (Optional[str]) -> int
       if input_str is not None:
           return len(input_str)
       return 0

   from typing import Mapping, MutableMapping
   # Dict is a python dictionary
   # MutableMapping is an abstract base class for a dict-type thing
   # Mapping is an abtract base class for a dict-type thing that may
   # not support writing to the mapping
   def f(my_dict):
       # type: (Mapping[int, str]) -> List[int]
       return list(my_dict.keys())
   f({3: 'yes', 4: 'no'})

   def f(my_mapping):
       # type: (MutableMapping[int, str]) -> Set[str]
       my_dict[5] = 'maybe'
       return set(my_dict.values())
   f({3: 'yes', 4: 'no'})

   from typing import Sequence, Iterable, Generator
   # Use Iterable[Type] for generic iterators
   # Sequence[Type] is abstract base class for list-like iterables
   def f(iterator_of_ints):
       # type: (Sequence[int]) -> List[str]
       return [str(x) for x in iterator_of_ints]
   f(range(1, 3))

   from typing import Tuple
   def f(my_tuple):
       # type: (Tuple[int, int]) -> int
       return sum([val for val in my_tuple])
   f((1, 2))

   from typing import Iterator
   def f(n):
       # type: (int) -> Iterator[int]
       i = 0
       while i < n:
           yield i
           i += 1
   f(5)

   # TODO: Add typevar example

   # This is how you annotate a class with '__init__' constructor and a method.
   class MyClass(object):
       """This is where your class docstring goes."""

       def __init__(self):
           # type: () -> None
           """Add your constructor stuff here."""
           pass

       def my_class_method(self, num, str1):
           # type: (int, str) -> str
           """Returns 'str1' repeated 'num' times."""
           return num * str1

   x = MyClass() # type: MyClass
