# Mypy Roadmap

The goal of the roadmap is to document areas the mypy core team is
planning to work on in the future or is currently working on. PRs
targeting these areas are very welcome, but please check first with a
core team member that nobody else is working on the same thing.

**Note:** This doesn’t include everything that the core team will work
on, and everything is subject to change.

- Continue making error messages more useful and informative.
  ([issues](https://github.com/python/mypy/labels/topic-usability))

- Refactor and simplify specific tricky parts of mypy internals, such
  as the [conditional type binder](https://github.com/python/mypy/issues/3457)
  and the [semantic analyzer](https://github.com/python/mypy/issues/6204).

- Use the redesigned semantic analyzer to support general recursive types
  ([issue](https://github.com/python/mypy/issues/731)).

- Infer signature of a single function using static analysis and integrate this
  functionality in mypy daemon.

- Support user defined variadic generics (focus on the use cases needed for precise
  typing of decorators, see [issue](https://github.com/python/mypy/issues/3157)).

- Dedicated support for NumPy and Python numeric stack (including
  integer generics/shape types, and a NumPy plugin, see
  [issue](https://github.com/python/mypy/issues/3540)).

- Gradual improvements to [mypyc compiler](https://github.com/mypyc/mypyc).

- Invest some effort into systematically filling in missing
  stubs in typeshed, with focus on libraries heavily used at Dropbox.
  Help with [typeshed transformation](https://github.com/python/typeshed/issues/2491)
  if needed.

- Support selected IDE features and deeper editor integrations.
