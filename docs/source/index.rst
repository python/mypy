.. Mypy documentation master file, created by
   sphinx-quickstart on Sun Sep 14 19:50:35 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to mypy documentation!
==============================

Mypy is a static type checker for Python 3 and Python 2.7. If you sprinkle
your code with type annotations, mypy can type check your code and find common
bugs. As mypy is a static analyzer, or a lint-like tool, the type
annotations are just hints for mypy and don't interfere when running your program.
You run your program with a standard Python interpreter, and the annotations
are treated effectively as comments.

Using the Python 3 annotation syntax (using :pep:`484` and :pep:`526` notation)
or a comment-based annotation syntax for Python 2 code, you will be able to
efficiently annotate your code and use mypy to check the code for common errors.
Mypy has a powerful and easy-to-use type system with modern features such as
type inference, generics, callable types, tuple types, union types, and
structural subtyping.

As a developer, you decide how to use mypy in your workflow. You can always
escape to dynamic typing as mypy's approach to static typing doesn't restrict
what you can do in your programs. Using mypy will make your programs easier to
understand, debug, and maintain.

This documentation provides a short introduction to mypy. It will help you
get started writing statically typed code. Knowledge of Python and a
statically typed object-oriented language, such as Java, are assumed.

.. note::

   Mypy is used in production by many companies and projects, but mypy is
   officially beta software. There will be occasional changes
   that break backward compatibility. The mypy development team tries to
   minimize the impact of changes to user code.

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: First steps

   getting_started
   existing_code

.. _overview-cheat-sheets:

.. toctree::
   :maxdepth: 2
   :caption: Cheat sheets

   cheat_sheet_py3
   cheat_sheet

.. _overview-type-system-reference:

.. toctree::
   :maxdepth: 2
   :caption: Type system reference

   builtin_types
   type_inference_and_annotations
   kinds_of_types
   class_basics
   runtime_troubles
   protocols
   dynamic_typing
   python2
   type_narrowing
   duck_type_compatibility
   stubs
   generics
   more_types
   literal_types
   final_attrs
   metaclasses

.. toctree::
   :maxdepth: 2
   :caption: Configuring and running mypy

   running_mypy
   command_line
   config_file
   inline_config
   mypy_daemon
   installed_packages
   extending_mypy
   stubgen
   stubtest

.. toctree::
   :maxdepth: 2
   :caption: Miscellaneous

   common_issues
   supported_python_features
   error_codes
   error_code_list
   error_code_list2
   additional_features
   faq

.. toctree::
   :hidden:
   :caption: Project Links

   GitHub <https://github.com/python/mypy>
   Website <http://mypy-lang.org/>

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
