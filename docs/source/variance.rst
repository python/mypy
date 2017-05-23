.. _invariance-vs-covariance:

Invariance vs covariance
------------------------

Most mutable generic collections are invariant, and mypy considers all
user-defined generic classes invariant by default
(see :ref:`variance-of-generics` for motivation). This could lead to some
unexpected errors when combined with type inference. For example:

.. code-block:: python

   class A: ...
   class B(A): ...

   lst = [A(), A()]  # Inferred type is List[A]
   new_lst = [B(), B()]  # inferred type is List[B]
   lst = new_lst  # mypy will complain about this, because List is invariant

Possible strategies in such situations are:

* Use an explicit type annotation:

  .. code-block:: python

     new_lst: List[A] = [B(), B()]
     lst = new_lst  # OK

* Make a copy of the right hand side:

  .. code-block:: python

     lst = list(new_lst) # Also OK

* Use immutable collections as annotations whenever possible:

  .. code-block:: python

     def f_bad(x: List[A]) -> A:
         return x[0]
     f_bad(new_lst) # Fails

     def f_good(x: Sequence[A]) -> A:
         return x[0]
     f_good(new_lst) # OK

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
