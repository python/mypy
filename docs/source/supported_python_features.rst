Supported Python features and modules
=====================================

Lists of supported Python features and standard library modules are
maintained in the mypy wiki:

- `Supported Python features <http://www.mypy-lang.org/wiki/SupportedPythonFeatures>`_
- `Supported Python modules <http://www.mypy-lang.org/wiki/SupportedPythonModules>`_

Runtime definition of methods and functions
*******************************************

By default, mypy will complain if you add a function to a class
or module outside its definition -- but only if this is visible to the
type checker. This only affects static checking, as mypy performs no
additional type checking at runtime. You can easily work around
this. For example, you can use dynamically typed code or values with
``Any`` types, or you can use ``setattr`` or other introspection
features. However, you need to be careful if you decide to do this. If
used indiscriminately, you may have difficulty using static typing
effectively, since the type checker cannot see functions defined at
runtime.
