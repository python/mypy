Mypy syntax cheat sheet
=======================

This document is a quick cheat sheet showing how the PEP-484 type
language represents various common types in Python 2.

# document the cool print type feature of mypy here.

.. code-block:: python

   from typing import List, Dict, Set, Tuple, Union, Optional, Callable, Match
   from six import text_type

   # For builtin types, just use the name of the type
   x = 1 # type: int
   x = 1.0 # type: float
   x = "test" # type: str
   x = u"test" # type: unicode

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

   class MyClass(object):
       pass
   x = MyClass() # type: MyClass

   # This is how you annotate a function definition
   def stringify(num):
       # type: (int) -> str
       return str(num)

   # And here's how you specify multiple arguments
   def plus(num1, num2):
       # type: (int, int) -> int
       return num1 + num2

   # Add type annotations for kwargs as though they were positional args
   def f(myclass_element, my_float=3.5):
       # type: (MyClass, float) -> float
       return my_float + 3.5
   # This is how you annotate a function value
   x = f # type: Callable[[MyClass, float], float]

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

   from typing import Generator
   def f(n):
       # type: (int) -> Generator
       i = 0
       while i < n:
           yield i
           i += 1

   # TODO: Add typevar example

