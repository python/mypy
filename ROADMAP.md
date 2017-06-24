# Mypy Roadmap

The goal of the roadmap is to document areas the mypy core team is
planning to work on in the future or is currently working on. PRs
targeting these areas are very welcome, but please check first with a
core team member that nobody else is working on the same thing.

**Note:** This doesn’t include everything that the core team will work
on, and everything is subject to change. Near-term plans are likely
more accurate.

## April-June 2017

- Add more comprehensive testing for `--incremental` and `--quick`
  modes to improve reliability. At least write more unit tests with
  focus on areas that have previously had bugs.
  ([issue](https://github.com/python/mypy/issues/3455))

- Speed up `--quick` mode to better support million+ line codebases
  through some of these:

  - Make it possible to use remote caching for incremental cache
    files. This would speed up a cold run with no local cache data.
    We need to update incremental cache to use hashes to determine
    whether files have changes to allow
    [sharing cache data](https://github.com/python/mypy/issues/3403).

  - See if we can speed up deserialization of incremental cache
    files. Initial experiments aren’t very promising though so there
    might not be any easy wins left.
    ([issue](https://github.com/python/mypy/issues/3456))

- Improve support for complex signatures such as `open(fn, 'rb')` and
  specific complex decorators such as `contextlib.contextmanager`
  through type checker plugins/hooks.
  ([issue](https://github.com/python/mypy/issues/1240))

- Document basic properties of all type operations used within mypy,
  including compatibility, proper subtyping, joins and meets.
  ([issue](https://github.com/python/mypy/issues/3454))

- Make TypedDict an officially supported mypy feature. This makes it
  possible to give precise types for dictionaries that represent JSON
  objects, such as `{"path": "/dir/fnam.ext", "size": 1234}`.
  ([issue](https://github.com/python/mypy/issues/3453))

- Make error messages more useful and informative.
  ([issue](https://github.com/python/mypy/labels/topic-usability))

- Resolve [#2008](https://github.com/python/mypy/issues/2008) (we are
  converging on approach 4).

## July-December 2017

- Invest some effort into systematically filling in missing
  annotations and stubs in typeshed, with focus on features heavily
  used at Dropbox. Better support for ORMs will be a separate
  project.

- Improve opt-in warnings about `Any` types to make it easier to keep
  code free from unwanted `Any` types. For example, warn about using
  `list` (instead of `List[x]`) and calling `open` if we can’t infer a
  precise return type, or using types imported from ignored modules
  (they are implicitly `Any`).

- Add support for protocols and structural subtyping (PEP 544).

- Switch completely to pytest and remove the custom testing framework.
  ([issue](https://github.com/python/mypy/issues/1673))

- Make it possible to run mypy as a daemon to avoid reprocessing the
  entire program on each run. This will improve performance
  significantly. Even when using the incremental mode, processing a
  large number of files is not cheap.

- Refactor and simplify specific tricky parts of mypy internals, such
  as the [conditional type binder](https://github.com/python/mypy/issues/3457),
  [symbol tables](https://github.com/python/mypy/issues/3458) or
  the various [semantic analysis passes](https://github.com/python/mypy/issues/3459).

- Implement a general type system plugin architecture. It should be
  able to support some typical ORM features at least, such as
  metaclasses that add methods with automatically inferred signatures
  and complex descriptors such as those used by Django models.
  ([issue](https://github.com/python/mypy/issues/1240))

- Add support for statically typed
  [protobufs](https://developers.google.com/protocol-buffers/).

- Provide much faster, reliable interactive feedback through
  fine-grained incremental type checking, built on top the daemon
  mode.

- Start work on editor plugins and support for selected IDE features.

- Turn on `--strict-optional` by default.
