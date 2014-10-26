Dynamically typed code
======================

As mentioned earlier, bodies of functions that don't have have an explicit return type are dynamically typed (operations are checked at runtime). Code outside functions is statically typed by default, and types of variables are inferred. This does usually the right thing, but you can also make any variable dynamically typed by defining it explicitly with the type Any:

.. code-block:: python

   from typing import Any

   s = 1                 # Statically typed (type int)
   d = 1  # type: Any    # Dynamically typed (type Any)
   s = 'x'               # Type check error
   d = 'x'               # OK

Alternatively, you can use the Undefined construct to define dynamically typed variables, as Any can be used anywhere any other type is valid:

.. code-block:: python

   from typing import Undefined, Any

   d = Undefined(Any)
   d = 1   # OK
   d = 'x' # OK

Additionally, if you don't import the typing module in a file, all code outside functions will be dynamically typed by default, and the file is not type checked at all. This mode makes it easy to include existing Python code that is not trivially compatible with static typing.

.. note::

   The current mypy version type checks all modules, even those that don't import typing. This will change in a future version.
