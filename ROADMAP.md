# Mypy Roadmap

The goal of the roadmap is to document areas the mypy core team is
planning to work on in the future or is currently working on. PRs
targeting these areas are very welcome, but please check first with a
core team member that nobody else is working on the same thing.

**Note:** This doesn’t include everything that the core team will work
on, and everything is subject to change. Near-term plans are likely
more accurate.

## September-December 2017

- Fix remaining highest-priority TypedDict issues and make TypedDict
  an officially supported mypy feature.

- Add support for protocols and structural subtyping (PEP 544).

- Continue making error messages more useful and informative.
  ([issue](https://github.com/python/mypy/labels/topic-usability))

- Switch completely to pytest and remove the custom testing framework.
  ([issue](https://github.com/python/mypy/issues/1673))

- Make it possible to run mypy as a daemon to avoid reprocessing the
  entire program on each run. This will improve performance
  significantly. Even when using the incremental mode, processing a
  large number of files is not cheap.

- Provide much faster, reliable interactive feedback through
  fine-grained incremental type checking, built on top the daemon
  mode.

- Document basic properties of all type operations used within mypy,
  including compatibility, proper subtyping, joins and meets.
  ([issue](https://github.com/python/mypy/issues/3454))

## 2018

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

- Add support for statically typed
  [protobufs](https://developers.google.com/protocol-buffers/).

- Start work on editor plugins and support for selected IDE features.

- Turn on `--strict-optional` by default.
