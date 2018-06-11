# Mypy Roadmap

The goal of the roadmap is to document areas the mypy core team is
planning to work on in the future or is currently working on. PRs
targeting these areas are very welcome, but please check first with a
core team member that nobody else is working on the same thing.

**Note:** This doesn’t include everything that the core team will work
on, and everything is subject to change.

- Continue making error messages more useful and informative.
  ([issue](https://github.com/python/mypy/labels/topic-usability))

- Refactor and simplify specific tricky parts of mypy internals, such
  as the [conditional type binder](https://github.com/python/mypy/issues/3457),
  [symbol tables](https://github.com/python/mypy/issues/3458) or
  the various [semantic analysis passes](https://github.com/python/mypy/issues/3459).

- Invest some effort into systematically filling in missing
  annotations and stubs in typeshed, with focus on features heavily
  used at Dropbox. Better support for ORMs will be a separate
  project.

- Make the mypy plugin architecture more general and officially
  supported. It should be able to support some typical ORM features at
  least, such as metaclasses that add methods with automatically
  inferred signatures and complex descriptors such as those used by
  Django models.
  ([issue](https://github.com/python/mypy/issues/1240))

- Implement editor plugins and/or document how to integrate mypy
  with popular editors. Support selected IDE features.
