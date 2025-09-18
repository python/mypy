# Mypy Release Notes

## Next Release

## Mypy 1.18.1

We’ve just uploaded mypy 1.18.1 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)).
Mypy is a static type checker for Python. This release includes new features, performance
improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Mypy Performance Improvements

Mypy 1.18.1 includes numerous performance improvements, resulting in about 40% speedup
compared to 1.17 when type checking mypy itself. In extreme cases, the improvement
can be 10x or higher. The list below is an overview of the various mypy optimizations.
Many mypyc improvements (discussed in a separate section below) also improve performance.

Type caching optimizations have a small risk of causing regressions. When
reporting issues with unexpected inferred types, please also check if
`--disable-expression-cache` will work around the issue, as it turns off some of
these optimizations.

- Improve self check performance by 1.8% (Jukka Lehtosalo, PR [19768](https://github.com/python/mypy/pull/19768), [19769](https://github.com/python/mypy/pull/19769), [19770](https://github.com/python/mypy/pull/19770))
- Optimize fixed-format deserialization (Ivan Levkivskyi, PR [19765](https://github.com/python/mypy/pull/19765))
- Use macros to optimize fixed-format deserialization (Ivan Levkivskyi, PR [19757](https://github.com/python/mypy/pull/19757))
- Two additional micro‑optimizations (Ivan Levkivskyi, PR [19627](https://github.com/python/mypy/pull/19627))
- Another set of micro‑optimizations (Ivan Levkivskyi, PR [19633](https://github.com/python/mypy/pull/19633))
- Cache common types (Ivan Levkivskyi, PR [19621](https://github.com/python/mypy/pull/19621))
- Skip more method bodies in third‑party libraries for speed (Ivan Levkivskyi, PR [19586](https://github.com/python/mypy/pull/19586))
- Simplify the representation of callable types (Ivan Levkivskyi, PR [19580](https://github.com/python/mypy/pull/19580))
- Add cache for types of some expressions (Ivan Levkivskyi, PR [19505](https://github.com/python/mypy/pull/19505))
- Use cache for dictionary expressions (Ivan Levkivskyi, PR [19536](https://github.com/python/mypy/pull/19536))
- Use cache for binary operations (Ivan Levkivskyi, PR [19523](https://github.com/python/mypy/pull/19523))
- Cache types of type objects (Ivan Levkivskyi, PR [19514](https://github.com/python/mypy/pull/19514))
- Avoid duplicate work when checking boolean operations (Ivan Levkivskyi, PR [19515](https://github.com/python/mypy/pull/19515))
- Optimize generic inference passes (Ivan Levkivskyi, PR [19501](https://github.com/python/mypy/pull/19501))
- Speed up the default plugin (Jukka Lehtosalo, PRs [19385](https://github.com/python/mypy/pull/19385) and [19462](https://github.com/python/mypy/pull/19462))
- Remove nested imports from the default plugin (Ivan Levkivskyi, PR [19388](https://github.com/python/mypy/pull/19388))
- Micro‑optimize type expansion (Jukka Lehtosalo, PR [19461](https://github.com/python/mypy/pull/19461))
- Micro‑optimize type indirection (Jukka Lehtosalo, PR [19460](https://github.com/python/mypy/pull/19460))
- Micro‑optimize the plugin framework (Jukka Lehtosalo, PR [19464](https://github.com/python/mypy/pull/19464))
- Avoid temporary set creation in subtype checking (Jukka Lehtosalo, PR [19463](https://github.com/python/mypy/pull/19463))
- Subtype checking micro‑optimization (Jukka Lehtosalo, PR [19384](https://github.com/python/mypy/pull/19384))
- Return early where possible in subtype check (Stanislav Terliakov, PR [19400](https://github.com/python/mypy/pull/19400))
- Deduplicate some types before joining (Stanislav Terliakov, PR [19409](https://github.com/python/mypy/pull/19409))
- Speed up type checking by caching argument inference context (Jukka Lehtosalo, PR [19323](https://github.com/python/mypy/pull/19323))
- Optimize binding method self argument type and deprecation checks (Ivan Levkivskyi, PR [19556](https://github.com/python/mypy/pull/19556))
- Keep trivial instance types/aliases during expansion (Ivan Levkivskyi, PR [19543](https://github.com/python/mypy/pull/19543))

### Fixed‑Format Cache (Experimental)

Mypy now supports a new cache format used for faster incremental builds. It makes
incremental builds up to twice as fast. The feature is experimental and
currently only supported when using a compiled version of mypy. Use `--fixed-format-cache`
to enable the new format, or `fixed_format_cache = True` in a configuration file.

We plan to enable this by default in a future mypy release, and we'll eventually
deprecate and remove support for the original JSON-based format.

Unlike the JSON-based cache format, the new binary format is currently
not easy to parse and inspect by mypy users. We are planning to provide a tool to
convert fixed-format cache files to JSON, but details of the output JSON may be
different from the current JSON format. If you rely on being able to inspect
mypy cache files, we recommend creating a GitHub issue and explaining your use
case, so that we can more likely provide support for it. (Using
`MypyFile.read(binary_data)` to inspect cache data may be sufficient to support
some use cases.)

This feature was contributed by Ivan Levkivskyi (PR [19668](https://github.com/python/mypy/pull/19668), [19735](https://github.com/python/mypy/pull/19735), [19750](https://github.com/python/mypy/pull/19750), [19681](https://github.com/python/mypy/pull/19681), [19752](https://github.com/python/mypy/pull/19752), [19815](https://github.com/python/mypy/pull/19815)).

### Flexible Variable Definitions: Update

Mypy 1.16.0 introduced `--allow-redefinition-new`, which allows redefining variables
with different types, and inferring union types for variables from multiple assignments.
The feature is now documented in the `--help` output, but the feature is still experimental.

We are planning to enable this by default in mypy 2.0, and we will also deprecate the
older `--allow-redefinition` flag. Since the new behavior differs significantly from
the older flag, we encourage users of `--allow-redefinition` to experiment with
`--allow-redefinition-new` and create a GitHub issue if the new functionality doesn't
support some important use cases.

This feature was contributed by Jukka Lehtosalo.

### Inferred Type for Bare ClassVar

A ClassVar without an explicit type annotation now causes the type of the variable
to be inferred from the initializer:


```python
from typing import ClassVar

class Item:
    # Type of 'next_id' is now 'int' (it was 'Any')
    next_id: ClassVar = 1

    ...
```

This feature was contributed by Ivan Levkivskyi (PR [19573](https://github.com/python/mypy/pull/19573)).

### Disjoint Base Classes (@disjoint_base, PEP 800)

Mypy now understands disjoint bases (PEP 800): it recognizes the `@disjoint_base`
decorator, and rejects class definitions that combine mutually incompatible base classes,
and takes advantage of the fact that such classes cannot exist in reachability and
narrowing logic.

This class definition will now generate an error:

```python
# Error: Class "Bad" has incompatible disjoint bases
class Bad(str, Exception):
    ...
```

This feature was contributed by Jelle Zijlstra (PR [19678](https://github.com/python/mypy/pull/19678)).

### Miscellaneous New Mypy Features

- Add `--strict-equality-for-none` to flag non-overlapping comparisons involving None (Christoph Tyralla, PR [19718](https://github.com/python/mypy/pull/19718))
- Don’t show import‑related errors after a module‑level assert such as `assert sys.platform == "linux"` that is always false (Stanislav Terliakov, PR [19347](https://github.com/python/mypy/pull/19347))

### Improvements to Match Statements

- Add temporary named expressions for match subjects (Stanislav Terliakov, PR [18446](https://github.com/python/mypy/pull/18446))
- Fix unwrapping of assignment expressions in match subject (Marc Mueller, PR [19742](https://github.com/python/mypy/pull/19742))
- Omit errors for class patterns against object (Marc Mueller, PR [19709](https://github.com/python/mypy/pull/19709))
- Remove unnecessary error for certain match class patterns (Marc Mueller, PR [19708](https://github.com/python/mypy/pull/19708))
- Use union type for captured vars in or pattern (Marc Mueller, PR [19710](https://github.com/python/mypy/pull/19710))
- Prevent final reassignment inside match case (Omer Hadari, PR [19496](https://github.com/python/mypy/pull/19496))

### Fixes to Crashes

- Fix crash with variadic tuple arguments to a generic type (Randolf Scholz, PR [19705](https://github.com/python/mypy/pull/19705))
- Fix crash when enable_error_code in pyproject.toml has wrong type (wyattscarpenter, PR [19494](https://github.com/python/mypy/pull/19494))
- Prevent crash for dataclass with PEP 695 TypeVarTuple on Python 3.13+ (Stanislav Terliakov, PR [19565](https://github.com/python/mypy/pull/19565))
- Fix crash on settable property alias (Ivan Levkivskyi, PR [19615](https://github.com/python/mypy/pull/19615))

### Experimental Free-threading Support for Mypyc

All mypyc tests now pass on free-threading Python 3.14 release candidate builds. The performance
of various micro-benchmarks scale well across multiple threads.

Free-threading support is still experimental. Note that native attribute access
(get and set), list item access and certain other operations are still
unsafe when there are race conditions. This will likely change in the future.
You can follow the
[area-free-threading label](https://github.com/mypyc/mypyc/issues?q=is%3Aissue%20state%3Aopen%20label%3Aarea-free-threading)
in the mypyc issues tracker to follow progress.

Related PRs:
- Enable free‑threading when compiling multiple modules (Jukka Lehtosalo, PR [19541](https://github.com/python/mypy/pull/19541))
- Fix `list.pop` on free‑threaded builds (Jukka Lehtosalo, PR [19522](https://github.com/python/mypy/pull/19522))
- Make type objects immortal under free‑threading (Jukka Lehtosalo, PR [19538](https://github.com/python/mypy/pull/19538))

### Mypyc: Support `__new__`

Mypyc now has rudimentary support for user-defined `__new__` methods.

This feature was contributed by Piotr Sawicki (PR [19739](https://github.com/python/mypy/pull/19739)).

### Mypyc: Faster Generators and Async Functions

Generators and calls of async functions are now faster, sometimes by 2x or more.

Related PRs:
- Speed up for loops over native generators (Jukka Lehtosalo, PR [19415](https://github.com/python/mypy/pull/19415))
- Speed up native‑to‑native calls using await (Jukka Lehtosalo, PR [19398](https://github.com/python/mypy/pull/19398))
- Call generator helper directly in await expressions (Jukka Lehtosalo, PR [19376](https://github.com/python/mypy/pull/19376))
- Speed up generator allocation with per‑type freelists (Jukka Lehtosalo, PR [19316](https://github.com/python/mypy/pull/19316))

### Miscellaneous Mypyc Improvements

- Special‑case certain Enum method calls for speed (Ivan Levkivskyi, PR [19634](https://github.com/python/mypy/pull/19634))
- Fix issues related to subclassing and undefined attribute tracking (Chainfire, PR [19787](https://github.com/python/mypy/pull/19787))
- Fix invalid C function signature (Jukka Lehtosalo, PR [19773](https://github.com/python/mypy/pull/19773))
- Speed up implicit `__ne__` (Jukka Lehtosalo, PR [19759](https://github.com/python/mypy/pull/19759))
- Speed up equality with optional str/bytes types (Jukka Lehtosalo, PR [19758](https://github.com/python/mypy/pull/19758))
- Speed up access to empty tuples (BobTheBuidler, PR [19654](https://github.com/python/mypy/pull/19654))
- Speed up calls with `*args` (BobTheBuidler, PRs [19623](https://github.com/python/mypy/pull/19623) and [19631](https://github.com/python/mypy/pull/19631))
- Speed up calls with `**kwargs` (BobTheBuidler, PR [19630](https://github.com/python/mypy/pull/19630))
- Optimize `type(x)`, `x.__class__`, and `<type>.__name__` (Jukka Lehtosalo, PR [19691](https://github.com/python/mypy/pull/19691), [19683](https://github.com/python/mypy/pull/19683))
- Specialize `bytes.decode` for common encodings (Jukka Lehtosalo, PR [19688](https://github.com/python/mypy/pull/19688))
- Speed up `in` operations using final fixed‑length tuples (Jukka Lehtosalo, PR [19682](https://github.com/python/mypy/pull/19682))
- Optimize f‑string building from final values (BobTheBuidler, PR [19611](https://github.com/python/mypy/pull/19611))
- Add dictionary set item for exact dict instances (BobTheBuidler, PR [19657](https://github.com/python/mypy/pull/19657))
- Cache length when iterating over immutable types (BobTheBuidler, PR [19656](https://github.com/python/mypy/pull/19656))
- Fix name conflict related to attributes of generator classes (Piotr Sawicki, PR [19535](https://github.com/python/mypy/pull/19535))
- Fix segfault from heap type objects with a static docstring (Brian Schubert, PR [19636](https://github.com/python/mypy/pull/19636))
- Unwrap NewType to its base type for additional optimizations (BobTheBuidler, PR [19497](https://github.com/python/mypy/pull/19497))
- Generate an export table only for separate compilation (Jukka Lehtosalo, PR [19521](https://github.com/python/mypy/pull/19521))
- Speed up `isinstance` with built‑in types (Piotr Sawicki, PR [19435](https://github.com/python/mypy/pull/19435))
- Use native integers for some sequence indexing (Jukka Lehtosalo, PR [19426](https://github.com/python/mypy/pull/19426))
- Speed up `isinstance(obj, list)` (Piotr Sawicki, PR [19416](https://github.com/python/mypy/pull/19416))
- Report error on reserved method names (Piotr Sawicki, PR [19407](https://github.com/python/mypy/pull/19407))
- Speed up string equality (Jukka Lehtosalo, PR [19402](https://github.com/python/mypy/pull/19402))
- Raise `NameError` on undefined names (Piotr Sawicki, PR [19395](https://github.com/python/mypy/pull/19395))
- Use per‑type freelists for nested functions (Jukka Lehtosalo, PR [19390](https://github.com/python/mypy/pull/19390))
- Simplify comparison of tuple elements (Piotr Sawicki, PR [19396](https://github.com/python/mypy/pull/19396))
- Generate introspection signatures for compiled functions (Brian Schubert, PR [19307](https://github.com/python/mypy/pull/19307))
- Fix undefined attribute checking special case (Jukka Lehtosalo, PR [19378](https://github.com/python/mypy/pull/19378))
- Fix comparison of tuples with different lengths (Piotr Sawicki, PR [19372](https://github.com/python/mypy/pull/19372))
- Speed up `list.clear` (Jahongir Qurbonov, PR [19344](https://github.com/python/mypy/pull/19344))
- Speed up `weakref.proxy` (BobTheBuidler, PR [19217](https://github.com/python/mypy/pull/19217))
- Speed up `weakref.ref` (BobTheBuidler, PR [19099](https://github.com/python/mypy/pull/19099))
- Speed up `str.count` (BobTheBuidler, PR [19264](https://github.com/python/mypy/pull/19264))

### Stubtest Improvements
- Add temporary `--ignore-disjoint-bases` flag to ease PEP 800 migration (Joren Hammudoglu, PR [19740](https://github.com/python/mypy/pull/19740))
- Flag redundant uses of `@disjoint_base` (Jelle Zijlstra, PR [19715](https://github.com/python/mypy/pull/19715))
- Improve signatures for `__init__` of C extension classes (Stephen Morton, PR [18259](https://github.com/python/mypy/pull/18259))
- Handle overloads with mixed positional‑only parameters (Stephen Morton, PR [18287](https://github.com/python/mypy/pull/18287))
- Use “parameter” (not “argument”) in error messages (PrinceNaroliya, PR [19707](https://github.com/python/mypy/pull/19707))
- Don’t require `@disjoint_base` when `__slots__` imply finality (Jelle Zijlstra, PR [19701](https://github.com/python/mypy/pull/19701))
- Allow runtime‑existing aliases of `@type_check_only` types (Brian Schubert, PR [19568](https://github.com/python/mypy/pull/19568))
- More detailed checking of type objects in stubtest (Stephen Morton, PR [18251](https://github.com/python/mypy/pull/18251))
- Support running stubtest in non-UTF8 terminals (Stanislav Terliakov, PR [19085](https://github.com/python/mypy/pull/19085))

### Documentation Updates

- Add idlemypyextension to IDE integrations (CoolCat467, PR [18615](https://github.com/python/mypy/pull/18615))
- Document that `object` is often preferable to `Any` in APIs (wyattscarpenter, PR [19103](https://github.com/python/mypy/pull/19103))
- Include a detailed listing of flags enabled by `--strict` (wyattscarpenter, PR [19062](https://github.com/python/mypy/pull/19062))
- Update “common issues” (reveal_type/reveal_locals; note on orjson) (wyattscarpenter, PR [19059](https://github.com/python/mypy/pull/19059), [19058](https://github.com/python/mypy/pull/19058))

### Other Notable Fixes and Improvements

- Remove deprecated `--new-type-inference` flag (the new algorithm has long been default) (Ivan Levkivskyi, PR [19570](https://github.com/python/mypy/pull/19570))
- Use empty context as a fallback for return expressions when outer context misleads inference (Ivan Levkivskyi, PR [19767](https://github.com/python/mypy/pull/19767))
- Fix forward references in type parameters of over‑parameterized PEP 695 aliases (Brian Schubert, PR [19725](https://github.com/python/mypy/pull/19725))
- Don’t expand PEP 695 aliases when checking node fullnames (Brian Schubert, PR [19699](https://github.com/python/mypy/pull/19699))
- Don’t use outer context for 'or' expression inference when LHS is Any (Stanislav Terliakov, PR [19748](https://github.com/python/mypy/pull/19748))
- Recognize buffer protocol special methods (Brian Schubert, PR [19581](https://github.com/python/mypy/pull/19581))
- Support attribute access on enum members correctly (Stanislav Terliakov, PR [19422](https://github.com/python/mypy/pull/19422))
- Check `__slots__` assignments on self types (Stanislav Terliakov, PR [19332](https://github.com/python/mypy/pull/19332))
- Move self‑argument checks after decorator application (Stanislav Terliakov, PR [19490](https://github.com/python/mypy/pull/19490))
- Infer empty list for `__slots__` and module `__all__` (Stanislav Terliakov, PR [19348](https://github.com/python/mypy/pull/19348))
- Use normalized tuples for fallback calculation (Stanislav Terliakov, PR [19111](https://github.com/python/mypy/pull/19111))
- Preserve literals when joining similar types (Stanislav Terliakov, PR [19279](https://github.com/python/mypy/pull/19279))
- Allow adjacent conditionally‑defined overloads (Stanislav Terliakov, PR [19042](https://github.com/python/mypy/pull/19042))
- Check property decorators more strictly (Stanislav Terliakov, PR [19313](https://github.com/python/mypy/pull/19313))
- Support properties with generic setters (Ivan Levkivskyi, PR [19298](https://github.com/python/mypy/pull/19298))
- Generalize class/static method and property alias support (Ivan Levkivskyi, PR [19297](https://github.com/python/mypy/pull/19297))
- Re‑widen custom properties after narrowing (Ivan Levkivskyi, PR [19296](https://github.com/python/mypy/pull/19296))
- Avoid erasing type objects when checking runtime cover (Shantanu, PR [19320](https://github.com/python/mypy/pull/19320))
- Include tuple fallback in constraints built from tuple types (Stanislav Terliakov, PR [19100](https://github.com/python/mypy/pull/19100))
- Somewhat better isinstance support on old‑style unions (Shantanu, PR [19714](https://github.com/python/mypy/pull/19714))
- Improve promotions inside unions (Christoph Tyralla, PR [19245](https://github.com/python/mypy/pull/19245))
- Treat uninhabited types as having all attributes (Ivan Levkivskyi, PR [19300](https://github.com/python/mypy/pull/19300))
- Improve metaclass conflict checks (Robsdedude, PR [17682](https://github.com/python/mypy/pull/17682))
- Fixes to metaclass resolution algorithm (Robsdedude, PR [17713](https://github.com/python/mypy/pull/17713))
- PEP 702 @deprecated: handle “combined” overloads (Christoph Tyralla, PR [19626](https://github.com/python/mypy/pull/19626))
- PEP 702 @deprecated: include overloads in snapshot descriptions (Christoph Tyralla, PR [19613](https://github.com/python/mypy/pull/19613))
- Ignore overload implementation when checking `__OP__` / `__rOP__` compatibility (Stanislav Terliakov, PR [18502](https://github.com/python/mypy/pull/18502))
- Support `_value_` as a fallback for ellipsis Enum members (Stanislav Terliakov, PR [19352](https://github.com/python/mypy/pull/19352))
- Sort arguments in TypedDict overlap messages (Marc Mueller, PR [19666](https://github.com/python/mypy/pull/19666))
- Fix handling of implicit return in lambda (Stanislav Terliakov, PR [19642](https://github.com/python/mypy/pull/19642))
- Improve behavior of uninhabited types (Stanislav Terliakov, PR [19648](https://github.com/python/mypy/pull/19648))
- Fix overload diagnostics when `*args` and `**kwargs` both match (Shantanu, PR [19614](https://github.com/python/mypy/pull/19614))
- Further fix overload diagnostics for `*args`/`**kwargs` (Shantanu, PR [19619](https://github.com/python/mypy/pull/19619))
- Show type variable name in "Cannot infer type argument" (Brian Schubert, PR [19290](https://github.com/python/mypy/pull/19290))
- Fail gracefully on unsupported template strings (PEP 750) (Brian Schubert, PR [19700](https://github.com/python/mypy/pull/19700))
- Revert colored argparse help for Python 3.14 (Marc Mueller, PR [19721](https://github.com/python/mypy/pull/19721))
- Update stubinfo for latest typeshed (Shantanu, PR [19771](https://github.com/python/mypy/pull/19771))
- Fix dict assignment when an incompatible same‑shape TypedDict exists (Stanislav Terliakov, PR [19592](https://github.com/python/mypy/pull/19592))
- Fix constructor type for subclasses of Any (Ivan Levkivskyi, PR [19295](https://github.com/python/mypy/pull/19295))
- Fix TypeGuard/TypeIs being forgotten in some cases (Brian Schubert, PR [19325](https://github.com/python/mypy/pull/19325))
- Fix TypeIs negative narrowing for unions of generics (Brian Schubert, PR [18193](https://github.com/python/mypy/pull/18193))
- dmypy suggest: Fix incorrect signature suggestion when a type matches a module name (Brian Schubert, PR [18937](https://github.com/python/mypy/pull/18937))
- dmypy suggest: Fix interaction with `__new__` (Stanislav Terliakov, PR [18966](https://github.com/python/mypy/pull/18966))
- dmypy suggest: Support Callable / callable Protocols in decorator unwrapping (Anthony Sottile, PR [19072](https://github.com/python/mypy/pull/19072))
- Fix missing error when redeclaring a type variable in a nested generic class (Brian Schubert, PR [18883](https://github.com/python/mypy/pull/18883))
- Fix for overloaded type object erasure (Shantanu, PR [19338](https://github.com/python/mypy/pull/19338))
- Fix TypeGuard with call on temporary object (Saul Shanabrook, PR [19577](https://github.com/python/mypy/pull/19577))

### Typeshed Updates

Please see [git log](https://github.com/python/typeshed/commits/main?after=2480d7e7c74493a024eaf254c5d2c6f452c80ee2+0&branch=main&path=stdlib) for full list of standard library typeshed stub changes.

### Mypy 1.18.2

- Fix crash on recursive alias (Ivan Levkivskyi, PR [19845](https://github.com/python/mypy/pull/19845))
- Add additional guidance for stubtest errors when runtime is `object.__init__` (Stephen Morton, PR [19733](https://github.com/python/mypy/pull/19733))
- Fix handling of None values in f-string expressions in mypyc (BobTheBuidler, PR [19846](https://github.com/python/mypy/pull/19846))

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

- Ali Hamdan
- Anthony Sottile
- BobTheBuidler
- Brian Schubert
- Chainfire
- Charlie Denton
- Christoph Tyralla
- CoolCat467
- Daniel Hnyk
- Emily
- Emma Smith
- Ethan Sarp
- Ivan Levkivskyi
- Jahongir Qurbonov
- Jelle Zijlstra
- Joren Hammudoglu
- Jukka Lehtosalo
- Marc Mueller
- Omer Hadari
- Piotr Sawicki
- PrinceNaroliya
- Randolf Scholz
- Robsdedude
- Saul Shanabrook
- Shantanu
- Stanislav Terliakov
- Stephen Morton
- wyattscarpenter

I’d also like to thank my employer, Dropbox, for supporting mypy development.

## Mypy 1.17

We’ve just uploaded mypy 1.17 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)).
Mypy is a static type checker for Python. This release includes new features and bug fixes.
You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Optionally Check That Match Is Exhaustive

Mypy can now optionally generate an error if a match statement does not
match exhaustively, without having to use `assert_never(...)`. Enable
this by using `--enable-error-code exhaustive-match`.

Example:

```python
# mypy: enable-error-code=exhaustive-match

import enum

class Color(enum.Enum):
    RED = 1
    BLUE = 2

def show_color(val: Color) -> None:
    # error: Unhandled case for values of type "Literal[Color.BLUE]"
    match val:
        case Color.RED:
            print("red")
```

This feature was contributed by Donal Burns (PR [19144](https://github.com/python/mypy/pull/19144)).

### Further Improvements to Attribute Resolution

This release includes additional improvements to how attribute types
and kinds are resolved. These fix many bugs and overall improve consistency.

* Handle corner case: protocol/class variable/descriptor (Ivan Levkivskyi, PR [19277](https://github.com/python/mypy/pull/19277))
* Fix a few inconsistencies in protocol/type object interactions (Ivan Levkivskyi, PR [19267](https://github.com/python/mypy/pull/19267))
* Refactor/unify access to static attributes (Ivan Levkivskyi, PR [19254](https://github.com/python/mypy/pull/19254))
* Remove inconsistencies in operator handling (Ivan Levkivskyi, PR [19250](https://github.com/python/mypy/pull/19250))
* Make protocol subtyping more consistent (Ivan Levkivskyi, PR [18943](https://github.com/python/mypy/pull/18943))

### Fixes to Nondeterministic Type Checking

Previous mypy versions could infer different types for certain expressions
across different runs (typically depending on which order certain types
were processed, and this order was nondeterministic). This release includes
fixes to several such issues.

* Fix nondeterministic type checking by making join with explicit Protocol and type promotion commute (Shantanu, PR [18402](https://github.com/python/mypy/pull/18402))
* Fix nondeterministic type checking caused by nonassociative of None joins (Shantanu, PR [19158](https://github.com/python/mypy/pull/19158))
* Fix nondeterministic type checking caused by nonassociativity of joins (Shantanu, PR [19147](https://github.com/python/mypy/pull/19147))
* Fix nondeterministic type checking by making join between `type` and TypeVar commute (Shantanu, PR [19149](https://github.com/python/mypy/pull/19149))

### Remove Support for Targeting Python 3.8

Mypy now requires `--python-version 3.9` or greater. Support for targeting Python 3.8 is
fully removed now. Since 3.8 is an unsupported version, mypy will default to the oldest
supported version (currently 3.9) if you still try to target 3.8.

This change is necessary because typeshed stopped supporting Python 3.8 after it
reached its End of Life in October 2024.

Contributed by Marc Mueller
(PR [19157](https://github.com/python/mypy/pull/19157), PR [19162](https://github.com/python/mypy/pull/19162)).

### Initial Support for Python 3.14

Mypy is now tested on 3.14 and mypyc works with 3.14.0b3 and later.
Binary wheels compiled with mypyc for mypy itself will be available for 3.14
some time after 3.14.0rc1 has been released.

Note that not all features are supported just yet.

Contributed by Marc Mueller (PR [19164](https://github.com/python/mypy/pull/19164))

### Deprecated Flag: `--force-uppercase-builtins`

Mypy only supports Python 3.9+. The `--force-uppercase-builtins` flag is now
deprecated as unnecessary, and a no-op. It will be removed in a future version.

Contributed by Marc Mueller (PR [19176](https://github.com/python/mypy/pull/19176))

### Mypyc: Improvements to Generators and Async Functions

This release includes both performance improvements and bug fixes related
to generators and async functions (these share many implementation details).

* Fix exception swallowing in async try/finally blocks with await (Chainfire, PR [19353](https://github.com/python/mypy/pull/19353))
* Fix AttributeError in async try/finally with mixed return paths (Chainfire, PR [19361](https://github.com/python/mypy/pull/19361))
* Make generated generator helper method internal (Jukka Lehtosalo, PR [19268](https://github.com/python/mypy/pull/19268))
* Free coroutine after await encounters StopIteration (Jukka Lehtosalo, PR [19231](https://github.com/python/mypy/pull/19231))
* Use non-tagged integer for generator label (Jukka Lehtosalo, PR [19218](https://github.com/python/mypy/pull/19218))
* Merge generator and environment classes in simple cases (Jukka Lehtosalo, PR [19207](https://github.com/python/mypy/pull/19207))

### Mypyc: Partial, Unsafe Support for Free Threading

Mypyc has minimal, quite memory-unsafe support for the free threaded
builds of 3.14. It is also only lightly tested. Bug reports and experience
reports are welcome!

Here are some of the major limitations:
* Free threading only works when compiling a single module at a time.
* If there is concurrent access to an object while another thread is mutating the same
  object, it's possible to encounter segfaults and memory corruption.
* There are no efficient native primitives for thread synthronization, though the
  regular `threading` module can be used.
* Some workloads don't scale well to multiple threads for no clear reason.

Related PRs:

* Enable partial, unsafe support for free-threading (Jukka Lehtosalo, PR [19167](https://github.com/python/mypy/pull/19167))
* Fix incref/decref on free-threaded builds (Jukka Lehtosalo, PR [19127](https://github.com/python/mypy/pull/19127))

### Other Mypyc Fixes and Improvements

* Derive .c file name from full module name if using multi_file (Jukka Lehtosalo, PR [19278](https://github.com/python/mypy/pull/19278))
* Support overriding the group name used in output files (Jukka Lehtosalo, PR [19272](https://github.com/python/mypy/pull/19272))
* Add note about using non-native class to subclass built-in types (Jukka Lehtosalo, PR [19236](https://github.com/python/mypy/pull/19236))
* Make some generated classes implicitly final (Jukka Lehtosalo, PR [19235](https://github.com/python/mypy/pull/19235))
* Don't simplify module prefixes if using separate compilation (Jukka Lehtosalo, PR [19206](https://github.com/python/mypy/pull/19206))

### Stubgen Improvements

* Add import for `types` in `__exit__` method signature (Alexey Makridenko, PR [19120](https://github.com/python/mypy/pull/19120))
* Add support for including class and property docstrings (Chad Dombrova, PR [17964](https://github.com/python/mypy/pull/17964))
* Don't generate `Incomplete | None = None` argument annotation (Sebastian Rittau, PR [19097](https://github.com/python/mypy/pull/19097))
* Support several more constructs in stubgen's alias printer (Stanislav Terliakov, PR [18888](https://github.com/python/mypy/pull/18888))

### Miscellaneous Fixes and Improvements

* Combine the revealed types of multiple iteration steps in a more robust manner (Christoph Tyralla, PR [19324](https://github.com/python/mypy/pull/19324))
* Improve the handling of "iteration dependent" errors and notes in finally clauses (Christoph Tyralla, PR [19270](https://github.com/python/mypy/pull/19270))
* Lessen dmypy suggest path limitations for Windows machines (CoolCat467, PR [19337](https://github.com/python/mypy/pull/19337))
* Fix type ignore comments erroneously marked as unused by dmypy (Charlie Denton, PR [15043](https://github.com/python/mypy/pull/15043))
* Fix misspelled `exhaustive-match` error code (johnthagen, PR [19276](https://github.com/python/mypy/pull/19276))
* Fix missing error context for unpacking assignment involving star expression (Brian Schubert, PR [19258](https://github.com/python/mypy/pull/19258))
* Fix and simplify error de-duplication (Ivan Levkivskyi, PR [19247](https://github.com/python/mypy/pull/19247))
* Disallow `ClassVar` in type aliases (Brian Schubert, PR [19263](https://github.com/python/mypy/pull/19263))
* Add script that prints list of compiled files when compiling mypy (Jukka Lehtosalo, PR [19260](https://github.com/python/mypy/pull/19260))
* Fix help message url for "None and Optional handling" section (Guy Wilson, PR [19252](https://github.com/python/mypy/pull/19252))
* Display fully qualified name of imported base classes in errors about incompatible overrides (Mikhail Golubev, PR [19115](https://github.com/python/mypy/pull/19115))
* Avoid false `unreachable`, `redundant-expr`, and `redundant-casts` warnings in loops more robustly and efficiently, and avoid multiple `revealed type` notes for the same line (Christoph Tyralla, PR [19118](https://github.com/python/mypy/pull/19118))
* Fix type extraction from `isinstance` checks (Stanislav Terliakov, PR [19223](https://github.com/python/mypy/pull/19223))
* Erase stray type variables in `functools.partial` (Stanislav Terliakov, PR [18954](https://github.com/python/mypy/pull/18954))
* Make inferring condition value recognize the whole truth table (Stanislav Terliakov, PR [18944](https://github.com/python/mypy/pull/18944))
* Support type aliases, `NamedTuple` and `TypedDict` in constrained TypeVar defaults (Stanislav Terliakov, PR [18884](https://github.com/python/mypy/pull/18884))
* Move dataclass `kw_only` fields to the end of the signature (Stanislav Terliakov, PR [19018](https://github.com/python/mypy/pull/19018))
* Provide a better fallback value for the `python_version` option (Marc Mueller, PR [19162](https://github.com/python/mypy/pull/19162))
* Avoid spurious non-overlapping equality error with metaclass with `__eq__` (Michael J. Sullivan, PR [19220](https://github.com/python/mypy/pull/19220))
* Narrow type variable bounds (Ivan Levkivskyi, PR [19183](https://github.com/python/mypy/pull/19183))
* Add classifier for Python 3.14 (Marc Mueller, PR [19199](https://github.com/python/mypy/pull/19199))
* Capitalize syntax error messages (Charulata, PR [19114](https://github.com/python/mypy/pull/19114))
* Infer constraints eagerly if actual is Any (Ivan Levkivskyi, PR [19190](https://github.com/python/mypy/pull/19190))
* Include walrus assignments in conditional inference (Stanislav Terliakov, PR [19038](https://github.com/python/mypy/pull/19038))
* Use PEP 604 syntax when converting types to strings (Marc Mueller, PR [19179](https://github.com/python/mypy/pull/19179))
* Use more lower-case builtin types in error messages (Marc Mueller, PR [19177](https://github.com/python/mypy/pull/19177))
* Fix example to use correct method of Stack (Łukasz Kwieciński, PR [19123](https://github.com/python/mypy/pull/19123))
* Forbid `.pop` of `Readonly` `NotRequired` TypedDict items (Stanislav Terliakov, PR [19133](https://github.com/python/mypy/pull/19133))
* Emit a friendlier warning on invalid exclude regex, instead of a stacktrace (wyattscarpenter, PR [19102](https://github.com/python/mypy/pull/19102))
* Enable ANSI color codes for dmypy client in Windows (wyattscarpenter, PR [19088](https://github.com/python/mypy/pull/19088))
* Extend special case for context-based type variable inference to unions in return position (Stanislav Terliakov, PR [18976](https://github.com/python/mypy/pull/18976))

### Mypy 1.17.1
* Retain `None` as constraints bottom if no bottoms were provided (Stanislav Terliakov, PR [19485](https://github.com/python/mypy/pull/19485))
* Fix "ignored exception in `hasattr`" in dmypy (Stanislav Terliakov, PR [19428](https://github.com/python/mypy/pull/19428))
* Prevent a crash when InitVar is redefined with a method in a subclass (Stanislav Terliakov, PR [19453](https://github.com/python/mypy/pull/19453))

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

* Alexey Makridenko
* Brian Schubert
* Chad Dombrova
* Chainfire
* Charlie Denton
* Charulata
* Christoph Tyralla
* CoolCat467
* Donal Burns
* Guy Wilson
* Ivan Levkivskyi
* johnthagen
* Jukka Lehtosalo
* Łukasz Kwieciński
* Marc Mueller
* Michael J. Sullivan
* Mikhail Golubev
* Sebastian Rittau
* Shantanu
* Stanislav Terliakov
* wyattscarpenter

I’d also like to thank my employer, Dropbox, for supporting mypy development.

## Mypy 1.16

We’ve just uploaded mypy 1.16 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)).
Mypy is a static type checker for Python. This release includes new features and bug fixes.
You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Different Property Getter and Setter Types

Mypy now supports using different types for a property getter and setter:

```python
class A:
    _value: int

    @property
    def foo(self) -> int:
        return self._value

    @foo.setter
    def foo(self, x: str | int) -> None:
        try:
            self._value = int(x)
        except ValueError:
            raise Exception(f"'{x}' is not a valid value for 'foo'")
```
This was contributed by Ivan Levkivskyi (PR [18510](https://github.com/python/mypy/pull/18510)).

### Flexible Variable Redefinitions (Experimental)

Mypy now allows unannotated variables to be freely redefined with
different types when using the experimental `--allow-redefinition-new`
flag. You will also need to enable `--local-partial-types`. Mypy will
now infer a union type when different types are assigned to a
variable:

```py
# mypy: allow-redefinition-new, local-partial-types

def f(n: int, b: bool) -> int | str:
    if b:
        x = n
    else:
        x = str(n)
    # Type of 'x' is int | str here.
    return x
```

Without the new flag, mypy only supports inferring optional types (`X
| None`) from multiple assignments, but now mypy can infer arbitrary
union types.

An unannotated variable can now also have different types in different
code locations:

```py
# mypy: allow-redefinition-new, local-partial-types
...

if cond():
    for x in range(n):
        # Type of 'x' is 'int' here
        ...
else:
    for x in ['a', 'b']:
        # Type of 'x' is 'str' here
        ...
```

We are planning to turn this flag on by default in mypy 2.0, along
with `--local-partial-types`. The feature is still experimental and
has known issues, and the semantics may still change in the
future. You may need to update or add type annotations when switching
to the new behavior, but if you encounter anything unexpected, please
create a GitHub issue.

This was contributed by Jukka Lehtosalo
(PR [18727](https://github.com/python/mypy/pull/18727), PR [19153](https://github.com/python/mypy/pull/19153)).

### Stricter Type Checking with Imprecise Types

Mypy can now detect additional errors in code that uses `Any` types or has missing function annotations.

When calling `dict.get(x, None)` on an object of type `dict[str, Any]`, this
now results in an optional type (in the past it was `Any`):

```python
def f(d: dict[str, Any]) -> int:
    # Error: Return value has type "Any | None" but expected "int"
    return d.get("x", None)
```

Type narrowing using assignments can result in more precise types in
the presence of `Any` types:

```python
def foo(): ...

def bar(n: int) -> None:
    x = foo()
    # Type of 'x' is 'Any' here
    if n > 5:
        x = str(n)
        # Type of 'x' is 'str' here
```

When using `--check-untyped-defs`, unannotated overrides are now
checked more strictly against superclass definitions.

Related PRs:

 * Use union types instead of join in binder (Ivan Levkivskyi, PR [18538](https://github.com/python/mypy/pull/18538))
 * Check superclass compatibility of untyped methods if `--check-untyped-defs` is set (Stanislav Terliakov, PR [18970](https://github.com/python/mypy/pull/18970))

### Improvements to Attribute Resolution

This release includes several fixes to inconsistent resolution of attribute, method and descriptor types.

 * Consolidate descriptor handling (Ivan Levkivskyi, PR [18831](https://github.com/python/mypy/pull/18831))
 * Make multiple inheritance checking use common semantics (Ivan Levkivskyi, PR [18876](https://github.com/python/mypy/pull/18876))
 * Make method override checking use common semantics  (Ivan Levkivskyi, PR [18870](https://github.com/python/mypy/pull/18870))
 * Fix descriptor overload selection (Ivan Levkivskyi, PR [18868](https://github.com/python/mypy/pull/18868))
 * Handle union types when binding `self` (Ivan Levkivskyi, PR [18867](https://github.com/python/mypy/pull/18867))
 * Make variable override checking use common semantics (Ivan Levkivskyi, PR [18847](https://github.com/python/mypy/pull/18847))
 * Make descriptor handling behave consistently (Ivan Levkivskyi, PR [18831](https://github.com/python/mypy/pull/18831))

### Make Implementation for Abstract Overloads Optional

The implementation can now be omitted for abstract overloaded methods,
even outside stubs:

```py
from abc import abstractmethod
from typing import overload

class C:
    @abstractmethod
    @overload
    def foo(self, x: int) -> int: ...

    @abstractmethod
    @overload
    def foo(self, x: str) -> str: ...

    # No implementation required for "foo"
```

This was contributed by Ivan Levkivskyi (PR [18882](https://github.com/python/mypy/pull/18882)).

### Option to Exclude Everything in .gitignore

You can now use `--exclude-gitignore` to exclude everything in a
`.gitignore` file from the mypy build. This behaves similar to
excluding the paths using `--exclude`. We might enable this by default
in a future mypy release.

This was contributed by Ivan Levkivskyi (PR [18696](https://github.com/python/mypy/pull/18696)).

### Selectively Disable Deprecated Warnings

It's now possible to selectively disable warnings generated from
[`warnings.deprecated`](https://docs.python.org/3/library/warnings.html#warnings.deprecated)
using the [`--deprecated-calls-exclude`](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-deprecated-calls-exclude)
option:

```python
# mypy --enable-error-code deprecated
#      --deprecated-calls-exclude=foo.A
import foo

foo.A().func()  # OK, the deprecated warning is ignored
```

```python
# file foo.py

from typing_extensions import deprecated

class A:
    @deprecated("Use A.func2 instead")
    def func(self): pass

    ...
```

Contributed by Marc Mueller (PR [18641](https://github.com/python/mypy/pull/18641))

### Annotating Native/Non-Native Classes in Mypyc

You can now declare a class as a non-native class when compiling with
mypyc. Unlike native classes, which are extension classes and have an
immutable structure, non-native classes are normal Python classes at
runtime and are fully dynamic.  Example:

```python
from mypy_extensions import mypyc_attr

@mypyc_attr(native_class=False)
class NonNativeClass:
    ...

o = NonNativeClass()

# Ok, even if attribute "foo" not declared in class body
setattr(o, "foo", 1)
```

Classes are native by default in compiled modules, but classes that
use certain features (such as most metaclasses) are implicitly
non-native.

You can also explicitly declare a class as native. In this case mypyc
will generate an error if it can't compile the class as a native
class, instead of falling back to a non-native class:

```python
from mypy_extensions import mypyc_attr
from foo import MyMeta

# Error: Unsupported metaclass for a native class
@mypyc_attr(native_class=True)
class C(metaclass=MyMeta):
    ...
```

Since native classes are significantly more efficient that non-native
classes, you may want to ensure that certain classes always compiled
as native classes.

This feature was contributed by Valentin Stanciu (PR [18802](https://github.com/python/mypy/pull/18802)).

### Mypyc Fixes and Improvements

 * Improve documentation of native and non-native classes (Jukka Lehtosalo, PR [19154](https://github.com/python/mypy/pull/19154))
 * Fix compilation when using Python 3.13 debug build (Valentin Stanciu, PR [19045](https://github.com/python/mypy/pull/19045))
 * Show the reason why a class can't be a native class (Valentin Stanciu, PR [19016](https://github.com/python/mypy/pull/19016))
 * Support await/yield while temporary values are live (Michael J. Sullivan, PR [16305](https://github.com/python/mypy/pull/16305))
 * Fix spilling values with overlapping error values (Jukka Lehtosalo, PR [18961](https://github.com/python/mypy/pull/18961))
 * Fix reference count of spilled register in async def (Jukka Lehtosalo, PR [18957](https://github.com/python/mypy/pull/18957))
 * Add basic optimization for `sorted` (Marc Mueller, PR [18902](https://github.com/python/mypy/pull/18902))
 * Fix access of class object in a type annotation (Advait Dixit, PR [18874](https://github.com/python/mypy/pull/18874))
 * Optimize `list.__imul__` and `tuple.__mul__ `(Marc Mueller, PR [18887](https://github.com/python/mypy/pull/18887))
 * Optimize `list.__add__`, `list.__iadd__` and `tuple.__add__` (Marc Mueller, PR [18845](https://github.com/python/mypy/pull/18845))
 * Add and implement primitive `list.copy()` (exertustfm, PR [18771](https://github.com/python/mypy/pull/18771))
 * Optimize `builtins.repr` (Marc Mueller, PR [18844](https://github.com/python/mypy/pull/18844))
 * Support iterating over keys/values/items of dict-bound TypeVar and ParamSpec.kwargs (Stanislav Terliakov, PR [18789](https://github.com/python/mypy/pull/18789))
 * Add efficient primitives for `str.strip()` etc. (Advait Dixit, PR [18742](https://github.com/python/mypy/pull/18742))
 * Document that `strip()` etc. are optimized (Jukka Lehtosalo, PR [18793](https://github.com/python/mypy/pull/18793))
 * Fix mypyc crash with enum type aliases (Valentin Stanciu, PR [18725](https://github.com/python/mypy/pull/18725))
 * Optimize `str.find` and `str.rfind` (Marc Mueller, PR [18709](https://github.com/python/mypy/pull/18709))
 * Optimize `str.__contains__` (Marc Mueller, PR [18705](https://github.com/python/mypy/pull/18705))
 * Fix order of steal/unborrow in tuple unpacking (Ivan Levkivskyi, PR [18732](https://github.com/python/mypy/pull/18732))
 * Optimize `str.partition` and `str.rpartition` (Marc Mueller, PR [18702](https://github.com/python/mypy/pull/18702))
 * Optimize `str.startswith` and `str.endswith` with tuple argument (Marc Mueller, PR [18678](https://github.com/python/mypy/pull/18678))
 * Improve `str.startswith` and `str.endswith` with tuple argument (Marc Mueller, PR [18703](https://github.com/python/mypy/pull/18703))
 * `pythoncapi_compat`: don't define Py_NULL if it is already defined (Michael R. Crusoe, PR [18699](https://github.com/python/mypy/pull/18699))
 * Optimize `str.splitlines` (Marc Mueller, PR [18677](https://github.com/python/mypy/pull/18677))
 * Mark `dict.setdefault` as optimized (Marc Mueller, PR [18685](https://github.com/python/mypy/pull/18685))
 * Support `__del__` methods (Advait Dixit, PR [18519](https://github.com/python/mypy/pull/18519))
 * Optimize `str.rsplit` (Marc Mueller, PR [18673](https://github.com/python/mypy/pull/18673))
 * Optimize `str.removeprefix` and `str.removesuffix` (Marc Mueller, PR [18672](https://github.com/python/mypy/pull/18672))
 * Recognize literal types in `__match_args__` (Stanislav Terliakov, PR [18636](https://github.com/python/mypy/pull/18636))
 * Fix non extension classes with attribute annotations using forward references (Valentin Stanciu, PR [18577](https://github.com/python/mypy/pull/18577))
 * Use lower-case generic types such as `list[t]` in documentation (Jukka Lehtosalo, PR [18576](https://github.com/python/mypy/pull/18576))
 * Improve support for `frozenset` (Marc Mueller, PR [18571](https://github.com/python/mypy/pull/18571))
 * Fix wheel build for cp313-win (Marc Mueller, PR [18560](https://github.com/python/mypy/pull/18560))
 * Reduce impact of immortality (introduced in Python 3.12) on reference counting performance (Jukka Lehtosalo, PR [18459](https://github.com/python/mypy/pull/18459))
 * Update math error messages for 3.14 (Marc Mueller, PR [18534](https://github.com/python/mypy/pull/18534))
 * Update math error messages for 3.14 (2) (Marc Mueller, PR [18949](https://github.com/python/mypy/pull/18949))
 * Replace deprecated `_PyLong_new` with `PyLongWriter` API (Marc Mueller, PR [18532](https://github.com/python/mypy/pull/18532))

### Fixes to Crashes

 * Traverse module ancestors when traversing reachable graph nodes during dmypy update (Stanislav Terliakov, PR [18906](https://github.com/python/mypy/pull/18906))
 * Fix crash on multiple unpacks in a bare type application (Stanislav Terliakov, PR [18857](https://github.com/python/mypy/pull/18857))
 * Prevent crash when enum/TypedDict call is stored as a class attribute (Stanislav Terliakov, PR [18861](https://github.com/python/mypy/pull/18861))
 * Fix crash on multiple unpacks in a bare type application (Stanislav Terliakov, PR [18857](https://github.com/python/mypy/pull/18857))
 * Fix crash on type inference against non-normal callables (Ivan Levkivskyi, PR [18858](https://github.com/python/mypy/pull/18858))
 * Fix crash on decorated getter in settable property (Ivan Levkivskyi, PR [18787](https://github.com/python/mypy/pull/18787))
 * Fix crash on callable with `*args` and suffix against Any (Ivan Levkivskyi, PR [18781](https://github.com/python/mypy/pull/18781))
 * Fix crash on deferred supertype and setter override (Ivan Levkivskyi, PR [18649](https://github.com/python/mypy/pull/18649))
 * Fix crashes on incorrectly detected recursive aliases (Ivan Levkivskyi, PR [18625](https://github.com/python/mypy/pull/18625))
 * Report that `NamedTuple` and `dataclass` are incompatile instead of crashing (Christoph Tyralla, PR [18633](https://github.com/python/mypy/pull/18633))
 * Fix mypy daemon crash (Valentin Stanciu, PR [19087](https://github.com/python/mypy/pull/19087))

### Performance Improvements

These are specific to mypy. Mypyc-related performance improvements are discussed elsewhere.

 * Speed up binding `self` in trivial cases (Ivan Levkivskyi, PR [19024](https://github.com/python/mypy/pull/19024))
 * Small constraint solver optimization (Aaron Gokaslan, PR [18688](https://github.com/python/mypy/pull/18688))

### Documentation Updates

 * Improve documentation of `--strict` (lenayoung8, PR [18903](https://github.com/python/mypy/pull/18903))
 * Remove a note about `from __future__ import annotations` (Ageev Maxim, PR [18915](https://github.com/python/mypy/pull/18915))
 * Improve documentation on type narrowing (Tim Hoffmann, PR [18767](https://github.com/python/mypy/pull/18767))
 * Fix metaclass usage example (Georg, PR [18686](https://github.com/python/mypy/pull/18686))
 * Update documentation on `extra_checks` flag (Ivan Levkivskyi, PR [18537](https://github.com/python/mypy/pull/18537))

### Stubgen Improvements

 * Fix `TypeAlias` handling (Alexey Makridenko, PR [18960](https://github.com/python/mypy/pull/18960))
 * Handle `arg=None` in C extension modules (Anthony Sottile, PR [18768](https://github.com/python/mypy/pull/18768))
 * Fix valid type detection to allow pipe unions (Chad Dombrova, PR [18726](https://github.com/python/mypy/pull/18726))
 * Include simple decorators in stub files (Marc Mueller, PR [18489](https://github.com/python/mypy/pull/18489))
 * Support positional and keyword-only arguments in stubdoc (Paul Ganssle, PR [18762](https://github.com/python/mypy/pull/18762))
 * Fall back to `Incomplete` if we are unable to determine the module name (Stanislav Terliakov, PR [19084](https://github.com/python/mypy/pull/19084))

### Stubtest Improvements

 * Make stubtest ignore `__slotnames__` (Nick Pope, PR [19077](https://github.com/python/mypy/pull/19077))
 * Fix stubtest tests on 3.14 (Jelle Zijlstra, PR [19074](https://github.com/python/mypy/pull/19074))
 * Support for `strict_bytes` in stubtest (Joren Hammudoglu, PR [19002](https://github.com/python/mypy/pull/19002))
 * Understand override (Shantanu, PR [18815](https://github.com/python/mypy/pull/18815))
 * Better checking of runtime arguments with dunder names (Shantanu, PR [18756](https://github.com/python/mypy/pull/18756))
 * Ignore setattr and delattr inherited from object (Stephen Morton, PR [18325](https://github.com/python/mypy/pull/18325))

### Miscellaneous Fixes and Improvements

 * Add `--strict-bytes` to `--strict` (wyattscarpenter, PR [19049](https://github.com/python/mypy/pull/19049))
 * Admit that Final variables are never redefined (Stanislav Terliakov, PR [19083](https://github.com/python/mypy/pull/19083))
 * Add special support for `@django.cached_property` needed in `django-stubs` (sobolevn, PR [18959](https://github.com/python/mypy/pull/18959))
 * Do not narrow types to `Never` with binder (Ivan Levkivskyi, PR [18972](https://github.com/python/mypy/pull/18972))
 * Local forward references should precede global forward references (Ivan Levkivskyi, PR [19000](https://github.com/python/mypy/pull/19000))
 * Do not cache module lookup results in incremental mode that may become invalid (Stanislav Terliakov, PR [19044](https://github.com/python/mypy/pull/19044))
 * Only consider meta variables in ambiguous "any of" constraints (Stanislav Terliakov, PR [18986](https://github.com/python/mypy/pull/18986))
 * Allow accessing `__init__` on final classes and when `__init__` is final (Stanislav Terliakov, PR [19035](https://github.com/python/mypy/pull/19035))
 * Treat varargs as positional-only (A5rocks, PR [19022](https://github.com/python/mypy/pull/19022))
 * Enable colored output for argparse help in Python 3.14 (Marc Mueller, PR [19021](https://github.com/python/mypy/pull/19021))
 * Fix argparse for Python 3.14 (Marc Mueller, PR [19020](https://github.com/python/mypy/pull/19020))
 * `dmypy suggest` can now suggest through contextmanager-based decorators (Anthony Sottile, PR [18948](https://github.com/python/mypy/pull/18948))
 * Fix `__r<magic_methods>__` being used under the same `__<magic_method>__` hook (Arnav Jain, PR [18995](https://github.com/python/mypy/pull/18995))
 * Prioritize `.pyi` from `-stubs` packages over bundled `.pyi` (Joren Hammudoglu, PR [19001](https://github.com/python/mypy/pull/19001))
 * Fix missing subtype check case for `type[T]` (Stanislav Terliakov, PR [18975](https://github.com/python/mypy/pull/18975))
 * Fixes to the detection of redundant casts (Anthony Sottile, PR [18588](https://github.com/python/mypy/pull/18588))
 * Make some parse errors non-blocking (Shantanu, PR [18941](https://github.com/python/mypy/pull/18941))
 * Fix PEP 695 type alias with a mix of type arguments (PEP 696) (Marc Mueller, PR [18919](https://github.com/python/mypy/pull/18919))
 * Allow deeper recursion in mypy daemon, better error reporting (Carter Dodd, PR [17707](https://github.com/python/mypy/pull/17707))
 * Fix swapped errors for frozen/non-frozen dataclass inheritance (Nazrawi Demeke, PR [18918](https://github.com/python/mypy/pull/18918))
 * Fix incremental issue with namespace packages (Shantanu, PR [18907](https://github.com/python/mypy/pull/18907))
 * Exclude irrelevant members when narrowing union overlapping with enum (Stanislav Terliakov, PR [18897](https://github.com/python/mypy/pull/18897))
 * Flatten union before contracting literals when checking subtyping (Stanislav Terliakov, PR [18898](https://github.com/python/mypy/pull/18898))
 * Do not add `kw_only` dataclass fields to `__match_args__` (sobolevn, PR [18892](https://github.com/python/mypy/pull/18892))
 * Fix error message when returning long tuple with type mismatch (Thomas Mattone, PR [18881](https://github.com/python/mypy/pull/18881))
 * Treat `TypedDict` (old-style) aliases as regular `TypedDict`s (Stanislav Terliakov, PR [18852](https://github.com/python/mypy/pull/18852))
 * Warn about unused `type: ignore` comments when error code is disabled (Brian Schubert, PR [18849](https://github.com/python/mypy/pull/18849))
 * Reject duplicate `ParamSpec.{args,kwargs}` at call site (Stanislav Terliakov, PR [18854](https://github.com/python/mypy/pull/18854))
 * Make detection of enum members more consistent (sobolevn, PR [18675](https://github.com/python/mypy/pull/18675))
 * Admit that `**kwargs` mapping subtypes may have no direct type parameters (Stanislav Terliakov, PR [18850](https://github.com/python/mypy/pull/18850))
 * Don't suggest `types-setuptools` for `pkg_resources` (Shantanu, PR [18840](https://github.com/python/mypy/pull/18840))
 * Suggest `scipy-stubs` for `scipy` as non-typeshed stub package (Joren Hammudoglu, PR [18832](https://github.com/python/mypy/pull/18832))
 * Narrow tagged unions in match statements (Gene Parmesan Thomas, PR [18791](https://github.com/python/mypy/pull/18791))
 * Consistently store settable property type (Ivan Levkivskyi, PR [18774](https://github.com/python/mypy/pull/18774))
 * Do not blindly undefer on leaving function (Ivan Levkivskyi, PR [18674](https://github.com/python/mypy/pull/18674))
 * Process superclass methods before subclass methods in semanal (Ivan Levkivskyi, PR [18723](https://github.com/python/mypy/pull/18723))
 * Only defer top-level functions (Ivan Levkivskyi, PR [18718](https://github.com/python/mypy/pull/18718))
 * Add one more type-checking pass (Ivan Levkivskyi, PR [18717](https://github.com/python/mypy/pull/18717))
 * Properly account for `member` and `nonmember` in enums (sobolevn, PR [18559](https://github.com/python/mypy/pull/18559))
 * Fix instance vs tuple subtyping edge case (Ivan Levkivskyi, PR [18664](https://github.com/python/mypy/pull/18664))
 * Improve handling of Any/object in variadic generics (Ivan Levkivskyi, PR [18643](https://github.com/python/mypy/pull/18643))
 * Fix handling of named tuples in class match pattern (Ivan Levkivskyi, PR [18663](https://github.com/python/mypy/pull/18663))
 * Fix regression for user config files (Shantanu, PR [18656](https://github.com/python/mypy/pull/18656))
 * Fix dmypy socket issue on GNU/Hurd (Mattias Ellert, PR [18630](https://github.com/python/mypy/pull/18630))
 * Don't assume that for loop body index variable is always set (Jukka Lehtosalo, PR [18631](https://github.com/python/mypy/pull/18631))
 * Fix overlap check for variadic generics (Ivan Levkivskyi, PR [18638](https://github.com/python/mypy/pull/18638))
 * Improve support for `functools.partial` of overloaded callable protocol (Shantanu, PR [18639](https://github.com/python/mypy/pull/18639))
 * Allow lambdas in `except*` clauses (Stanislav Terliakov, PR [18620](https://github.com/python/mypy/pull/18620))
 * Fix trailing commas in many multiline string options in `pyproject.toml` (sobolevn, PR [18624](https://github.com/python/mypy/pull/18624))
 * Allow trailing commas for `files` setting in `mypy.ini` and `setup.ini` (sobolevn, PR [18621](https://github.com/python/mypy/pull/18621))
 * Fix "not callable" issue for `@dataclass(frozen=True)` with `Final` attr (sobolevn, PR [18572](https://github.com/python/mypy/pull/18572))
 * Add missing TypedDict special case when checking member access (Stanislav Terliakov, PR [18604](https://github.com/python/mypy/pull/18604))
 * Use lower case `list` and `dict` in invariance notes (Jukka Lehtosalo, PR [18594](https://github.com/python/mypy/pull/18594))
 * Fix inference when class and instance match protocol (Ivan Levkivskyi, PR [18587](https://github.com/python/mypy/pull/18587))
 * Remove support for `builtins.Any` (Marc Mueller, PR [18578](https://github.com/python/mypy/pull/18578))
 * Update the overlapping check for tuples to account for NamedTuples (A5rocks, PR [18564](https://github.com/python/mypy/pull/18564))
 * Fix `@deprecated` (PEP 702) with normal overloaded methods (Christoph Tyralla, PR [18477](https://github.com/python/mypy/pull/18477))
 * Start propagating end columns/lines for `type-arg` errors (A5rocks, PR [18533](https://github.com/python/mypy/pull/18533))
 * Improve handling of `type(x) is Foo` checks (Stanislav Terliakov, PR [18486](https://github.com/python/mypy/pull/18486))
 * Suggest `typing.Literal` for exit-return error messages (Marc Mueller, PR [18541](https://github.com/python/mypy/pull/18541))
 * Allow redefinitions in except/else/finally (Stanislav Terliakov, PR [18515](https://github.com/python/mypy/pull/18515))
 * Disallow setting Python version using inline config (Shantanu, PR [18497](https://github.com/python/mypy/pull/18497))
 * Improve type inference in tuple multiplication plugin (Shantanu, PR [18521](https://github.com/python/mypy/pull/18521))
 * Add missing line number to `yield from` with wrong type (Stanislav Terliakov, PR [18518](https://github.com/python/mypy/pull/18518))
 * Hint at argument names when formatting callables with compatible return types in error messages (Stanislav Terliakov, PR [18495](https://github.com/python/mypy/pull/18495))
 * Add better naming and improve compatibility for ad hoc intersections of instances (Christoph Tyralla, PR [18506](https://github.com/python/mypy/pull/18506))

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

- A5rocks
- Aaron Gokaslan
- Advait Dixit
- Ageev Maxim
- Alexey Makridenko
- Ali Hamdan
- Anthony Sottile
- Arnav Jain
- Brian Schubert
- bzoracler
- Carter Dodd
- Chad Dombrova
- Christoph Tyralla
- Dimitri Papadopoulos Orfanos
- Emma Smith
- exertustfm
- Gene Parmesan Thomas
- Georg
- Ivan Levkivskyi
- Jared Hance
- Jelle Zijlstra
- Joren Hammudoglu
- lenayoung8
- Marc Mueller
- Mattias Ellert
- Michael J. Sullivan
- Michael R. Crusoe
- Nazrawi Demeke
- Nick Pope
- Paul Ganssle
- Shantanu
- sobolevn
- Stanislav Terliakov
- Stephen Morton
- Thomas Mattone
- Tim Hoffmann
- Tim Ruffing
- Valentin Stanciu
- Wesley Collin Wright
- wyattscarpenter

I’d also like to thank my employer, Dropbox, for supporting mypy development.

## Mypy 1.15

We’ve just uploaded mypy 1.15 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)).
Mypy is a static type checker for Python. This release includes new features, performance
improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Performance Improvements

Mypy is up to 40% faster in some use cases. This improvement comes largely from tuning the performance
of the garbage collector. Additionally, the release includes several micro-optimizations that may
be impactful for large projects.

Contributed by Jukka Lehtosalo
- PR [18306](https://github.com/python/mypy/pull/18306)
- PR [18302](https://github.com/python/mypy/pull/18302)
- PR [18298](https://github.com/python/mypy/pull/18298)
- PR [18299](https://github.com/python/mypy/pull/18299)

### Mypyc Accelerated Mypy Wheels for ARM Linux

For best performance, mypy can be compiled to C extension modules using mypyc. This makes
mypy 3-5x faster than when interpreted with pure Python. We now build and upload mypyc
accelerated mypy wheels for `manylinux_aarch64` to PyPI, making it easy for Linux users on
ARM platforms to realise this speedup -- just `pip install` the latest mypy.

Contributed by Christian Bundy and Marc Mueller
(PR [mypy_mypyc-wheels#76](https://github.com/mypyc/mypy_mypyc-wheels/pull/76),
PR [mypy_mypyc-wheels#89](https://github.com/mypyc/mypy_mypyc-wheels/pull/89)).

### `--strict-bytes`

By default, mypy treats `bytearray` and `memoryview` values as assignable to the `bytes`
type, for historical reasons. Use the `--strict-bytes` flag to disable this
behavior. [PEP 688](https://peps.python.org/pep-0688) specified the removal of this
special case. The flag will be enabled by default in **mypy 2.0**.

Contributed by Ali Hamdan (PR [18263](https://github.com/python/mypy/pull/18263)) and
Shantanu Jain (PR [13952](https://github.com/python/mypy/pull/13952)).

### Improvements to Reachability Analysis and Partial Type Handling in Loops

This change results in mypy better modelling control flow within loops and hence detecting
several previously ignored issues. In some cases, this change may require additional
explicit variable annotations.

Contributed by Christoph Tyralla (PR [18180](https://github.com/python/mypy/pull/18180),
PR [18433](https://github.com/python/mypy/pull/18433)).

(Speaking of partial types, remember that we plan to enable `--local-partial-types`
by default in **mypy 2.0**.)

### Better Discovery of Configuration Files

Mypy will now walk up the filesystem (up until a repository or file system root) to discover
configuration files. See the
[mypy configuration file documentation](https://mypy.readthedocs.io/en/stable/config_file.html)
for more details.

Contributed by Mikhail Shiryaev and Shantanu Jain
(PR [16965](https://github.com/python/mypy/pull/16965), PR [18482](https://github.com/python/mypy/pull/18482))

### Better Line Numbers for Decorators and Slice Expressions

Mypy now uses more correct line numbers for decorators and slice expressions. In some cases,
you may have to change the location of a `# type: ignore` comment.

Contributed by Shantanu Jain (PR [18392](https://github.com/python/mypy/pull/18392),
PR [18397](https://github.com/python/mypy/pull/18397)).

### Drop Support for Python 3.8

Mypy no longer supports running with Python 3.8, which has reached end-of-life.
When running mypy with Python 3.9+, it is still possible to type check code
that needs to support Python 3.8 with the `--python-version 3.8` argument.
Support for this will be dropped in the first half of 2025!

Contributed by Marc Mueller (PR [17492](https://github.com/python/mypy/pull/17492)).

### Mypyc Improvements

 * Fix `__init__` for classes with `@attr.s(slots=True)` (Advait Dixit, PR [18447](https://github.com/python/mypy/pull/18447))
 * Report error for nested class instead of crashing (Valentin Stanciu, PR [18460](https://github.com/python/mypy/pull/18460))
 * Fix `InitVar` for dataclasses (Advait Dixit, PR [18319](https://github.com/python/mypy/pull/18319))
 * Remove unnecessary mypyc files from wheels (Marc Mueller, PR [18416](https://github.com/python/mypy/pull/18416))
 * Fix issues with relative imports (Advait Dixit, PR [18286](https://github.com/python/mypy/pull/18286))
 * Add faster primitive for some list get item operations (Jukka Lehtosalo, PR [18136](https://github.com/python/mypy/pull/18136))
 * Fix iteration over `NamedTuple` objects (Advait Dixit, PR [18254](https://github.com/python/mypy/pull/18254))
 * Mark mypyc package with `py.typed` (bzoracler, PR [18253](https://github.com/python/mypy/pull/18253))
 * Fix list index while checking for `Enum` class (Advait Dixit, PR [18426](https://github.com/python/mypy/pull/18426))

### Stubgen Improvements

 * Improve dataclass init signatures (Marc Mueller, PR [18430](https://github.com/python/mypy/pull/18430))
 * Preserve `dataclass_transform` decorator (Marc Mueller, PR [18418](https://github.com/python/mypy/pull/18418))
 * Fix `UnpackType` for 3.11+ (Marc Mueller, PR [18421](https://github.com/python/mypy/pull/18421))
 * Improve `self` annotations (Marc Mueller, PR [18420](https://github.com/python/mypy/pull/18420))
 * Print `InspectError` traceback in stubgen `walk_packages` when verbose is specified (Gareth, PR [18224](https://github.com/python/mypy/pull/18224))

### Stubtest Improvements

 * Fix crash with numpy array default values (Ali Hamdan, PR [18353](https://github.com/python/mypy/pull/18353))
 * Distinguish metaclass attributes from class attributes (Stephen Morton, PR [18314](https://github.com/python/mypy/pull/18314))

### Fixes to Crashes

 * Prevent crash with `Unpack` of a fixed tuple in PEP695 type alias (Stanislav Terliakov, PR [18451](https://github.com/python/mypy/pull/18451))
 * Fix crash with `--cache-fine-grained --cache-dir=/dev/null` (Shantanu, PR [18457](https://github.com/python/mypy/pull/18457))
 * Prevent crashing when `match` arms use name of existing callable (Stanislav Terliakov, PR [18449](https://github.com/python/mypy/pull/18449))
 * Gracefully handle encoding errors when writing to stdout (Brian Schubert, PR [18292](https://github.com/python/mypy/pull/18292))
 * Prevent crash on generic NamedTuple with unresolved typevar bound (Stanislav Terliakov, PR [18585](https://github.com/python/mypy/pull/18585))

### Documentation Updates

 * Add inline tabs to documentation (Marc Mueller, PR [18262](https://github.com/python/mypy/pull/18262))
 * Document any `TYPE_CHECKING` name works (Shantanu, PR [18443](https://github.com/python/mypy/pull/18443))
 * Update documentation to not mention 3.8 where possible (sobolevn, PR [18455](https://github.com/python/mypy/pull/18455))
 * Mention `ignore_errors` in exclude documentation (Shantanu, PR [18412](https://github.com/python/mypy/pull/18412))
 * Add `Self` misuse to common issues (Shantanu, PR [18261](https://github.com/python/mypy/pull/18261))

### Other Notable Fixes and Improvements

 * Fix literal context for ternary expressions (Ivan Levkivskyi, PR [18545](https://github.com/python/mypy/pull/18545))
 * Ignore `dataclass.__replace__` LSP violations (Marc Mueller, PR [18464](https://github.com/python/mypy/pull/18464))
 * Bind `self` to the class being defined when checking multiple inheritance (Stanislav Terliakov, PR [18465](https://github.com/python/mypy/pull/18465))
 * Fix attribute type resolution with multiple inheritance (Stanislav Terliakov, PR [18415](https://github.com/python/mypy/pull/18415))
 * Improve security of our GitHub Actions (sobolevn, PR [18413](https://github.com/python/mypy/pull/18413))
 * Unwrap `type[Union[...]]` when solving type variable constraints (Stanislav Terliakov, PR [18266](https://github.com/python/mypy/pull/18266))
 * Allow `Any` to match sequence patterns in match/case (Stanislav Terliakov, PR [18448](https://github.com/python/mypy/pull/18448))
 * Fix parent generics mapping when overriding generic attribute with property (Stanislav Terliakov, PR [18441](https://github.com/python/mypy/pull/18441))
 * Add dedicated error code for explicit `Any` (Shantanu, PR [18398](https://github.com/python/mypy/pull/18398))
 * Reject invalid `ParamSpec` locations (Stanislav Terliakov, PR [18278](https://github.com/python/mypy/pull/18278))
 * Stop suggesting stubs that have been removed from typeshed (Shantanu, PR [18373](https://github.com/python/mypy/pull/18373))
 * Allow inverting `--local-partial-types` (Shantanu, PR [18377](https://github.com/python/mypy/pull/18377))
 * Allow to use `Final` and `ClassVar` after Python 3.13 (정승원, PR [18358](https://github.com/python/mypy/pull/18358))
 * Update suggestions to include latest stubs in typeshed (Shantanu, PR [18366](https://github.com/python/mypy/pull/18366))
 * Fix `--install-types` masking failure details (wyattscarpenter, PR [17485](https://github.com/python/mypy/pull/17485))
 * Reject promotions when checking against protocols (Christoph Tyralla, PR [18360](https://github.com/python/mypy/pull/18360))
 * Don't erase type object arguments in diagnostics (Shantanu, PR [18352](https://github.com/python/mypy/pull/18352))
 * Clarify status in `dmypy status` output (Kcornw, PR [18331](https://github.com/python/mypy/pull/18331))
 * Disallow no-argument generic aliases when using PEP 613 explicit aliases (Brian Schubert, PR [18173](https://github.com/python/mypy/pull/18173))
 * Suppress errors for unreachable branches in conditional expressions (Brian Schubert, PR [18295](https://github.com/python/mypy/pull/18295))
 * Do not allow `ClassVar` and `Final` in `TypedDict` and `NamedTuple` (sobolevn, PR [18281](https://github.com/python/mypy/pull/18281))
 * Report error if not enough or too many types provided to `TypeAliasType` (bzoracler, PR [18308](https://github.com/python/mypy/pull/18308))
 * Use more precise context for `TypedDict` plugin errors (Brian Schubert, PR [18293](https://github.com/python/mypy/pull/18293))
 * Use more precise context for invalid type argument errors (Brian Schubert, PR [18290](https://github.com/python/mypy/pull/18290))
 * Do not allow `type[]` to contain `Literal` types (sobolevn, PR [18276](https://github.com/python/mypy/pull/18276))
 * Allow bytearray/bytes comparisons with `--strict-bytes` (Jukka Lehtosalo, PR [18255](https://github.com/python/mypy/pull/18255))

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

- Advait Dixit
- Ali Hamdan
- Brian Schubert
- bzoracler
- Cameron Matsui
- Christoph Tyralla
- Gareth
- Ivan Levkivskyi
- Jukka Lehtosalo
- Kcornw
- Marc Mueller
- Mikhail f. Shiryaev
- Shantanu
- sobolevn
- Stanislav Terliakov
- Stephen Morton
- Valentin Stanciu
- Viktor Szépe
- wyattscarpenter
- 정승원

I’d also like to thank my employer, Dropbox, for supporting mypy development.

## Mypy 1.14

We’ve just uploaded mypy 1.14 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)).
Mypy is a static type checker for Python. This release includes new features and bug fixes.
You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Change to Enum Membership Semantics

As per the updated [typing specification for enums](https://typing.readthedocs.io/en/latest/spec/enums.html#defining-members),
enum members must be left unannotated.

```python
class Pet(Enum):
    CAT = 1  # Member attribute
    DOG = 2  # Member attribute

    # New error: Enum members must be left unannotated
    WOLF: int = 3

    species: str  # Considered a non-member attribute
```

In particular, the specification change can result in issues in type stubs (`.pyi` files), since
historically it was common to leave the value absent:

```python
# In a type stub (.pyi file)

class Pet(Enum):
    # Change in semantics: previously considered members,
    # now non-member attributes
    CAT: int
    DOG: int

    # Mypy will now issue a warning if it detects this
    # situation in type stubs:
    # > Detected enum "Pet" in a type stub with zero
    # > members. There is a chance this is due to a recent
    # > change in the semantics of enum membership. If so,
    # > use `member = value` to mark an enum member,
    # > instead of `member: type`

class Pet(Enum):
    # As per the specification, you should now do one of
    # the following:
    DOG = 1  # Member attribute with value 1 and known type
    WOLF = cast(int, ...)  # Member attribute with unknown
                           # value but known type
    LION = ...  # Member attribute with unknown value and
                # # unknown type
```

Contributed by Terence Honles (PR [17207](https://github.com/python/mypy/pull/17207)) and
Shantanu Jain (PR [18068](https://github.com/python/mypy/pull/18068)).

### Support for @deprecated Decorator (PEP 702)

Mypy can now issue errors or notes when code imports a deprecated feature
explicitly with a `from mod import depr` statement, or uses a deprecated feature
imported otherwise or defined locally. Features are considered deprecated when
decorated with `warnings.deprecated`, as specified in [PEP 702](https://peps.python.org/pep-0702).

You can enable the error code via `--enable-error-code=deprecated` on the mypy
command line or `enable_error_code = deprecated` in the mypy config file.
Use the command line flag `--report-deprecated-as-note` or config file option
`report_deprecated_as_note=True` to turn all such errors into notes.

Deprecation errors will be enabled by default in a future mypy version.

This feature was contributed by Christoph Tyralla.

List of changes:

 * Add basic support for PEP 702 (`@deprecated`) (Christoph Tyralla, PR [17476](https://github.com/python/mypy/pull/17476))
 * Support descriptors with `@deprecated` (Christoph Tyralla, PR [18090](https://github.com/python/mypy/pull/18090))
 * Make "deprecated" note an error, disabled by default (Valentin Stanciu, PR [18192](https://github.com/python/mypy/pull/18192))
 * Consider all possible type positions with `@deprecated` (Christoph Tyralla, PR [17926](https://github.com/python/mypy/pull/17926))
 * Improve the handling of explicit type annotations in assignment statements with `@deprecated` (Christoph Tyralla, PR [17899](https://github.com/python/mypy/pull/17899))

### Optionally Analyzing Untyped Modules

Mypy normally doesn't analyze imports from third-party modules (installed using pip, for example)
if there are no stubs or a py.typed marker file. To force mypy to analyze these imports, you
can now use the `--follow-untyped-imports` flag or set the `follow_untyped_imports`
config file option to True. This can be set either in the global section of your mypy config
file, or individually on a per-module basis.

This feature was contributed by Jannick Kremer.

List of changes:

 * Implement flag to allow type checking of untyped modules (Jannick Kremer, PR [17712](https://github.com/python/mypy/pull/17712))
 * Warn about `--follow-untyped-imports` (Shantanu, PR [18249](https://github.com/python/mypy/pull/18249))

### Support New Style Type Variable Defaults (PEP 696)

Mypy now supports type variable defaults using the new syntax described in PEP 696, which
was introduced in Python 3.13. Example:

```python
@dataclass
class Box[T = int]:  # Set default for "T"
    value: T | None = None

reveal_type(Box())                      # type is Box[int], since it's the default
reveal_type(Box(value="Hello World!"))  # type is Box[str]
```

This feature was contributed by Marc Mueller (PR [17985](https://github.com/python/mypy/pull/17985)).

### Improved For Loop Index Variable Type Narrowing

Mypy now preserves the literal type of for loop index variables, to support `TypedDict`
lookups. Example:

```python
from typing import TypedDict

class X(TypedDict):
    hourly: int
    daily: int

def func(x: X) -> int:
    s = 0
    for var in ("hourly", "daily"):
        # "Union[Literal['hourly']?, Literal['daily']?]"
        reveal_type(var)

        # x[var] no longer triggers a literal-required error
        s += x[var]
    return s
```

This was contributed by Marc Mueller (PR [18014](https://github.com/python/mypy/pull/18014)).

### Mypyc Improvements

 * Document optimized bytes operations and additional str operations (Jukka Lehtosalo, PR [18242](https://github.com/python/mypy/pull/18242))
 * Add primitives and specialization for `ord()` (Jukka Lehtosalo, PR [18240](https://github.com/python/mypy/pull/18240))
 * Optimize `str.encode` with specializations for common used encodings (Valentin Stanciu, PR [18232](https://github.com/python/mypy/pull/18232))
 * Fix fall back to generic operation for staticmethod and classmethod (Advait Dixit, PR [18228](https://github.com/python/mypy/pull/18228))
 * Support unicode surrogates in string literals (Jukka Lehtosalo, PR [18209](https://github.com/python/mypy/pull/18209))
 * Fix index variable in for loop with `builtins.enumerate` (Advait Dixit, PR [18202](https://github.com/python/mypy/pull/18202))
 * Fix check for enum classes (Advait Dixit, PR [18178](https://github.com/python/mypy/pull/18178))
 * Fix loading type from imported modules (Advait Dixit, PR [18158](https://github.com/python/mypy/pull/18158))
 * Fix initializers of final attributes in class body (Jared Hance, PR [18031](https://github.com/python/mypy/pull/18031))
 * Fix name generation for modules with similar full names (aatle, PR [18001](https://github.com/python/mypy/pull/18001))
 * Fix relative imports in `__init__.py` (Shantanu, PR [17979](https://github.com/python/mypy/pull/17979))
 * Optimize dunder methods (jairov4, PR [17934](https://github.com/python/mypy/pull/17934))
 * Replace deprecated `_PyDict_GetItemStringWithError` (Marc Mueller, PR [17930](https://github.com/python/mypy/pull/17930))
 * Fix wheel build for cp313-win (Marc Mueller, PR [17941](https://github.com/python/mypy/pull/17941))
 * Use public PyGen_GetCode instead of vendored implementation (Marc Mueller, PR [17931](https://github.com/python/mypy/pull/17931))
 * Optimize calls to final classes (jairov4, PR [17886](https://github.com/python/mypy/pull/17886))
 * Support ellipsis (`...`) expressions in class bodies (Newbyte, PR [17923](https://github.com/python/mypy/pull/17923))
 * Sync `pythoncapi_compat.h` (Marc Mueller, PR [17929](https://github.com/python/mypy/pull/17929))
 * Add `runtests.py mypyc-fast` for running fast mypyc tests (Jukka Lehtosalo, PR [17906](https://github.com/python/mypy/pull/17906))

### Stubgen Improvements

 * Do not include mypy generated symbols (Ali Hamdan, PR [18137](https://github.com/python/mypy/pull/18137))
 * Fix `FunctionContext.fullname` for nested classes (Chad Dombrova, PR [17963](https://github.com/python/mypy/pull/17963))
 * Add flagfile support (Ruslan Sayfutdinov, PR [18061](https://github.com/python/mypy/pull/18061))
 * Add support for PEP 695 and PEP 696 syntax (Ali Hamdan, PR [18054](https://github.com/python/mypy/pull/18054))

### Stubtest Improvements

 * Allow the use of `--show-traceback` and `--pdb` with stubtest (Stephen Morton, PR [18037](https://github.com/python/mypy/pull/18037))
 * Verify `__all__` exists in stub (Sebastian Rittau, PR [18005](https://github.com/python/mypy/pull/18005))
 * Stop telling people to use double underscores (Jelle Zijlstra, PR [17897](https://github.com/python/mypy/pull/17897))

### Documentation Updates

 * Update config file documentation (sobolevn, PR [18103](https://github.com/python/mypy/pull/18103))
 * Improve contributor documentation for Windows (ag-tafe, PR [18097](https://github.com/python/mypy/pull/18097))
 * Correct note about `--disallow-any-generics` flag in documentation (Abel Sen, PR [18055](https://github.com/python/mypy/pull/18055))
 * Further caution against `--follow-imports=skip` (Shantanu, PR [18048](https://github.com/python/mypy/pull/18048))
 * Fix the edit page button link in documentation (Kanishk Pachauri, PR [17933](https://github.com/python/mypy/pull/17933))

### Other Notables Fixes and Improvements

 * Allow enum members to have type objects as values (Jukka Lehtosalo, PR [19160](https://github.com/python/mypy/pull/19160))
 * Show `Protocol` `__call__` for arguments with incompatible types (MechanicalConstruct, PR [18214](https://github.com/python/mypy/pull/18214))
 * Make join and meet symmetric with `strict_optional` (MechanicalConstruct, PR [18227](https://github.com/python/mypy/pull/18227))
 * Preserve block unreachablility when checking function definitions with constrained TypeVars (Brian Schubert, PR [18217](https://github.com/python/mypy/pull/18217))
 * Do not include non-init fields in the synthesized `__replace__` method for dataclasses (Victorien, PR [18221](https://github.com/python/mypy/pull/18221))
 * Disallow `TypeVar` constraints parameterized by type variables (Brian Schubert, PR [18186](https://github.com/python/mypy/pull/18186))
 * Always complain about invalid varargs and varkwargs (Shantanu, PR [18207](https://github.com/python/mypy/pull/18207))
 * Set default strict_optional state to True (Shantanu, PR [18198](https://github.com/python/mypy/pull/18198))
 * Preserve type variable default None in type alias (Sukhorosov Aleksey, PR [18197](https://github.com/python/mypy/pull/18197))
 * Add checks for invalid usage of continue/break/return in `except*` block (coldwolverine, PR [18132](https://github.com/python/mypy/pull/18132))
 * Do not consider bare TypeVar not overlapping with None for reachability analysis (Stanislav Terliakov, PR [18138](https://github.com/python/mypy/pull/18138))
 * Special case `types.DynamicClassAttribute` as property-like (Stephen Morton, PR [18150](https://github.com/python/mypy/pull/18150))
 * Disallow bare `ParamSpec` in type aliases (Brian Schubert, PR [18174](https://github.com/python/mypy/pull/18174))
 * Move long_description metadata to pyproject.toml (Marc Mueller, PR [18172](https://github.com/python/mypy/pull/18172))
 * Support `==`-based narrowing of Optional (Christoph Tyralla, PR [18163](https://github.com/python/mypy/pull/18163))
 * Allow TypedDict assignment of Required item to NotRequired ReadOnly item (Brian Schubert, PR [18164](https://github.com/python/mypy/pull/18164))
 * Allow nesting of Annotated with TypedDict special forms inside TypedDicts (Brian Schubert, PR [18165](https://github.com/python/mypy/pull/18165))
 * Infer generic type arguments for slice expressions (Brian Schubert, PR [18160](https://github.com/python/mypy/pull/18160))
 * Fix checking of match sequence pattern against bounded type variables (Brian Schubert, PR [18091](https://github.com/python/mypy/pull/18091))
 * Fix incorrect truthyness for Enum types and literals (David Salvisberg, PR [17337](https://github.com/python/mypy/pull/17337))
 * Move static project metadata to pyproject.toml (Marc Mueller, PR [18146](https://github.com/python/mypy/pull/18146))
 * Fallback to stdlib json if integer exceeds 64-bit range (q0w, PR [18148](https://github.com/python/mypy/pull/18148))
 * Fix 'or' pattern structural matching exhaustiveness (yihong, PR [18119](https://github.com/python/mypy/pull/18119))
 * Fix type inference of positional parameter in class pattern involving builtin subtype (Brian Schubert, PR [18141](https://github.com/python/mypy/pull/18141))
 * Fix `[override]` error with no line number when argument node has no line number (Brian Schubert, PR [18122](https://github.com/python/mypy/pull/18122))
 * Fix some dmypy crashes (Ivan Levkivskyi, PR [18098](https://github.com/python/mypy/pull/18098))
 * Fix subtyping between instance type and overloaded (Shantanu, PR [18102](https://github.com/python/mypy/pull/18102))
 * Clean up new_semantic_analyzer config (Shantanu, PR [18071](https://github.com/python/mypy/pull/18071))
 * Issue warning for enum with no members in stub (Shantanu, PR [18068](https://github.com/python/mypy/pull/18068))
 * Fix enum attributes are not members (Terence Honles, PR [17207](https://github.com/python/mypy/pull/17207))
 * Fix crash when checking slice expression with step 0 in tuple index (Brian Schubert, PR [18063](https://github.com/python/mypy/pull/18063))
 * Allow union-with-callable attributes to be overridden by methods (Brian Schubert, PR [18018](https://github.com/python/mypy/pull/18018))
 * Emit `[mutable-override]` for covariant override of attribute with method (Brian Schubert, PR [18058](https://github.com/python/mypy/pull/18058))
 * Support ParamSpec mapping with `functools.partial` (Stanislav Terliakov, PR [17355](https://github.com/python/mypy/pull/17355))
 * Fix approved stub ignore, remove normpath (Shantanu, PR [18045](https://github.com/python/mypy/pull/18045))
 * Make `disallow-any-unimported` flag invertible (Séamus Ó Ceanainn, PR [18030](https://github.com/python/mypy/pull/18030))
 * Filter to possible package paths before trying to resolve a module (falsedrow, PR [18038](https://github.com/python/mypy/pull/18038))
 * Fix overlap check for ParamSpec types (Jukka Lehtosalo, PR [18040](https://github.com/python/mypy/pull/18040))
 * Do not prioritize ParamSpec signatures during overload resolution (Stanislav Terliakov, PR [18033](https://github.com/python/mypy/pull/18033))
 * Fix ternary union for literals (Ivan Levkivskyi, PR [18023](https://github.com/python/mypy/pull/18023))
 * Fix compatibility checks for conditional function definitions using decorators (Brian Schubert, PR [18020](https://github.com/python/mypy/pull/18020))
 * TypeGuard should be bool not Any when matching TypeVar (Evgeniy Slobodkin, PR [17145](https://github.com/python/mypy/pull/17145))
 * Fix convert-cache tool (Shantanu, PR [17974](https://github.com/python/mypy/pull/17974))
 * Fix generator comprehension with mypyc (Shantanu, PR [17969](https://github.com/python/mypy/pull/17969))
 * Fix crash issue when using shadowfile with pretty (Max Chang, PR [17894](https://github.com/python/mypy/pull/17894))
 * Fix multiple nested classes with new generics syntax (Max Chang, PR [17820](https://github.com/python/mypy/pull/17820))
 * Better error for `mypy -p package` without py.typed (Joe Gordon, PR [17908](https://github.com/python/mypy/pull/17908))
 * Emit error for `raise NotImplemented` (Brian Schubert, PR [17890](https://github.com/python/mypy/pull/17890))
 * Add `is_lvalue` attribute to AttributeContext (Brian Schubert, PR [17881](https://github.com/python/mypy/pull/17881))

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

- aatle
- Abel Sen
- Advait Dixit
- ag-tafe
- Alex Waygood
- Ali Hamdan
- Brian Schubert
- Carlton Gibson
- Chad Dombrova
- Chelsea Durazo
- chiri
- Christoph Tyralla
- coldwolverine
- David Salvisberg
- Ekin Dursun
- Evgeniy Slobodkin
- falsedrow
- Gaurav Giri
- Ihor
- Ivan Levkivskyi
- jairov4
- Jannick Kremer
- Jared Hance
- Jelle Zijlstra
- jianghuyiyuan
- Joe Gordon
- John Doknjas
- Jukka Lehtosalo
- Kanishk Pachauri
- Marc Mueller
- Max Chang
- MechanicalConstruct
- Newbyte
- q0w
- Ruslan Sayfutdinov
- Sebastian Rittau
- Shantanu
- sobolevn
- Stanislav Terliakov
- Stephen Morton
- Sukhorosov Aleksey
- Séamus Ó Ceanainn
- Terence Honles
- Valentin Stanciu
- vasiliy
- Victorien
- yihong

I’d also like to thank my employer, Dropbox, for supporting mypy development.


## Mypy 1.13

We’ve just uploaded mypy 1.13 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)).
Mypy is a static type checker for Python. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

Note that unlike typical releases, Mypy 1.13 does not have any changes to type checking semantics
from 1.12.1.

### Improved Performance

Mypy 1.13 contains several performance improvements. Users can expect mypy to be 5-20% faster.
In environments with long search paths (such as environments using many editable installs), mypy
can be significantly faster, e.g. 2.2x faster in the use case targeted by these improvements.

Mypy 1.13 allows use of the `orjson` library for handling the cache instead of the stdlib `json`,
for improved performance. You can ensure the presence of `orjson` using the `faster-cache` extra:

    python3 -m pip install -U mypy[faster-cache]

Mypy may depend on `orjson` by default in the future.

These improvements were contributed by Shantanu.

List of changes:
* Significantly speed up file handling error paths (Shantanu, PR [17920](https://github.com/python/mypy/pull/17920))
* Use fast path in modulefinder more often (Shantanu, PR [17950](https://github.com/python/mypy/pull/17950))
* Let mypyc optimise os.path.join (Shantanu, PR [17949](https://github.com/python/mypy/pull/17949))
* Make is_sub_path faster (Shantanu, PR [17962](https://github.com/python/mypy/pull/17962))
* Speed up stubs suggestions (Shantanu, PR [17965](https://github.com/python/mypy/pull/17965))
* Use sha1 for hashing (Shantanu, PR [17953](https://github.com/python/mypy/pull/17953))
* Use orjson instead of json, when available (Shantanu, PR [17955](https://github.com/python/mypy/pull/17955))
* Add faster-cache extra, test in CI (Shantanu, PR [17978](https://github.com/python/mypy/pull/17978))

### Acknowledgements
Thanks to all mypy contributors who contributed to this release:

- Shantanu Jain
- Jukka Lehtosalo

## Mypy 1.12

We’ve just uploaded mypy 1.12 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type
checker for Python. This release includes new features, performance improvements and bug fixes.
You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Support Python 3.12 Syntax for Generics (PEP 695)

Support for the new type parameter syntax introduced in Python 3.12 is now enabled by default,
documented, and no longer experimental. It was available through a feature flag in
mypy 1.11 as an experimental feature.

This example demonstrates the new syntax:

```python
# Generic function
def f[T](x: T) -> T: ...

reveal_type(f(1))  # Revealed type is 'int'

# Generic class
class C[T]:
    def __init__(self, x: T) -> None:
       self.x = x

c = C('a')
reveal_type(c.x)  # Revealed type is 'str'

# Type alias
type A[T] = C[list[T]]
```

For more information, refer to the [documentation](https://mypy.readthedocs.io/en/latest/generics.html).

These improvements are included:

 * Document Python 3.12 type parameter syntax (Jukka Lehtosalo, PR [17816](https://github.com/python/mypy/pull/17816))
 * Further documentation updates (Jukka Lehtosalo, PR [17826](https://github.com/python/mypy/pull/17826))
 * Allow Self return types with contravariance (Jukka Lehtosalo, PR [17786](https://github.com/python/mypy/pull/17786))
 * Enable new type parameter syntax by default (Jukka Lehtosalo, PR [17798](https://github.com/python/mypy/pull/17798))
 * Generate error if new-style type alias used as base class (Jukka Lehtosalo, PR [17789](https://github.com/python/mypy/pull/17789))
 * Inherit variance if base class has explicit variance (Jukka Lehtosalo, PR [17787](https://github.com/python/mypy/pull/17787))
 * Fix crash on invalid type var reference (Jukka Lehtosalo, PR [17788](https://github.com/python/mypy/pull/17788))
 * Fix covariance of frozen dataclasses (Jukka Lehtosalo, PR [17783](https://github.com/python/mypy/pull/17783))
 * Allow covariance with attribute that has "`_`" name prefix (Jukka Lehtosalo, PR [17782](https://github.com/python/mypy/pull/17782))
 * Support `Annotated[...]` in new-style type aliases (Jukka Lehtosalo, PR [17777](https://github.com/python/mypy/pull/17777))
 * Fix nested generic classes (Jukka Lehtosalo, PR [17776](https://github.com/python/mypy/pull/17776))
 * Add detection and error reporting for the use of incorrect expressions within the scope of a type parameter and a type alias (Kirill Podoprigora, PR [17560](https://github.com/python/mypy/pull/17560))

### Basic Support for Python 3.13

This release adds partial support for Python 3.13 features and compiled binaries for
Python 3.13. Mypyc now also supports Python 3.13.

In particular, these features are supported:
 * Various new stdlib features and changes (through typeshed stub improvements)
 * `typing.ReadOnly` (see below for more)
 * `typing.TypeIs` (added in mypy 1.10, [PEP 742](https://peps.python.org/pep-0742/))
 * Type parameter defaults when using the legacy syntax ([PEP 696](https://peps.python.org/pep-0696/))

These features are not supported yet:
 * `warnings.deprecated` ([PEP 702](https://peps.python.org/pep-0702/))
 * Type parameter defaults when using Python 3.12 type parameter syntax

### Mypyc Support for Python 3.13

Mypyc now supports Python 3.13. This was contributed by Marc Mueller, with additional
fixes by Jukka Lehtosalo. Free threaded Python 3.13 builds are not supported yet.

List of changes:

 * Add additional includes for Python 3.13 (Marc Mueller, PR [17506](https://github.com/python/mypy/pull/17506))
 * Add another include for Python 3.13 (Marc Mueller, PR [17509](https://github.com/python/mypy/pull/17509))
 * Fix ManagedDict functions for Python 3.13 (Marc Mueller, PR [17507](https://github.com/python/mypy/pull/17507))
 * Update mypyc test output for Python 3.13 (Marc Mueller, PR [17508](https://github.com/python/mypy/pull/17508))
 * Fix `PyUnicode` functions for Python 3.13 (Marc Mueller, PR [17504](https://github.com/python/mypy/pull/17504))
 * Fix `_PyObject_LookupAttrId` for Python 3.13 (Marc Mueller, PR [17505](https://github.com/python/mypy/pull/17505))
 * Fix `_PyList_Extend` for Python 3.13 (Marc Mueller, PR [17503](https://github.com/python/mypy/pull/17503))
 * Fix `gen_is_coroutine` for Python 3.13 (Marc Mueller, PR [17501](https://github.com/python/mypy/pull/17501))
 * Fix `_PyObject_FastCall` for Python 3.13 (Marc Mueller, PR [17502](https://github.com/python/mypy/pull/17502))
 * Avoid uses of `_PyObject_CallMethodOneArg` on 3.13 (Jukka Lehtosalo, PR [17526](https://github.com/python/mypy/pull/17526))
 * Don't rely on `_PyType_CalculateMetaclass` on 3.13 (Jukka Lehtosalo, PR [17525](https://github.com/python/mypy/pull/17525))
 * Don't use `_PyUnicode_FastCopyCharacters` on 3.13 (Jukka Lehtosalo, PR [17524](https://github.com/python/mypy/pull/17524))
 * Don't use `_PyUnicode_EQ` on 3.13, as it's no longer exported (Jukka Lehtosalo, PR [17523](https://github.com/python/mypy/pull/17523))

### Inferring Unions for Conditional Expressions

Mypy now always tries to infer a union type for a conditional expression if left and right
operand types are different. This results in more precise inferred types and lets mypy detect
more issues. Example:

```python
s = "foo" if cond() else 1
# Type of "s" is now "str | int" (it used to be "object")
```

Notably, if one of the operands has type `Any`, the type of a conditional expression is
now `<type> | Any`. Previously the inferred type was just `Any`. The new type essentially
indicates that the value can be of type `<type>`, and potentially of some (unknown) type.
Most operations performed on the result must also be valid for `<type>`.
Example where this is relevant:

```python
from typing import Any

def func(a: Any, b: bool) -> None:
    x = a if b else None
    # Type of x is "Any | None"
    print(x.y)  # Error: None has no attribute "y"
```

This feature was contributed by Ivan Levkivskyi (PR [17427](https://github.com/python/mypy/pull/17427)).

### ReadOnly Support for TypedDict (PEP 705)

You can now use `typing.ReadOnly` to specity TypedDict items as
read-only ([PEP 705](https://peps.python.org/pep-0705/)):

```python
from typing import TypedDict

# Or "from typing ..." on Python 3.13
from typing_extensions import ReadOnly

class TD(TypedDict):
    a: int
    b: ReadOnly[int]

d: TD = {"a": 1, "b": 2}
d["a"] = 3  # OK
d["b"] = 5  # Error: "b" is ReadOnly
```

This feature was contributed by Nikita Sobolev (PR [17644](https://github.com/python/mypy/pull/17644)).

### Python 3.8 End of Life Approaching

We are planning to drop support for Python 3.8 in the next mypy feature release or the
one after that. Python 3.8 reaches end of life in October 2024.

### Planned Changes to Defaults

We are planning to enable `--local-partial-types` by default in mypy 2.0. This will
often require at least minor code changes. This option is implicitly enabled by mypy
daemon, so this makes the behavior of daemon and non-daemon modes consistent.

We recommend that mypy users start using local partial types soon (or to explicitly disable
them) to prepare for the change.

This can also be configured in a mypy configuration file:

```
local_partial_types = True
```

For more information, refer to the
[documentation](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-local-partial-types).

### Documentation Updates

Mypy documentation now uses modern syntax variants and imports in many examples. Some
examples no longer work on Python 3.8, which is the earliest Python version that mypy supports.

Notably, `Iterable` and other protocols/ABCs are imported from `collections.abc` instead of
`typing`:
```python
from collections.abc import Iterable, Callable
```

Examples also avoid the upper-case aliases to built-in types: `list[str]` is used instead
of `List[str]`. The `X | Y` union type syntax introduced in Python 3.10 is also now prevalent.

List of documentation updates:

 * Document `--output=json` CLI option (Edgar Ramírez Mondragón, PR [17611](https://github.com/python/mypy/pull/17611))
 * Update various references to deprecated type aliases in docs (Jukka Lehtosalo, PR [17829](https://github.com/python/mypy/pull/17829))
 * Make "X | Y" union syntax more prominent in documentation (Jukka Lehtosalo, PR [17835](https://github.com/python/mypy/pull/17835))
 * Discuss upper bounds before self types in documentation (Jukka Lehtosalo, PR [17827](https://github.com/python/mypy/pull/17827))
 * Make changelog visible in mypy documentation (quinn-sasha, PR [17742](https://github.com/python/mypy/pull/17742))
 * List all incomplete features in `--enable-incomplete-feature` docs (sobolevn, PR [17633](https://github.com/python/mypy/pull/17633))
 * Remove the explicit setting of a pygments theme (Pradyun Gedam, PR [17571](https://github.com/python/mypy/pull/17571))
 * Document ReadOnly with TypedDict (Jukka Lehtosalo, PR [17905](https://github.com/python/mypy/pull/17905))
 * Document TypeIs (Chelsea Durazo, PR [17821](https://github.com/python/mypy/pull/17821))

### Experimental Inline TypedDict Syntax

Mypy now supports a non-standard, experimental syntax for defining anonymous TypedDicts.
Example:

```python
def func(n: str, y: int) -> {"name": str, "year": int}:
    return {"name": n, "year": y}
```

The feature is disabled by default. Use `--enable-incomplete-feature=InlineTypedDict` to
enable it. *We might remove this feature in a future release.*

This feature was contributed by Ivan Levkivskyi (PR [17457](https://github.com/python/mypy/pull/17457)).

### Stubgen Improvements

 * Fix crash on literal class-level keywords (sobolevn, PR [17663](https://github.com/python/mypy/pull/17663))
 * Stubgen add `--version` (sobolevn, PR [17662](https://github.com/python/mypy/pull/17662))
 * Fix `stubgen --no-analysis/--parse-only` docs (sobolevn, PR [17632](https://github.com/python/mypy/pull/17632))
 * Include keyword only args when generating signatures in stubgenc (Eric Mark Martin, PR [17448](https://github.com/python/mypy/pull/17448))
 * Add support for detecting `Literal` types when extracting types from docstrings (Michael Carlstrom, PR [17441](https://github.com/python/mypy/pull/17441))
 * Use `Generator` type var defaults (Sebastian Rittau, PR [17670](https://github.com/python/mypy/pull/17670))

### Stubtest Improvements
 * Add support for `cached_property` (Ali Hamdan, PR [17626](https://github.com/python/mypy/pull/17626))
 * Add `enable_incomplete_feature` validation to `stubtest` (sobolevn, PR [17635](https://github.com/python/mypy/pull/17635))
 * Fix error code handling in `stubtest` with `--mypy-config-file` (sobolevn, PR [17629](https://github.com/python/mypy/pull/17629))

### Other Notables Fixes and Improvements

 * Report error if using unsupported type parameter defaults (Jukka Lehtosalo, PR [17876](https://github.com/python/mypy/pull/17876))
 * Fix re-processing cross-reference in mypy daemon when node kind changes (Ivan Levkivskyi, PR [17883](https://github.com/python/mypy/pull/17883))
 * Don't use equality to narrow when value is IntEnum/StrEnum (Jukka Lehtosalo, PR [17866](https://github.com/python/mypy/pull/17866))
 * Don't consider None vs IntEnum comparison ambiguous (Jukka Lehtosalo, PR [17877](https://github.com/python/mypy/pull/17877))
 * Fix narrowing of IntEnum and StrEnum types (Jukka Lehtosalo, PR [17874](https://github.com/python/mypy/pull/17874))
 * Filter overload items based on self type during type inference (Jukka Lehtosalo, PR [17873](https://github.com/python/mypy/pull/17873))
 * Enable negative narrowing of union TypeVar upper bounds (Brian Schubert, PR [17850](https://github.com/python/mypy/pull/17850))
 * Fix issue with member expression formatting (Brian Schubert, PR [17848](https://github.com/python/mypy/pull/17848))
 * Avoid type size explosion when expanding types (Jukka Lehtosalo, PR [17842](https://github.com/python/mypy/pull/17842))
 * Fix negative narrowing of tuples in match statement (Brian Schubert, PR [17817](https://github.com/python/mypy/pull/17817))
 * Narrow falsey str/bytes/int to literal type (Brian Schubert, PR [17818](https://github.com/python/mypy/pull/17818))
 * Test against latest Python 3.13, make testing 3.14 easy (Shantanu, PR [17812](https://github.com/python/mypy/pull/17812))
 * Reject ParamSpec-typed callables calls with insufficient arguments (Stanislav Terliakov, PR [17323](https://github.com/python/mypy/pull/17323))
 * Fix crash when passing too many type arguments to generic base class accepting single ParamSpec (Brian Schubert, PR [17770](https://github.com/python/mypy/pull/17770))
 * Fix TypeVar upper bounds sometimes not being displayed in pretty callables (Brian Schubert, PR [17802](https://github.com/python/mypy/pull/17802))
 * Added error code for overlapping function signatures (Katrina Connors, PR [17597](https://github.com/python/mypy/pull/17597))
 * Check for `truthy-bool` in `not ...` unary expressions (sobolevn, PR [17773](https://github.com/python/mypy/pull/17773))
 * Add missing lines-covered and lines-valid attributes (Soubhik Kumar Mitra, PR [17738](https://github.com/python/mypy/pull/17738))
 * Fix another crash scenario with recursive tuple types (Ivan Levkivskyi, PR [17708](https://github.com/python/mypy/pull/17708))
 * Resolve TypeVar upper bounds in `functools.partial` (Shantanu, PR [17660](https://github.com/python/mypy/pull/17660))
 * Always reset binder when checking deferred nodes (Ivan Levkivskyi, PR [17643](https://github.com/python/mypy/pull/17643))
 * Fix crash on a callable attribute with single unpack (Ivan Levkivskyi, PR [17641](https://github.com/python/mypy/pull/17641))
 * Fix mismatched signature between checker plugin API and implementation (bzoracler, PR [17343](https://github.com/python/mypy/pull/17343))
 * Indexing a type also produces a GenericAlias (Shantanu, PR [17546](https://github.com/python/mypy/pull/17546))
 * Fix crash on self-type in callable protocol (Ivan Levkivskyi, PR [17499](https://github.com/python/mypy/pull/17499))
 * Fix crash on NamedTuple with method and error in function (Ivan Levkivskyi, PR [17498](https://github.com/python/mypy/pull/17498))
 * Add `__replace__` for dataclasses in 3.13 (Max Muoto, PR [17469](https://github.com/python/mypy/pull/17469))
 * Fix help message for `--no-namespace-packages` (Raphael Krupinski, PR [17472](https://github.com/python/mypy/pull/17472))
 * Fix typechecking for async generators (Danny Yang, PR [17452](https://github.com/python/mypy/pull/17452))
 * Fix strict optional handling in attrs plugin (Ivan Levkivskyi, PR [17451](https://github.com/python/mypy/pull/17451))
 * Allow mixing ParamSpec and TypeVarTuple in Generic (Ivan Levkivskyi, PR [17450](https://github.com/python/mypy/pull/17450))
 * Improvements to `functools.partial` of types (Shantanu, PR [17898](https://github.com/python/mypy/pull/17898))
 * Make ReadOnly TypedDict items covariant (Jukka Lehtosalo, PR [17904](https://github.com/python/mypy/pull/17904))
 * Fix union callees with `functools.partial` (Jukka Lehtosalo, PR [17903](https://github.com/python/mypy/pull/17903))
 * Improve handling of generic functions with `functools.partial` (Ivan Levkivskyi, PR [17925](https://github.com/python/mypy/pull/17925))

### Typeshed Updates

Please see [git log](https://github.com/python/typeshed/commits/main?after=91a58b07cdd807b1d965e04ba85af2adab8bf924+0&branch=main&path=stdlib) for full list of standard library typeshed stub changes.

### Mypy 1.12.1
 * Fix crash when showing partially analyzed type in error message (Ivan Levkivskyi, PR [17961](https://github.com/python/mypy/pull/17961))
 * Fix iteration over union (when self type is involved) (Shantanu, PR [17976](https://github.com/python/mypy/pull/17976))
 * Fix type object with type var default in union context (Jukka Lehtosalo, PR [17991](https://github.com/python/mypy/pull/17991))
 * Revert change to `os.path` stubs affecting use of `os.PathLike[Any]` (Shantanu, PR [17995](https://github.com/python/mypy/pull/17995))

### Acknowledgements
Thanks to all mypy contributors who contributed to this release:

- Ali Hamdan
- Anders Kaseorg
- Bénédikt Tran
- Brian Schubert
- bzoracler
- Chelsea Durazo
- Danny Yang
- Edgar Ramírez Mondragón
- Eric Mark Martin
- InSync
- Ivan Levkivskyi
- Jordandev678
- Katrina Connors
- Kirill Podoprigora
- Marc Mueller
- Max Muoto
- Max Murin
- Michael Carlstrom
- Michael I Chen
- Pradyun Gedam
- quinn-sasha
- Raphael Krupinski
- Sebastian Rittau
- Shantanu
- sobolevn
- Soubhik Kumar Mitra
- Stanislav Terliakov
- wyattscarpenter

I’d also like to thank my employer, Dropbox, for supporting mypy development.


## Mypy 1.11

We’ve just uploaded mypy 1.11 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Support Python 3.12 Syntax for Generics (PEP 695)

Mypy now supports the new type parameter syntax introduced in Python 3.12 ([PEP 695](https://peps.python.org/pep-0695/)).
This feature is still experimental and must be enabled with the `--enable-incomplete-feature=NewGenericSyntax` flag, or with `enable_incomplete_feature = NewGenericSyntax` in the mypy configuration file.
We plan to enable this by default in the next mypy feature release.

This example demonstrates the new syntax:

```python
# Generic function
def f[T](x: T) -> T: ...

reveal_type(f(1))  # Revealed type is 'int'

# Generic class
class C[T]:
    def __init__(self, x: T) -> None:
       self.x = x

c = C('a')
reveal_type(c.x)  # Revealed type is 'str'

# Type alias
type A[T] = C[list[T]]
```

This feature was contributed by Jukka Lehtosalo.


### Support for `functools.partial`

Mypy now type checks uses of `functools.partial`. Previously mypy would accept arbitrary arguments.

This example will now produce an error:

```python
from functools import partial

def f(a: int, b: str) -> None: ...

g = partial(f, 1)

# Argument has incompatible type "int"; expected "str"
g(11)
```

This feature was contributed by Shantanu (PR [16939](https://github.com/python/mypy/pull/16939)).


### Stricter Checks for Untyped Overrides

Past mypy versions didn't check if untyped methods were compatible with overridden methods. This would result in false negatives. Now mypy performs these checks when using `--check-untyped-defs`.

For example, this now generates an error if using `--check-untyped-defs`:

```python
class Base:
    def f(self, x: int = 0) -> None: ...

class Derived(Base):
    # Signature incompatible with "Base"
    def f(self): ...
```

This feature was contributed by Steven Troxler (PR [17276](https://github.com/python/mypy/pull/17276)).


### Type Inference Improvements

The new polymorphic inference algorithm introduced in mypy 1.5 is now used in more situations. This improves type inference involving generic higher-order functions, in particular.

This feature was contributed by Ivan Levkivskyi (PR [17348](https://github.com/python/mypy/pull/17348)).

Mypy now uses unions of tuple item types in certain contexts to enable more precise inferred types. Example:

```python
for x in (1, 'x'):
    # Previously inferred as 'object'
    reveal_type(x)  # Revealed type is 'int | str'
```

This was also contributed by Ivan Levkivskyi (PR [17408](https://github.com/python/mypy/pull/17408)).


### Improvements to Detection of Overlapping Overloads

The details of how mypy checks if two `@overload` signatures are unsafely overlapping were overhauled. This both fixes some false positives, and allows mypy to detect additional unsafe signatures.

This feature was contributed by Ivan Levkivskyi (PR [17392](https://github.com/python/mypy/pull/17392)).


### Better Support for Type Hints in Expressions

Mypy now allows more expressions that evaluate to valid type annotations in all expression contexts. The inferred types of these expressions are also sometimes more precise. Previously they were often `object`.

This example uses a union type that includes a callable type as an expression, and it no longer generates an error:

```python
from typing import Callable

print(Callable[[], int] | None)  # No error
```

This feature was contributed by Jukka Lehtosalo (PR [17404](https://github.com/python/mypy/pull/17404)).


### Mypyc Improvements

Mypyc now supports the new syntax for generics introduced in Python 3.12 (see above). Another notable improvement is significantly faster basic operations on `int` values.

 * Support Python 3.12 syntax for generic functions and classes (Jukka Lehtosalo, PR [17357](https://github.com/python/mypy/pull/17357))
 * Support Python 3.12 type alias syntax (Jukka Lehtosalo, PR [17384](https://github.com/python/mypy/pull/17384))
 * Fix ParamSpec (Shantanu, PR [17309](https://github.com/python/mypy/pull/17309))
 * Inline fast paths of integer unboxing operations (Jukka Lehtosalo, PR [17266](https://github.com/python/mypy/pull/17266))
 * Inline tagged integer arithmetic and bitwise operations (Jukka Lehtosalo, PR [17265](https://github.com/python/mypy/pull/17265))
 * Allow specifying primitives as pure (Jukka Lehtosalo, PR [17263](https://github.com/python/mypy/pull/17263))


### Changes to Stubtest
 * Ignore `_ios_support` (Alex Waygood, PR [17270](https://github.com/python/mypy/pull/17270))
 * Improve support for Python 3.13 (Shantanu, PR [17261](https://github.com/python/mypy/pull/17261))


### Changes to Stubgen
 * Gracefully handle invalid `Optional` and recognize aliases to PEP 604 unions (Ali Hamdan, PR [17386](https://github.com/python/mypy/pull/17386))
 * Fix for Python 3.13 (Jelle Zijlstra, PR [17290](https://github.com/python/mypy/pull/17290))
 * Preserve enum value initialisers (Shantanu, PR [17125](https://github.com/python/mypy/pull/17125))


### Miscellaneous New Features
 * Add error format support and JSON output option via `--output json` (Tushar Sadhwani, PR [11396](https://github.com/python/mypy/pull/11396))
 * Support `enum.member` in Python 3.11+ (Nikita Sobolev, PR [17382](https://github.com/python/mypy/pull/17382))
 * Support `enum.nonmember` in Python 3.11+ (Nikita Sobolev, PR [17376](https://github.com/python/mypy/pull/17376))
 * Support `namedtuple.__replace__` in Python 3.13 (Shantanu, PR [17259](https://github.com/python/mypy/pull/17259))
 * Support `rename=True` in collections.namedtuple (Jelle Zijlstra, PR [17247](https://github.com/python/mypy/pull/17247))
 * Add support for `__spec__` (Shantanu, PR [14739](https://github.com/python/mypy/pull/14739))


### Changes to Error Reporting
 * Mention `--enable-incomplete-feature=NewGenericSyntax` in messages (Shantanu, PR [17462](https://github.com/python/mypy/pull/17462))
 * Do not report plugin-generated methods with `explicit-override` (sobolevn, PR [17433](https://github.com/python/mypy/pull/17433))
 * Use and display namespaces for function type variables (Ivan Levkivskyi, PR [17311](https://github.com/python/mypy/pull/17311))
 * Fix false positive for Final local scope variable in Protocol (GiorgosPapoutsakis, PR [17308](https://github.com/python/mypy/pull/17308))
 * Use Never in more messages, use ambiguous in join (Shantanu, PR [17304](https://github.com/python/mypy/pull/17304))
 * Log full path to config file in verbose output (dexterkennedy, PR [17180](https://github.com/python/mypy/pull/17180))
 * Added `[prop-decorator]` code for unsupported property decorators (#14461) (Christopher Barber, PR [16571](https://github.com/python/mypy/pull/16571))
 * Suppress second error message with `:=` and `[truthy-bool]` (Nikita Sobolev, PR [15941](https://github.com/python/mypy/pull/15941))
 * Generate error for assignment of functional Enum to variable of different name (Shantanu, PR [16805](https://github.com/python/mypy/pull/16805))
 * Fix error reporting on cached run after uninstallation of third party library (Shantanu, PR [17420](https://github.com/python/mypy/pull/17420))


### Fixes for Crashes
 * Fix daemon crash on invalid type in TypedDict (Ivan Levkivskyi, PR [17495](https://github.com/python/mypy/pull/17495))
 * Fix crash and bugs related to `partial()` (Ivan Levkivskyi, PR [17423](https://github.com/python/mypy/pull/17423))
 * Fix crash when overriding with unpacked TypedDict (Ivan Levkivskyi, PR [17359](https://github.com/python/mypy/pull/17359))
 * Fix crash on TypedDict unpacking for ParamSpec (Ivan Levkivskyi, PR [17358](https://github.com/python/mypy/pull/17358))
 * Fix crash involving recursive union of tuples (Ivan Levkivskyi, PR [17353](https://github.com/python/mypy/pull/17353))
 * Fix crash on invalid callable property override (Ivan Levkivskyi, PR [17352](https://github.com/python/mypy/pull/17352))
 * Fix crash on unpacking self in NamedTuple (Ivan Levkivskyi, PR [17351](https://github.com/python/mypy/pull/17351))
 * Fix crash on recursive alias with an optional type (Ivan Levkivskyi, PR [17350](https://github.com/python/mypy/pull/17350))
 * Fix crash on type comment inside generic definitions (Bénédikt Tran, PR [16849](https://github.com/python/mypy/pull/16849))


### Changes to Documentation
 * Use inline config in documentation for optional error codes (Shantanu, PR [17374](https://github.com/python/mypy/pull/17374))
 * Use lower-case generics in documentation (Seo Sanghyeon, PR [17176](https://github.com/python/mypy/pull/17176))
 * Add documentation for show-error-code-links (GiorgosPapoutsakis, PR [17144](https://github.com/python/mypy/pull/17144))
 * Update CONTRIBUTING.md to include commands for Windows (GiorgosPapoutsakis, PR [17142](https://github.com/python/mypy/pull/17142))


### Other Notable Improvements and Fixes
 * Fix ParamSpec inference against TypeVarTuple (Ivan Levkivskyi, PR [17431](https://github.com/python/mypy/pull/17431))
 * Fix explicit type for `partial` (Ivan Levkivskyi, PR [17424](https://github.com/python/mypy/pull/17424))
 * Always allow lambda calls (Ivan Levkivskyi, PR [17430](https://github.com/python/mypy/pull/17430))
 * Fix isinstance checks with PEP 604 unions containing None (Shantanu, PR [17415](https://github.com/python/mypy/pull/17415))
 * Fix self-referential upper bound in new-style type variables (Ivan Levkivskyi, PR [17407](https://github.com/python/mypy/pull/17407))
 * Consider overlap between instances and callables (Ivan Levkivskyi, PR [17389](https://github.com/python/mypy/pull/17389))
 * Allow new-style self-types in classmethods (Ivan Levkivskyi, PR [17381](https://github.com/python/mypy/pull/17381))
 * Fix isinstance with type aliases to PEP 604 unions (Shantanu, PR [17371](https://github.com/python/mypy/pull/17371))
 * Properly handle unpacks in overlap checks (Ivan Levkivskyi, PR [17356](https://github.com/python/mypy/pull/17356))
 * Fix type application for classes with generic constructors (Ivan Levkivskyi, PR [17354](https://github.com/python/mypy/pull/17354))
 * Update `typing_extensions` to >=4.6.0 to fix Python 3.12 error (Ben Brown, PR [17312](https://github.com/python/mypy/pull/17312))
 * Avoid "does not return" error in lambda (Shantanu, PR [17294](https://github.com/python/mypy/pull/17294))
 * Fix bug with descriptors in non-strict-optional mode (Max Murin, PR [17293](https://github.com/python/mypy/pull/17293))
 * Don’t leak unreachability from lambda body to surrounding scope (Anders Kaseorg, PR [17287](https://github.com/python/mypy/pull/17287))
 * Fix issues with non-ASCII characters on Windows (Alexander Leopold Shon, PR [17275](https://github.com/python/mypy/pull/17275))
 * Fix for type narrowing of negative integer literals (gilesgc, PR [17256](https://github.com/python/mypy/pull/17256))
 * Fix confusion between .py and .pyi files in mypy daemon (Valentin Stanciu, PR [17245](https://github.com/python/mypy/pull/17245))
 * Fix type of `tuple[X, Y]` expression (urnest, PR [17235](https://github.com/python/mypy/pull/17235))
 * Don't forget that a `TypedDict` was wrapped in `Unpack` after a `name-defined` error occurred (Christoph Tyralla, PR [17226](https://github.com/python/mypy/pull/17226))
 * Mark annotated argument as having an explicit, not inferred type (bzoracler, PR [17217](https://github.com/python/mypy/pull/17217))
 * Don't consider Enum private attributes as enum members (Ali Hamdan, PR [17182](https://github.com/python/mypy/pull/17182))
 * Fix Literal strings containing pipe characters (Jelle Zijlstra, PR [17148](https://github.com/python/mypy/pull/17148))


### Typeshed Updates

Please see [git log](https://github.com/python/typeshed/commits/main?after=6dda799d8ad1d89e0f8aad7ac41d2d34bd838ace+0&branch=main&path=stdlib) for full list of standard library typeshed stub changes.

### Mypy 1.11.1
 * Fix `RawExpressionType.accept` crash with `--cache-fine-grained` (Anders Kaseorg, PR [17588](https://github.com/python/mypy/pull/17588))
 * Fix PEP 604 isinstance caching (Shantanu, PR [17563](https://github.com/python/mypy/pull/17563))
 * Fix `typing.TypeAliasType` being undefined on python < 3.12 (Nikita Sobolev, PR [17558](https://github.com/python/mypy/pull/17558))
 * Fix `types.GenericAlias` lookup crash (Shantanu, PR [17543](https://github.com/python/mypy/pull/17543))

### Mypy 1.11.2
 * Alternative fix for a union-like literal string (Ivan Levkivskyi, PR [17639](https://github.com/python/mypy/pull/17639))
 * Unwrap `TypedDict` item types before storing (Ivan Levkivskyi, PR [17640](https://github.com/python/mypy/pull/17640))

### Acknowledgements
Thanks to all mypy contributors who contributed to this release:

- Alex Waygood
- Alexander Leopold Shon
- Ali Hamdan
- Anders Kaseorg
- Ben Brown
- Bénédikt Tran
- bzoracler
- Christoph Tyralla
- Christopher Barber
- dexterkennedy
- gilesgc
- GiorgosPapoutsakis
- Ivan Levkivskyi
- Jelle Zijlstra
- Jukka Lehtosalo
- Marc Mueller
- Matthieu Devlin
- Michael R. Crusoe
- Nikita Sobolev
- Seo Sanghyeon
- Shantanu
- sobolevn
- Steven Troxler
- Tadeu Manoel
- Tamir Duberstein
- Tushar Sadhwani
- urnest
- Valentin Stanciu

I’d also like to thank my employer, Dropbox, for supporting mypy development.


## Mypy 1.10

We’ve just uploaded mypy 1.10 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Support TypeIs (PEP 742)

Mypy now supports `TypeIs` ([PEP 742](https://peps.python.org/pep-0742/)), which allows
functions to narrow the type of a value, similar to `isinstance()`. Unlike `TypeGuard`,
`TypeIs` can narrow in both the `if` and `else` branches of an if statement:

```python
from typing_extensions import TypeIs

def is_str(s: object) -> TypeIs[str]:
    return isinstance(s, str)

def f(o: str | int) -> None:
    if is_str(o):
        # Type of o is 'str'
        ...
    else:
        # Type of o is 'int'
        ...
```

`TypeIs` will be added to the `typing` module in Python 3.13, but it
can be used on earlier Python versions by importing it from
`typing_extensions`.

This feature was contributed by Jelle Zijlstra (PR [16898](https://github.com/python/mypy/pull/16898)).

### Support TypeVar Defaults (PEP 696)

[PEP 696](https://peps.python.org/pep-0696/) adds support for type parameter defaults.
Example:

```python
from typing import Generic
from typing_extensions import TypeVar

T = TypeVar("T", default=int)

class C(Generic[T]):
   ...

x: C = ...
y: C[str] = ...
reveal_type(x)  # C[int], because of the default
reveal_type(y)  # C[str]
```

TypeVar defaults will be added to the `typing` module in Python 3.13, but they
can be used with earlier Python releases by importing `TypeVar` from
`typing_extensions`.

This feature was contributed by Marc Mueller (PR [16878](https://github.com/python/mypy/pull/16878)
and PR [16925](https://github.com/python/mypy/pull/16925)).

### Support TypeAliasType (PEP 695)
As part of the initial steps towards implementing [PEP 695](https://peps.python.org/pep-0695/), mypy now supports `TypeAliasType`.
`TypeAliasType` provides a backport of the new `type` statement in Python 3.12.

```python
type ListOrSet[T] = list[T] | set[T]
```

is equivalent to:

```python
T = TypeVar("T")
ListOrSet = TypeAliasType("ListOrSet", list[T] | set[T], type_params=(T,))
```

Example of use in mypy:

```python
from typing_extensions import TypeAliasType, TypeVar

NewUnionType = TypeAliasType("NewUnionType", int | str)
x: NewUnionType = 42
y: NewUnionType = 'a'
z: NewUnionType = object()  # error: Incompatible types in assignment (expression has type "object", variable has type "int | str")  [assignment]

T = TypeVar("T")
ListOrSet = TypeAliasType("ListOrSet", list[T] | set[T], type_params=(T,))
a: ListOrSet[int] = [1, 2]
b: ListOrSet[str] = {'a', 'b'}
c: ListOrSet[str] = 'test'  # error: Incompatible types in assignment (expression has type "str", variable has type "list[str] | set[str]")  [assignment]
```

`TypeAliasType` was added to the `typing` module in Python 3.12, but it can be used with earlier Python releases by importing from `typing_extensions`.

This feature was contributed by Ali Hamdan (PR [16926](https://github.com/python/mypy/pull/16926), PR [17038](https://github.com/python/mypy/pull/17038) and PR [17053](https://github.com/python/mypy/pull/17053))

### Detect Additional Unsafe Uses of super()

Mypy will reject unsafe uses of `super()` more consistently, when the target has a
trivial (empty) body. Example:

```python
class Proto(Protocol):
    def method(self) -> int: ...

class Sub(Proto):
    def method(self) -> int:
        return super().meth()  # Error (unsafe)
```

This feature was contributed by Shantanu (PR [16756](https://github.com/python/mypy/pull/16756)).

### Stubgen Improvements
- Preserve empty tuple annotation (Ali Hamdan, PR [16907](https://github.com/python/mypy/pull/16907))
- Add support for PEP 570 positional-only parameters (Ali Hamdan, PR [16904](https://github.com/python/mypy/pull/16904))
- Replace obsolete typing aliases with builtin containers (Ali Hamdan, PR [16780](https://github.com/python/mypy/pull/16780))
- Fix generated dataclass `__init__` signature (Ali Hamdan, PR [16906](https://github.com/python/mypy/pull/16906))

### Mypyc Improvements

- Provide an easier way to define IR-to-IR transforms (Jukka Lehtosalo, PR [16998](https://github.com/python/mypy/pull/16998))
- Implement lowering pass and add primitives for int (in)equality (Jukka Lehtosalo, PR [17027](https://github.com/python/mypy/pull/17027))
- Implement lowering for remaining tagged integer comparisons (Jukka Lehtosalo, PR [17040](https://github.com/python/mypy/pull/17040))
- Optimize away some bool/bit registers (Jukka Lehtosalo, PR [17022](https://github.com/python/mypy/pull/17022))
- Remangle redefined names produced by async with (Richard Si, PR [16408](https://github.com/python/mypy/pull/16408))
- Optimize TYPE_CHECKING to False at Runtime (Srinivas Lade, PR [16263](https://github.com/python/mypy/pull/16263))
- Fix compilation of unreachable comprehensions (Richard Si, PR [15721](https://github.com/python/mypy/pull/15721))
- Don't crash on non-inlinable final local reads (Richard Si, PR [15719](https://github.com/python/mypy/pull/15719))

### Documentation Improvements
- Import `TypedDict` from `typing` instead of `typing_extensions` (Riccardo Di Maio, PR [16958](https://github.com/python/mypy/pull/16958))
- Add missing `mutable-override` to section title (James Braza, PR [16886](https://github.com/python/mypy/pull/16886))

### Error Reporting Improvements

- Use lower-case generics more consistently in error messages (Jukka Lehtosalo, PR [17035](https://github.com/python/mypy/pull/17035))

### Other Notable Changes and Fixes
- Fix incorrect inferred type when accessing descriptor on union type (Matthieu Devlin, PR [16604](https://github.com/python/mypy/pull/16604))
- Fix crash when expanding invalid `Unpack` in a `Callable` alias (Ali Hamdan, PR [17028](https://github.com/python/mypy/pull/17028))
- Fix false positive when string formatting with string enum (roberfi, PR [16555](https://github.com/python/mypy/pull/16555))
- Narrow individual items when matching a tuple to a sequence pattern (Loïc Simon, PR [16905](https://github.com/python/mypy/pull/16905))
- Fix false positive from type variable within TypeGuard or TypeIs (Evgeniy Slobodkin, PR [17071](https://github.com/python/mypy/pull/17071))
- Improve `yield from` inference for unions of generators (Shantanu, PR [16717](https://github.com/python/mypy/pull/16717))
- Fix emulating hash method logic in `attrs` classes (Hashem, PR [17016](https://github.com/python/mypy/pull/17016))
- Add reverted typeshed commit that uses `ParamSpec` for `functools.wraps` (Tamir Duberstein, PR [16942](https://github.com/python/mypy/pull/16942))
- Fix type narrowing for `types.EllipsisType` (Shantanu, PR [17003](https://github.com/python/mypy/pull/17003))
- Fix single item enum match type exhaustion (Oskari Lehto, PR [16966](https://github.com/python/mypy/pull/16966))
- Improve type inference with empty collections (Marc Mueller, PR [16994](https://github.com/python/mypy/pull/16994))
- Fix override checking for decorated property (Shantanu, PR [16856](https://github.com/python/mypy/pull/16856))
- Fix narrowing on match with function subject (Edward Paget, PR [16503](https://github.com/python/mypy/pull/16503))
- Allow `+N` within `Literal[...]` (Spencer Brown, PR [16910](https://github.com/python/mypy/pull/16910))
- Experimental: Support TypedDict within `type[...]` (Marc Mueller, PR [16963](https://github.com/python/mypy/pull/16963))
- Experimtental: Fix issue with TypedDict with optional keys in `type[...]` (Marc Mueller, PR [17068](https://github.com/python/mypy/pull/17068))

### Typeshed Updates

Please see [git log](https://github.com/python/typeshed/commits/main?after=6dda799d8ad1d89e0f8aad7ac41d2d34bd838ace+0&branch=main&path=stdlib) for full list of standard library typeshed stub changes.

### Mypy 1.10.1

- Fix error reporting on cached run after uninstallation of third party library (Shantanu, PR [17420](https://github.com/python/mypy/pull/17420))

### Acknowledgements
Thanks to all mypy contributors who contributed to this release:

- Alex Waygood
- Ali Hamdan
- Edward Paget
- Evgeniy Slobodkin
- Hashem
- hesam
- Hugo van Kemenade
- Ihor
- James Braza
- Jelle Zijlstra
- jhance
- Jukka Lehtosalo
- Loïc Simon
- Marc Mueller
- Matthieu Devlin
- Michael R. Crusoe
- Nikita Sobolev
- Oskari Lehto
- Riccardo Di Maio
- Richard Si
- roberfi
- Roman Solomatin
- Sam Xifaras
- Shantanu
- Spencer Brown
- Srinivas Lade
- Tamir Duberstein
- youkaichao

I’d also like to thank my employer, Dropbox, for supporting mypy development.


## Mypy 1.9

We’ve just uploaded mypy 1.9 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Breaking Changes

Because the version of typeshed we use in mypy 1.9 doesn't support 3.7, neither does mypy 1.9. (Jared Hance, PR [16883](https://github.com/python/mypy/pull/16883))

We are planning to enable
[local partial types](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-local-partial-types) (enabled via the
`--local-partial-types` flag) later this year by default. This change
was announced years ago, but now it's finally happening. This is a
major backward-incompatible change, so we'll probably include it as
part of the upcoming mypy 2.0 release. This makes daemon and
non-daemon mypy runs have the same behavior by default.

Local partial types can also be enabled in the mypy config file:
```
local_partial_types = True
```

We are looking at providing a tool to make it easier to migrate
projects to use `--local-partial-types`, but it's not yet clear whether
this is practical. The migration usually involves adding some
explicit type annotations to module-level and class-level variables.

### Basic Support for Type Parameter Defaults (PEP 696)

This release contains new experimental support for type parameter
defaults ([PEP 696](https://peps.python.org/pep-0696)). Please try it
out! This feature was contributed by Marc Mueller.

Since this feature will be officially introduced in the next Python
feature release (3.13), you will need to import `TypeVar`, `ParamSpec`
or `TypeVarTuple` from `typing_extensions` to use defaults for now.

This example adapted from the PEP defines a default for `BotT`:
```python
from typing import Generic
from typing_extensions import TypeVar

class Bot: ...

BotT = TypeVar("BotT", bound=Bot, default=Bot)

class Context(Generic[BotT]):
    bot: BotT

class MyBot(Bot): ...

# type is Bot (the default)
reveal_type(Context().bot)
# type is MyBot
reveal_type(Context[MyBot]().bot)
```

### Type-checking Improvements
 * Fix missing type store for overloads (Marc Mueller, PR [16803](https://github.com/python/mypy/pull/16803))
 * Fix `'WriteToConn' object has no attribute 'flush'` (Charlie Denton, PR [16801](https://github.com/python/mypy/pull/16801))
 * Improve TypeAlias error messages (Marc Mueller, PR [16831](https://github.com/python/mypy/pull/16831))
 * Support narrowing unions that include `type[None]` (Christoph Tyralla, PR [16315](https://github.com/python/mypy/pull/16315))
 * Support TypedDict functional syntax as class base type (anniel-stripe, PR [16703](https://github.com/python/mypy/pull/16703))
 * Accept multiline quoted annotations (Shantanu, PR [16765](https://github.com/python/mypy/pull/16765))
 * Allow unary + in `Literal` (Jelle Zijlstra, PR [16729](https://github.com/python/mypy/pull/16729))
 * Substitute type variables in return type of static methods (Kouroche Bouchiat, PR [16670](https://github.com/python/mypy/pull/16670))
 * Consider TypeVarTuple to be invariant (Marc Mueller, PR [16759](https://github.com/python/mypy/pull/16759))
 * Add `alias` support to `field()` in `attrs` plugin (Nikita Sobolev, PR [16610](https://github.com/python/mypy/pull/16610))
 * Improve attrs hashability detection (Tin Tvrtković, PR [16556](https://github.com/python/mypy/pull/16556))

### Performance Improvements

 * Speed up finding function type variables (Jukka Lehtosalo, PR [16562](https://github.com/python/mypy/pull/16562))

### Documentation Updates

 * Document supported values for `--enable-incomplete-feature` in "mypy --help" (Froger David, PR [16661](https://github.com/python/mypy/pull/16661))
 * Update new type system discussion links (thomaswhaley, PR [16841](https://github.com/python/mypy/pull/16841))
 * Add missing class instantiation to cheat sheet (Aleksi Tarvainen, PR [16817](https://github.com/python/mypy/pull/16817))
 * Document how evil `--no-strict-optional` is (Shantanu, PR [16731](https://github.com/python/mypy/pull/16731))
 * Improve mypy daemon documentation note about local partial types (Makonnen Makonnen, PR [16782](https://github.com/python/mypy/pull/16782))
 * Fix numbering error (Stefanie Molin, PR [16838](https://github.com/python/mypy/pull/16838))
 * Various documentation improvements (Shantanu, PR [16836](https://github.com/python/mypy/pull/16836))

### Stubtest Improvements
 * Ignore private function/method parameters when they are missing from the stub (private parameter names start with a single underscore and have a default) (PR [16507](https://github.com/python/mypy/pull/16507))
 * Ignore a new protocol dunder (Alex Waygood, PR [16895](https://github.com/python/mypy/pull/16895))
 * Private parameters can be omitted (Sebastian Rittau, PR [16507](https://github.com/python/mypy/pull/16507))
 * Add support for setting enum members to "..." (Jelle Zijlstra, PR [16807](https://github.com/python/mypy/pull/16807))
 * Adjust symbol table logic (Shantanu, PR [16823](https://github.com/python/mypy/pull/16823))
 * Fix posisitional-only handling in overload resolution (Shantanu, PR [16750](https://github.com/python/mypy/pull/16750))

### Stubgen Improvements
 * Fix crash on star unpack of TypeVarTuple (Ali Hamdan, PR [16869](https://github.com/python/mypy/pull/16869))
 * Use PEP 604 unions everywhere (Ali Hamdan, PR [16519](https://github.com/python/mypy/pull/16519))
 * Do not ignore property deleter (Ali Hamdan, PR [16781](https://github.com/python/mypy/pull/16781))
 * Support type stub generation for `staticmethod` (WeilerMarcel, PR [14934](https://github.com/python/mypy/pull/14934))

### Acknowledgements

​Thanks to all mypy contributors who contributed to this release:

- Aleksi Tarvainen
- Alex Waygood
- Ali Hamdan
- anniel-stripe
- Charlie Denton
- Christoph Tyralla
- Dheeraj
- Fabian Keller
- Fabian Lewis
- Froger David
- Ihor
- Jared Hance
- Jelle Zijlstra
- Jukka Lehtosalo
- Kouroche Bouchiat
- Lukas Geiger
- Maarten Huijsmans
- Makonnen Makonnen
- Marc Mueller
- Nikita Sobolev
- Sebastian Rittau
- Shantanu
- Stefanie Molin
- Stephen Morton
- thomaswhaley
- Tin Tvrtković
- WeilerMarcel
- Wesley Collin Wright
- zipperer

I’d also like to thank my employer, Dropbox, for supporting mypy development.

## Mypy 1.8

We’ve just uploaded mypy 1.8 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Type-checking Improvements
 * Do not intersect types in isinstance checks if at least one is final (Christoph Tyralla, PR [16330](https://github.com/python/mypy/pull/16330))
 * Detect that `@final` class without `__bool__` cannot have falsey instances (Ilya Priven, PR [16566](https://github.com/python/mypy/pull/16566))
 * Do not allow `TypedDict` classes with extra keywords (Nikita Sobolev, PR [16438](https://github.com/python/mypy/pull/16438))
 * Do not allow class-level keywords for `NamedTuple` (Nikita Sobolev, PR [16526](https://github.com/python/mypy/pull/16526))
 * Make imprecise constraints handling more robust (Ivan Levkivskyi, PR [16502](https://github.com/python/mypy/pull/16502))
 * Fix strict-optional in extending generic TypedDict (Ivan Levkivskyi, PR [16398](https://github.com/python/mypy/pull/16398))
 * Allow type ignores of PEP 695 constructs (Shantanu, PR [16608](https://github.com/python/mypy/pull/16608))
 * Enable `type_check_only` support for `TypedDict` and `NamedTuple` (Nikita Sobolev, PR [16469](https://github.com/python/mypy/pull/16469))

### Performance Improvements
 * Add fast path to analyzing special form assignments (Jukka Lehtosalo, PR [16561](https://github.com/python/mypy/pull/16561))

### Improvements to Error Reporting
 * Don't show documentation links for plugin error codes (Ivan Levkivskyi, PR [16383](https://github.com/python/mypy/pull/16383))
 * Improve error messages for `super` checks and add more tests (Nikita Sobolev, PR [16393](https://github.com/python/mypy/pull/16393))
 * Add error code for mutable covariant override (Ivan Levkivskyi, PR [16399](https://github.com/python/mypy/pull/16399))

### Stubgen Improvements
 * Preserve simple defaults in function signatures (Ali Hamdan, PR [15355](https://github.com/python/mypy/pull/15355))
 * Include `__all__` in output (Jelle Zijlstra, PR [16356](https://github.com/python/mypy/pull/16356))
 * Fix stubgen regressions with pybind11 and mypy 1.7 (Chad Dombrova, PR [16504](https://github.com/python/mypy/pull/16504))

### Stubtest Improvements
 * Improve handling of unrepresentable defaults (Jelle Zijlstra, PR [16433](https://github.com/python/mypy/pull/16433))
 * Print more helpful errors if a function is missing from stub (Alex Waygood, PR [16517](https://github.com/python/mypy/pull/16517))
 * Support `@type_check_only` decorator (Nikita Sobolev, PR [16422](https://github.com/python/mypy/pull/16422))
 * Warn about missing `__del__` (Shantanu, PR [16456](https://github.com/python/mypy/pull/16456))
 * Fix crashes with some uses of `final` and `deprecated` (Shantanu, PR [16457](https://github.com/python/mypy/pull/16457))

### Fixes to Crashes
 * Fix crash with type alias to `Callable[[Unpack[Tuple[Any, ...]]], Any]` (Alex Waygood, PR [16541](https://github.com/python/mypy/pull/16541))
 * Fix crash on TypeGuard in `__call__` (Ivan Levkivskyi, PR [16516](https://github.com/python/mypy/pull/16516))
 * Fix crash on invalid enum in method (Ivan Levkivskyi, PR [16511](https://github.com/python/mypy/pull/16511))
 * Fix crash on unimported Any in TypedDict (Ivan Levkivskyi, PR [16510](https://github.com/python/mypy/pull/16510))

### Documentation Updates
 * Update soft-error-limit default value to -1 (Sveinung Gundersen, PR [16542](https://github.com/python/mypy/pull/16542))
 * Support Sphinx 7.x (Michael R. Crusoe, PR [16460](https://github.com/python/mypy/pull/16460))

### Other Notable Changes and Fixes
 * Allow mypy to output a junit file with per-file results (Matthew Wright, PR [16388](https://github.com/python/mypy/pull/16388))

### Typeshed Updates

Please see [git log](https://github.com/python/typeshed/commits/main?after=4a854366e03dee700109f8e758a08b2457ea2f51+0&branch=main&path=stdlib) for full list of standard library typeshed stub changes.

### Acknowledgements

​Thanks to all mypy contributors who contributed to this release:

- Alex Waygood
- Ali Hamdan
- Chad Dombrova
- Christoph Tyralla
- Ilya Priven
- Ivan Levkivskyi
- Jelle Zijlstra
- Jukka Lehtosalo
- Marcel Telka
- Matthew Wright
- Michael R. Crusoe
- Nikita Sobolev
- Ole Peder Brandtzæg
- robjhornby
- Shantanu
- Sveinung Gundersen
- Valentin Stanciu

I’d also like to thank my employer, Dropbox, for supporting mypy development.

Posted by Wesley Collin Wright

## Mypy 1.7

We’ve just uploaded mypy 1.7 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Using TypedDict for `**kwargs` Typing

Mypy now has support for using `Unpack[...]` with a TypedDict type to annotate `**kwargs` arguments enabled by default. Example:

```python
# Or 'from typing_extensions import ...'
from typing import TypedDict, Unpack

class Person(TypedDict):
    name: str
    age: int

def foo(**kwargs: Unpack[Person]) -> None:
    ...

foo(name="x", age=1)  # Ok
foo(name=1)  # Error
```

The definition of `foo` above is equivalent to the one below, with keyword-only arguments `name` and `age`:

```python
def foo(*, name: str, age: int) -> None:
    ...
```

Refer to [PEP 692](https://peps.python.org/pep-0692/) for more information. Note that unlike in the current version of the PEP, mypy always treats signatures with `Unpack[SomeTypedDict]` as equivalent to their expanded forms with explicit keyword arguments, and there aren't special type checking rules for TypedDict arguments.

This was contributed by Ivan Levkivskyi back in 2022 (PR [13471](https://github.com/python/mypy/pull/13471)).

### TypeVarTuple Support Enabled (Experimental)

Mypy now has support for variadic generics (TypeVarTuple) enabled by default, as an experimental feature. Refer to [PEP 646](https://peps.python.org/pep-0646/) for the details.

TypeVarTuple was implemented by Jared Hance and Ivan Levkivskyi over several mypy releases, with help from Jukka Lehtosalo.

Changes included in this release:

 * Fix handling of tuple type context with unpacks (Ivan Levkivskyi, PR [16444](https://github.com/python/mypy/pull/16444))
 * Handle TypeVarTuples when checking overload constraints (robjhornby, PR [16428](https://github.com/python/mypy/pull/16428))
 * Enable Unpack/TypeVarTuple support (Ivan Levkivskyi, PR [16354](https://github.com/python/mypy/pull/16354))
 * Fix crash on unpack call special-casing (Ivan Levkivskyi, PR [16381](https://github.com/python/mypy/pull/16381))
 * Some final touches for variadic types support (Ivan Levkivskyi, PR [16334](https://github.com/python/mypy/pull/16334))
 * Support PEP-646 and PEP-692 in the same callable (Ivan Levkivskyi, PR [16294](https://github.com/python/mypy/pull/16294))
 * Support new `*` syntax for variadic types (Ivan Levkivskyi, PR [16242](https://github.com/python/mypy/pull/16242))
 * Correctly handle variadic instances with empty arguments (Ivan Levkivskyi, PR [16238](https://github.com/python/mypy/pull/16238))
 * Correctly handle runtime type applications of variadic types (Ivan Levkivskyi, PR [16240](https://github.com/python/mypy/pull/16240))
 * Support variadic tuple packing/unpacking (Ivan Levkivskyi, PR [16205](https://github.com/python/mypy/pull/16205))
 * Better support for variadic calls and indexing (Ivan Levkivskyi, PR [16131](https://github.com/python/mypy/pull/16131))
 * Subtyping and inference of user-defined variadic types (Ivan Levkivskyi, PR [16076](https://github.com/python/mypy/pull/16076))
 * Complete type analysis of variadic types (Ivan Levkivskyi, PR [15991](https://github.com/python/mypy/pull/15991))

### New Way of Installing Mypyc Dependencies

If you want to install package dependencies needed by mypyc (not just mypy), you should now install `mypy[mypyc]` instead of just `mypy`:

```
python3 -m pip install -U 'mypy[mypyc]'
```

Mypy has many more users than mypyc, so always installing mypyc dependencies would often bring unnecessary dependencies.

This change was contributed by Shantanu (PR [16229](https://github.com/python/mypy/pull/16229)).

### New Rules for Re-exports

Mypy no longer considers an import such as `import a.b as b` as an explicit re-export. The old behavior was arguably inconsistent and surprising. This may impact some stub packages, such as older versions of `types-six`. You can change the import to `from a import b as b`, if treating the import as a re-export was intentional.

This change was contributed by Anders Kaseorg (PR [14086](https://github.com/python/mypy/pull/14086)).

### Improved Type Inference

The new type inference algorithm that was recently introduced to mypy (but was not enabled by default) is now enabled by default. It improves type inference of calls to generic callables where an argument is also a generic callable, in particular. You can use `--old-type-inference` to disable the new behavior.

The new algorithm can (rarely) produce different error messages, different error codes, or errors reported on different lines. This is more likely in cases where generic types were used incorrectly.

The new type inference algorithm was contributed by Ivan Levkivskyi. PR [16345](https://github.com/python/mypy/pull/16345) enabled it by default.

### Narrowing Tuple Types Using len()

Mypy now can narrow tuple types using `len()` checks. Example:

```python
def f(t: tuple[int, int] | tuple[int, int, int]) -> None:
    if len(t) == 2:
        a, b = t   # Ok
    ...
```

This feature was contributed by Ivan Levkivskyi (PR [16237](https://github.com/python/mypy/pull/16237)).

### More Precise Tuple Lengths (Experimental)

Mypy supports experimental, more precise checking of tuple type lengths through `--enable-incomplete-feature=PreciseTupleTypes`. Refer to the [documentation](https://mypy.readthedocs.io/en/latest/command_line.html#enabling-incomplete-experimental-features) for more information.

More generally, we are planning to use `--enable-incomplete-feature` to introduce experimental features that would benefit from community feedback.

This feature was contributed by Ivan Levkivskyi (PR [16237](https://github.com/python/mypy/pull/16237)).

### Mypy Changelog

We now maintain a [changelog](https://github.com/python/mypy/blob/master/CHANGELOG.md) in the mypy Git repository. It mirrors the contents of [mypy release blog posts](https://mypy-lang.blogspot.com/). We will continue to also publish release blog posts. In the future, release blog posts will be created based on the changelog near a release date.

This was contributed by Shantanu (PR [16280](https://github.com/python/mypy/pull/16280)).

### Mypy Daemon Improvements

 * Fix daemon crash caused by deleted submodule (Jukka Lehtosalo, PR [16370](https://github.com/python/mypy/pull/16370))
 * Fix file reloading in dmypy with --export-types (Ivan Levkivskyi, PR [16359](https://github.com/python/mypy/pull/16359))
 * Fix dmypy inspect on Windows (Ivan Levkivskyi, PR [16355](https://github.com/python/mypy/pull/16355))
 * Fix dmypy inspect for namespace packages (Ivan Levkivskyi, PR [16357](https://github.com/python/mypy/pull/16357))
 * Fix return type change to optional in generic function (Jukka Lehtosalo, PR [16342](https://github.com/python/mypy/pull/16342))
 * Fix daemon false positives related to module-level `__getattr__` (Jukka Lehtosalo, PR [16292](https://github.com/python/mypy/pull/16292))
 * Fix daemon crash related to ABCs (Jukka Lehtosalo, PR [16275](https://github.com/python/mypy/pull/16275))
 * Stream dmypy output instead of dumping everything at the end (Valentin Stanciu, PR [16252](https://github.com/python/mypy/pull/16252))
 * Make sure all dmypy errors are shown (Valentin Stanciu, PR [16250](https://github.com/python/mypy/pull/16250))

### Mypyc Improvements

 * Generate error on duplicate function definitions (Jukka Lehtosalo, PR [16309](https://github.com/python/mypy/pull/16309))
 * Don't crash on unreachable statements (Jukka Lehtosalo, PR [16311](https://github.com/python/mypy/pull/16311))
 * Avoid cyclic reference in nested functions (Jukka Lehtosalo, PR [16268](https://github.com/python/mypy/pull/16268))
 * Fix direct `__dict__` access on inner functions in new Python (Shantanu, PR [16084](https://github.com/python/mypy/pull/16084))
 * Make tuple packing and unpacking more efficient (Jukka Lehtosalo, PR [16022](https://github.com/python/mypy/pull/16022))

### Improvements to Error Reporting

 * Update starred expression error message to match CPython (Cibin Mathew, PR [16304](https://github.com/python/mypy/pull/16304))
 * Fix error code of "Maybe you forgot to use await" note (Jelle Zijlstra, PR [16203](https://github.com/python/mypy/pull/16203))
 * Use error code `[unsafe-overload]` for unsafe overloads, instead of `[misc]` (Randolf Scholz, PR [16061](https://github.com/python/mypy/pull/16061))
 * Reword the error message related to void functions (Albert Tugushev, PR [15876](https://github.com/python/mypy/pull/15876))
 * Represent bottom type as Never in messages (Shantanu, PR [15996](https://github.com/python/mypy/pull/15996))
 * Add hint for AsyncIterator incompatible return type (Ilya Priven, PR [15883](https://github.com/python/mypy/pull/15883))
 * Don't suggest stubs packages where the runtime package now ships with types (Alex Waygood, PR [16226](https://github.com/python/mypy/pull/16226))

### Performance Improvements

 * Speed up type argument checking (Jukka Lehtosalo, PR [16353](https://github.com/python/mypy/pull/16353))
 * Add fast path for checking self types (Jukka Lehtosalo, PR [16352](https://github.com/python/mypy/pull/16352))
 * Cache information about whether file is typeshed file (Jukka Lehtosalo, PR [16351](https://github.com/python/mypy/pull/16351))
 * Skip expensive `repr()` in logging call when not needed (Jukka Lehtosalo, PR [16350](https://github.com/python/mypy/pull/16350))

### Attrs and Dataclass Improvements

 * `dataclass.replace`: Allow transformed classes (Ilya Priven, PR [15915](https://github.com/python/mypy/pull/15915))
 * `dataclass.replace`: Fall through to typeshed signature (Ilya Priven, PR [15962](https://github.com/python/mypy/pull/15962))
 * Document `dataclass_transform` behavior (Ilya Priven, PR [16017](https://github.com/python/mypy/pull/16017))
 * `attrs`: Remove fields type check (Ilya Priven, PR [15983](https://github.com/python/mypy/pull/15983))
 * `attrs`, `dataclasses`: Don't enforce slots when base class doesn't (Ilya Priven, PR [15976](https://github.com/python/mypy/pull/15976))
 * Fix crash on dataclass field / property collision (Nikita Sobolev, PR [16147](https://github.com/python/mypy/pull/16147))

### Stubgen Improvements

 * Write stubs with utf-8 encoding (Jørgen Lind, PR [16329](https://github.com/python/mypy/pull/16329))
 * Fix missing property setter in semantic analysis mode (Ali Hamdan, PR [16303](https://github.com/python/mypy/pull/16303))
 * Unify C extension and pure python stub generators with object oriented design (Chad Dombrova, PR [15770](https://github.com/python/mypy/pull/15770))
 * Multiple fixes to the generated imports (Ali Hamdan, PR [15624](https://github.com/python/mypy/pull/15624))
 * Generate valid dataclass stubs (Ali Hamdan, PR [15625](https://github.com/python/mypy/pull/15625))

### Fixes to Crashes

 * Fix incremental mode crash on TypedDict in method (Ivan Levkivskyi, PR [16364](https://github.com/python/mypy/pull/16364))
 * Fix crash on star unpack in TypedDict (Ivan Levkivskyi, PR [16116](https://github.com/python/mypy/pull/16116))
 * Fix crash on malformed TypedDict in incremental mode (Ivan Levkivskyi, PR [16115](https://github.com/python/mypy/pull/16115))
 * Fix crash with report generation on namespace packages (Shantanu, PR [16019](https://github.com/python/mypy/pull/16019))
 * Fix crash when parsing error code config with typo (Shantanu, PR [16005](https://github.com/python/mypy/pull/16005))
 * Fix `__post_init__()` internal error (Ilya Priven, PR [16080](https://github.com/python/mypy/pull/16080))

### Documentation Updates

 * Make it easier to copy commands from README (Hamir Mahal, PR [16133](https://github.com/python/mypy/pull/16133))
 * Document and rename `[overload-overlap]` error code (Shantanu, PR [16074](https://github.com/python/mypy/pull/16074))
 * Document `--force-uppercase-builtins` and `--force-union-syntax` (Nikita Sobolev, PR [16049](https://github.com/python/mypy/pull/16049))
 * Document `force_union_syntax` and `force_uppercase_builtins` (Nikita Sobolev, PR [16048](https://github.com/python/mypy/pull/16048))
 * Document we're not tracking relationships between symbols (Ilya Priven, PR [16018](https://github.com/python/mypy/pull/16018))

### Other Notable Changes and Fixes

 * Propagate narrowed types to lambda expressions (Ivan Levkivskyi, PR [16407](https://github.com/python/mypy/pull/16407))
 * Avoid importing from `setuptools._distutils` (Shantanu, PR [16348](https://github.com/python/mypy/pull/16348))
 * Delete recursive aliases flags (Ivan Levkivskyi, PR [16346](https://github.com/python/mypy/pull/16346))
 * Properly use proper subtyping for callables (Ivan Levkivskyi, PR [16343](https://github.com/python/mypy/pull/16343))
 * Use upper bound as inference fallback more consistently (Ivan Levkivskyi, PR [16344](https://github.com/python/mypy/pull/16344))
 * Add `[unimported-reveal]` error code (Nikita Sobolev, PR [16271](https://github.com/python/mypy/pull/16271))
 * Add `|=` and `|` operators support for `TypedDict` (Nikita Sobolev, PR [16249](https://github.com/python/mypy/pull/16249))
 * Clarify variance convention for Parameters (Ivan Levkivskyi, PR [16302](https://github.com/python/mypy/pull/16302))
 * Correctly recognize `typing_extensions.NewType` (Ganden Schaffner, PR [16298](https://github.com/python/mypy/pull/16298))
 * Fix partially defined in the case of missing type maps (Shantanu, PR [15995](https://github.com/python/mypy/pull/15995))
 * Use SPDX license identifier (Nikita Sobolev, PR [16230](https://github.com/python/mypy/pull/16230))
 * Make `__qualname__` and `__module__` available in class bodies (Anthony Sottile, PR [16215](https://github.com/python/mypy/pull/16215))
 * stubtest: Hint when args in stub need to be keyword-only (Alex Waygood, PR [16210](https://github.com/python/mypy/pull/16210))
 * Tuple slice should not propagate fallback (Thomas Grainger, PR [16154](https://github.com/python/mypy/pull/16154))
 * Fix cases of type object handling for overloads (Shantanu, PR [16168](https://github.com/python/mypy/pull/16168))
 * Fix walrus interaction with empty collections (Ivan Levkivskyi, PR [16197](https://github.com/python/mypy/pull/16197))
 * Use type variable bound when it appears as actual during inference (Ivan Levkivskyi, PR [16178](https://github.com/python/mypy/pull/16178))
 * Use upper bounds as fallback solutions for inference (Ivan Levkivskyi, PR [16184](https://github.com/python/mypy/pull/16184))
 * Special-case type inference of empty collections (Ivan Levkivskyi, PR [16122](https://github.com/python/mypy/pull/16122))
 * Allow TypedDict unpacking in Callable types (Ivan Levkivskyi, PR [16083](https://github.com/python/mypy/pull/16083))
 * Fix inference for overloaded `__call__` with generic self (Shantanu, PR [16053](https://github.com/python/mypy/pull/16053))
 * Call dynamic class hook on generic classes (Petter Friberg, PR [16052](https://github.com/python/mypy/pull/16052))
 * Preserve implicitly exported types via attribute access (Shantanu, PR [16129](https://github.com/python/mypy/pull/16129))
 * Fix a stubtest bug (Alex Waygood)
 * Fix `tuple[Any, ...]` subtyping (Shantanu, PR [16108](https://github.com/python/mypy/pull/16108))
 * Lenient handling of trivial Callable suffixes (Ivan Levkivskyi, PR [15913](https://github.com/python/mypy/pull/15913))
 * Add `add_overloaded_method_to_class` helper for plugins (Nikita Sobolev, PR [16038](https://github.com/python/mypy/pull/16038))
 * Bundle `misc/proper_plugin.py` as a part of `mypy` (Nikita Sobolev, PR [16036](https://github.com/python/mypy/pull/16036))
 * Fix `case Any()` in match statement (DS/Charlie, PR [14479](https://github.com/python/mypy/pull/14479))
 * Make iterable logic more consistent (Shantanu, PR [16006](https://github.com/python/mypy/pull/16006))
 * Fix inference for properties with `__call__` (Shantanu, PR [15926](https://github.com/python/mypy/pull/15926))

### Typeshed Updates

Please see [git log](https://github.com/python/typeshed/commits/main?after=4a854366e03dee700109f8e758a08b2457ea2f51+0&branch=main&path=stdlib) for full list of standard library typeshed stub changes.

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

* Albert Tugushev
* Alex Waygood
* Ali Hamdan
* Anders Kaseorg
* Anthony Sottile
* Chad Dombrova
* Cibin Mathew
* dinaldoap
* DS/Charlie
* Eli Schwartz
* Ganden Schaffner
* Hamir Mahal
* Ihor
* Ikko Eltociear Ashimine
* Ilya Priven
* Ivan Levkivskyi
* Jelle Zijlstra
* Jukka Lehtosalo
* Jørgen Lind
* KotlinIsland
* Matt Bogosian
* Nikita Sobolev
* Petter Friberg
* Randolf Scholz
* Shantanu
* Thomas Grainger
* Valentin Stanciu

I’d also like to thank my employer, Dropbox, for supporting mypy development.

Posted by Jukka Lehtosalo

## Mypy 1.6

[Tuesday, 10 October 2023](https://mypy-lang.blogspot.com/2023/10/mypy-16-released.html)

We’ve just uploaded mypy 1.6 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Introduce Error Subcodes for Import Errors

Mypy now uses the error code import-untyped if an import targets an installed library that doesn’t support static type checking, and no stub files are available. Other invalid imports produce the import-not-found error code. They both are subcodes of the import error code, which was previously used for both kinds of import-related errors.

Use \--disable-error-code=import-untyped to only ignore import errors about installed libraries without stubs. This way mypy will still report errors about typos in import statements, for example.

If you use \--warn-unused-ignore or \--strict, mypy will complain if you use \# type: ignore\[import\] to ignore an import error. You are expected to use one of the more specific error codes instead. Otherwise, ignoring the import error code continues to silence both errors.

This feature was contributed by Shantanu (PR [15840](https://github.com/python/mypy/pull/15840), PR [14740](https://github.com/python/mypy/pull/14740)).

### Remove Support for Targeting Python 3.6 and Earlier

Running mypy with \--python-version 3.6, for example, is no longer supported. Python 3.6 hasn’t been properly supported by mypy for some time now, and this makes it explicit. This was contributed by Nikita Sobolev (PR [15668](https://github.com/python/mypy/pull/15668)).

### Selective Filtering of \--disallow-untyped-calls Targets

Using \--disallow-untyped-calls could be annoying when using libraries with missing type information, as mypy would generate many errors about code that uses the library. Now you can use \--untyped-calls-exclude=acme, for example, to disable these errors about calls targeting functions defined in the acme package. Refer to the [documentation](https://mypy.readthedocs.io/en/latest/command_line.html#cmdoption-mypy-untyped-calls-exclude) for more information.

This feature was contributed by Ivan Levkivskyi (PR [15845](https://github.com/python/mypy/pull/15845)).

### Improved Type Inference between Callable Types

Mypy now does a better job inferring type variables inside arguments of callable types. For example, this code fragment now type checks correctly:

```python
def f(c: Callable[[T, S], None]) -> Callable[[str, T, S], None]: ...
def g(*x: int) -> None: ...

reveal_type(f(g))  # Callable[[str, int, int], None]
```

This was contributed by Ivan Levkivskyi (PR [15910](https://github.com/python/mypy/pull/15910)).

### Don’t Consider None and TypeVar to Overlap in Overloads

Mypy now doesn’t consider an overload item with an argument type None to overlap with a type variable:

```python
@overload
def f(x: None) -> None: ..
@overload
def f(x: T) -> Foo[T]: ...
...
```

Previously mypy would generate an error about the definition of f above. This is slightly unsafe if the upper bound of T is object, since the value of the type variable could be None. We relaxed the rules a little, since this solves a common issue.

This feature was contributed by Ivan Levkivskyi (PR [15846](https://github.com/python/mypy/pull/15846)).

### Improvements to \--new-type-inference

The experimental new type inference algorithm (polymorphic inference) introduced as an opt-in feature in mypy 1.5 has several improvements:

*   Improve transitive closure computation during constraint solving (Ivan Levkivskyi, PR [15754](https://github.com/python/mypy/pull/15754))
*   Add support for upper bounds and values with \--new-type-inference (Ivan Levkivskyi, PR [15813](https://github.com/python/mypy/pull/15813))
*   Basic support for variadic types with \--new-type-inference (Ivan Levkivskyi, PR [15879](https://github.com/python/mypy/pull/15879))
*   Polymorphic inference: support for parameter specifications and lambdas (Ivan Levkivskyi, PR [15837](https://github.com/python/mypy/pull/15837))
*   Invalidate cache when adding \--new-type-inference (Marc Mueller, PR [16059](https://github.com/python/mypy/pull/16059))

**Note:** We are planning to enable \--new-type-inference by default in mypy 1.7. Please try this out and let us know if you encounter any issues.

### ParamSpec Improvements

*   Support self-types containing ParamSpec (Ivan Levkivskyi, PR [15903](https://github.com/python/mypy/pull/15903))
*   Allow “…” in Concatenate, and clean up ParamSpec literals (Ivan Levkivskyi, PR [15905](https://github.com/python/mypy/pull/15905))
*   Fix ParamSpec inference for callback protocols (Ivan Levkivskyi, PR [15986](https://github.com/python/mypy/pull/15986))
*   Infer ParamSpec constraint from arguments (Ivan Levkivskyi, PR [15896](https://github.com/python/mypy/pull/15896))
*   Fix crash on invalid type variable with ParamSpec (Ivan Levkivskyi, PR [15953](https://github.com/python/mypy/pull/15953))
*   Fix subtyping between ParamSpecs (Ivan Levkivskyi, PR [15892](https://github.com/python/mypy/pull/15892))

### Stubgen Improvements

*   Add option to include docstrings with stubgen (chylek, PR [13284](https://github.com/python/mypy/pull/13284))
*   Add required ... initializer to NamedTuple fields with default values (Nikita Sobolev, PR [15680](https://github.com/python/mypy/pull/15680))

### Stubtest Improvements

*   Fix \_\_mypy-replace false positives (Alex Waygood, PR [15689](https://github.com/python/mypy/pull/15689))
*   Fix edge case for bytes enum subclasses (Alex Waygood, PR [15943](https://github.com/python/mypy/pull/15943))
*   Generate error if typeshed is missing modules from the stdlib (Alex Waygood, PR [15729](https://github.com/python/mypy/pull/15729))
*   Fixes to new check for missing stdlib modules (Alex Waygood, PR [15960](https://github.com/python/mypy/pull/15960))
*   Fix stubtest enum.Flag edge case (Alex Waygood, PR [15933](https://github.com/python/mypy/pull/15933))

### Documentation Improvements

*   Do not advertise to create your own assert\_never helper (Nikita Sobolev, PR [15947](https://github.com/python/mypy/pull/15947))
*   Fix all the missing references found within the docs (Albert Tugushev, PR [15875](https://github.com/python/mypy/pull/15875))
*   Document await-not-async error code (Shantanu, PR [15858](https://github.com/python/mypy/pull/15858))
*   Improve documentation of disabling error codes (Shantanu, PR [15841](https://github.com/python/mypy/pull/15841))

### Other Notable Changes and Fixes

*   Make unsupported PEP 695 features (introduced in Python 3.12) give a reasonable error message (Shantanu, PR [16013](https://github.com/python/mypy/pull/16013))
*   Remove the \--py2 command-line argument (Marc Mueller, PR [15670](https://github.com/python/mypy/pull/15670))
*   Change empty tuple from tuple\[\] to tuple\[()\] in error messages (Nikita Sobolev, PR [15783](https://github.com/python/mypy/pull/15783))
*   Fix assert\_type failures when some nodes are deferred (Nikita Sobolev, PR [15920](https://github.com/python/mypy/pull/15920))
*   Generate error on unbound TypeVar with values (Nikita Sobolev, PR [15732](https://github.com/python/mypy/pull/15732))
*   Fix over-eager types-google-cloud-ndb suggestion (Shantanu, PR [15347](https://github.com/python/mypy/pull/15347))
*   Fix type narrowing of \== None and in (None,) conditions (Marti Raudsepp, PR [15760](https://github.com/python/mypy/pull/15760))
*   Fix inference for attrs.fields (Shantanu, PR [15688](https://github.com/python/mypy/pull/15688))
*   Make “await in non-async function” a non-blocking error and give it an error code (Gregory Santosa, PR [15384](https://github.com/python/mypy/pull/15384))
*   Add basic support for decorated overloads (Ivan Levkivskyi, PR [15898](https://github.com/python/mypy/pull/15898))
*   Fix TypeVar regression with self types (Ivan Levkivskyi, PR [15945](https://github.com/python/mypy/pull/15945))
*   Add \_\_match\_args\_\_ to dataclasses with no fields (Ali Hamdan, PR [15749](https://github.com/python/mypy/pull/15749))
*   Include stdout and stderr in dmypy verbose output (Valentin Stanciu, PR [15881](https://github.com/python/mypy/pull/15881))
*   Improve match narrowing and reachability analysis (Shantanu, PR [15882](https://github.com/python/mypy/pull/15882))
*   Support \_\_bool\_\_ with Literal in \--warn-unreachable (Jannic Warken, PR [15645](https://github.com/python/mypy/pull/15645))
*   Fix inheriting from generic @frozen attrs class (Ilya Priven, PR [15700](https://github.com/python/mypy/pull/15700))
*   Correctly narrow types for tuple\[type\[X\], ...\] (Nikita Sobolev, PR [15691](https://github.com/python/mypy/pull/15691))
*   Don't flag intentionally empty generators unreachable (Ilya Priven, PR [15722](https://github.com/python/mypy/pull/15722))
*   Add tox.ini to mypy sdist (Marcel Telka, PR [15853](https://github.com/python/mypy/pull/15853))
*   Fix mypyc regression with pretty (Shantanu, PR [16124](https://github.com/python/mypy/pull/16124))

### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=6a8d653a671925b0a3af61729ff8cf3f90c9c662+0&branch=main&path=stdlib) for full list of typeshed changes.

### Acknowledgements

Thanks to Max Murin, who did most of the release manager work for this release (I just did the final steps).

Thanks to all mypy contributors who contributed to this release:

*   Albert Tugushev
*   Alex Waygood
*   Ali Hamdan
*   chylek
*   EXPLOSION
*   Gregory Santosa
*   Ilya Priven
*   Ivan Levkivskyi
*   Jannic Warken
*   KotlinIsland
*   Marc Mueller
*   Marcel Johannesmann
*   Marcel Telka
*   Mark Byrne
*   Marti Raudsepp
*   Max Murin
*   Nikita Sobolev
*   Shantanu
*   Valentin Stanciu

Posted by Jukka Lehtosalo


## Mypy 1.5

[Thursday, 10 August 2023](https://mypy-lang.blogspot.com/2023/08/mypy-15-released.html)

We’ve just uploaded mypy 1.5 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, deprecations and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Drop Support for Python 3.7

Mypy no longer supports running with Python 3.7, which has reached end-of-life. This was contributed by Shantanu (PR [15566](https://github.com/python/mypy/pull/15566)).

### Optional Check to Require Explicit @override

If you enable the explicit-override error code, mypy will generate an error if a method override doesn’t use the @typing.override decorator (as discussed in [PEP 698](https://peps.python.org/pep-0698/#strict-enforcement-per-project)). This way mypy will detect accidentally introduced overrides. Example:

```python
# mypy: enable-error-code="explicit-override"

from typing_extensions import override

class C:
    def foo(self) -> None: pass
    def bar(self) -> None: pass

class D(C):
    # Error: Method "foo" is not using @override but is
    # overriding a method
    def foo(self) -> None:
        ...

    @override
    def bar(self) -> None:  # OK
        ...
```

You can enable the error code via \--enable-error-code=explicit-override on the mypy command line or enable\_error\_code = explicit-override in the mypy config file.

The override decorator will be available in typing in Python 3.12, but you can also use the backport from a recent version of `typing_extensions` on all supported Python versions.

This feature was contributed by Marc Mueller(PR [15512](https://github.com/python/mypy/pull/15512)).

### More Flexible TypedDict Creation and Update

Mypy was previously overly strict when type checking TypedDict creation and update operations. Though these checks were often technically correct, they sometimes triggered for apparently valid code. These checks have now been relaxed by default. You can enable stricter checking by using the new \--extra-checks flag.

Construction using the `**` syntax is now more flexible:

```python
from typing import TypedDict

class A(TypedDict):
    foo: int
    bar: int

class B(TypedDict):
    foo: int

a: A = {"foo": 1, "bar": 2}
b: B = {"foo": 3}
a2: A = { **a, **b}  # OK (previously an error)
```

You can also call update() with a TypedDict argument that contains a subset of the keys in the updated TypedDict:
```python
a.update(b)  # OK (previously an error)
```

This feature was contributed by Ivan Levkivskyi (PR [15425](https://github.com/python/mypy/pull/15425)).

### Deprecated Flag: \--strict-concatenate

The behavior of \--strict-concatenate is now included in the new \--extra-checks flag, and the old flag is deprecated.

### Optionally Show Links to Error Code Documentation

If you use \--show-error-code-links, mypy will add documentation links to (many) reported errors. The links are not shown for error messages that are sufficiently obvious, and they are shown once per error code only.

Example output:
```
a.py:1: error: Need type annotation for "foo" (hint: "x: List[<type>] = ...")  [var-annotated]
a.py:1: note: See https://mypy.rtfd.io/en/stable/_refs.html#code-var-annotated for more info
```
This was contributed by Ivan Levkivskyi (PR [15449](https://github.com/python/mypy/pull/15449)).

### Consistently Avoid Type Checking Unreachable Code

If a module top level has unreachable code, mypy won’t type check the unreachable statements. This is consistent with how functions behave. The behavior of \--warn-unreachable is also more consistent now.

This was contributed by Ilya Priven (PR [15386](https://github.com/python/mypy/pull/15386)).

### Experimental Improved Type Inference for Generic Functions

You can use \--new-type-inference to opt into an experimental new type inference algorithm. It fixes issues when calling a generic functions with an argument that is also a generic function, in particular. This current implementation is still incomplete, but we encourage trying it out and reporting bugs if you encounter regressions. We are planning to enable the new algorithm by default in a future mypy release.

This feature was contributed by Ivan Levkivskyi (PR [15287](https://github.com/python/mypy/pull/15287)).

### Partial Support for Python 3.12

Mypy and mypyc now support running on recent Python 3.12 development versions. Not all new Python 3.12 features are supported, and we don’t ship compiled wheels for Python 3.12 yet.

*   Fix ast warnings for Python 3.12 (Nikita Sobolev, PR [15558](https://github.com/python/mypy/pull/15558))
*   mypyc: Fix multiple inheritance with a protocol on Python 3.12 (Jukka Lehtosalo, PR [15572](https://github.com/python/mypy/pull/15572))
*   mypyc: Fix self-compilation on Python 3.12 (Jukka Lehtosalo, PR [15582](https://github.com/python/mypy/pull/15582))
*   mypyc: Fix 3.12 issue with pickling of instances with \_\_dict\_\_ (Jukka Lehtosalo, PR [15574](https://github.com/python/mypy/pull/15574))
*   mypyc: Fix i16 on Python 3.12 (Jukka Lehtosalo, PR [15510](https://github.com/python/mypy/pull/15510))
*   mypyc: Fix int operations on Python 3.12 (Jukka Lehtosalo, PR [15470](https://github.com/python/mypy/pull/15470))
*   mypyc: Fix generators on Python 3.12 (Jukka Lehtosalo, PR [15472](https://github.com/python/mypy/pull/15472))
*   mypyc: Fix classes with \_\_dict\_\_ on 3.12 (Jukka Lehtosalo, PR [15471](https://github.com/python/mypy/pull/15471))
*   mypyc: Fix coroutines on Python 3.12 (Jukka Lehtosalo, PR [15469](https://github.com/python/mypy/pull/15469))
*   mypyc: Don't use \_PyErr\_ChainExceptions on 3.12, since it's deprecated (Jukka Lehtosalo, PR [15468](https://github.com/python/mypy/pull/15468))
*   mypyc: Add Python 3.12 feature macro (Jukka Lehtosalo, PR [15465](https://github.com/python/mypy/pull/15465))

### Improvements to Dataclasses

*   Improve signature of dataclasses.replace (Ilya Priven, PR [14849](https://github.com/python/mypy/pull/14849))
*   Fix dataclass/protocol crash on joining types (Ilya Priven, PR [15629](https://github.com/python/mypy/pull/15629))
*   Fix strict optional handling in dataclasses (Ivan Levkivskyi, PR [15571](https://github.com/python/mypy/pull/15571))
*   Support optional types for custom dataclass descriptors (Marc Mueller, PR [15628](https://github.com/python/mypy/pull/15628))
*   Add `__slots__` attribute to dataclasses (Nikita Sobolev, PR [15649](https://github.com/python/mypy/pull/15649))
*   Support better \_\_post\_init\_\_ method signature for dataclasses (Nikita Sobolev, PR [15503](https://github.com/python/mypy/pull/15503))

### Mypyc Improvements

*   Support unsigned 8-bit native integer type: mypy\_extensions.u8 (Jukka Lehtosalo, PR [15564](https://github.com/python/mypy/pull/15564))
*   Support signed 16-bit native integer type: mypy\_extensions.i16 (Jukka Lehtosalo, PR [15464](https://github.com/python/mypy/pull/15464))
*   Define mypy\_extensions.i16 in stubs (Jukka Lehtosalo, PR [15562](https://github.com/python/mypy/pull/15562))
*   Document more unsupported features and update supported features (Richard Si, PR [15524](https://github.com/python/mypy/pull/15524))
*   Fix final NamedTuple classes (Richard Si, PR [15513](https://github.com/python/mypy/pull/15513))
*   Use C99 compound literals for undefined tuple values (Jukka Lehtosalo, PR [15453](https://github.com/python/mypy/pull/15453))
*   Don't explicitly assign NULL values in setup functions (Logan Hunt, PR [15379](https://github.com/python/mypy/pull/15379))

### Stubgen Improvements

*   Teach stubgen to work with complex and unary expressions (Nikita Sobolev, PR [15661](https://github.com/python/mypy/pull/15661))
*   Support ParamSpec and TypeVarTuple (Ali Hamdan, PR [15626](https://github.com/python/mypy/pull/15626))
*   Fix crash on non-str docstring (Ali Hamdan, PR [15623](https://github.com/python/mypy/pull/15623))

### Documentation Updates

*   Add documentation for additional error codes (Ivan Levkivskyi, PR [15539](https://github.com/python/mypy/pull/15539))
*   Improve documentation of type narrowing (Ilya Priven, PR [15652](https://github.com/python/mypy/pull/15652))
*   Small improvements to protocol documentation (Shantanu, PR [15460](https://github.com/python/mypy/pull/15460))
*   Remove confusing instance variable example in cheat sheet (Adel Atallah, PR [15441](https://github.com/python/mypy/pull/15441))

### Other Notable Fixes and Improvements

*   Constant fold additional unary and binary expressions (Richard Si, PR [15202](https://github.com/python/mypy/pull/15202))
*   Exclude the same special attributes from Protocol as CPython (Kyle Benesch, PR [15490](https://github.com/python/mypy/pull/15490))
*   Change the default value of the slots argument of attrs.define to True, to match runtime behavior (Ilya Priven, PR [15642](https://github.com/python/mypy/pull/15642))
*   Fix type of class attribute if attribute is defined in both class and metaclass (Alex Waygood, PR [14988](https://github.com/python/mypy/pull/14988))
*   Handle type the same as typing.Type in the first argument of classmethods (Erik Kemperman, PR [15297](https://github.com/python/mypy/pull/15297))
*   Fix \--find-occurrences flag (Shantanu, PR [15528](https://github.com/python/mypy/pull/15528))
*   Fix error location for class patterns (Nikita Sobolev, PR [15506](https://github.com/python/mypy/pull/15506))
*   Fix re-added file with errors in mypy daemon (Ivan Levkivskyi, PR [15440](https://github.com/python/mypy/pull/15440))
*   Fix dmypy run on Windows (Ivan Levkivskyi, PR [15429](https://github.com/python/mypy/pull/15429))
*   Fix abstract and non-abstract variant error for property deleter (Shantanu, PR [15395](https://github.com/python/mypy/pull/15395))
*   Remove special casing for "cannot" in error messages (Ilya Priven, PR [15428](https://github.com/python/mypy/pull/15428))
*   Add runtime `__slots__` attribute to attrs classes (Nikita Sobolev, PR [15651](https://github.com/python/mypy/pull/15651))
*   Add get\_expression\_type to CheckerPluginInterface (Ilya Priven, PR [15369](https://github.com/python/mypy/pull/15369))
*   Remove parameters that no longer exist from NamedTuple.\_make() (Alex Waygood, PR [15578](https://github.com/python/mypy/pull/15578))
*   Allow using typing.Self in `__all__` with an explicit @staticmethod decorator (Erik Kemperman, PR [15353](https://github.com/python/mypy/pull/15353))
*   Fix self types in subclass methods without Self annotation (Ivan Levkivskyi, PR [15541](https://github.com/python/mypy/pull/15541))
*   Check for abstract class objects in tuples (Nikita Sobolev, PR [15366](https://github.com/python/mypy/pull/15366))

### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=fc7d4722eaa54803926cee5730e1f784979c0531+0&branch=main&path=stdlib) for full list of typeshed changes.

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Adel Atallah
*   Alex Waygood
*   Ali Hamdan
*   Erik Kemperman
*   Federico Padua
*   Ilya Priven
*   Ivan Levkivskyi
*   Jelle Zijlstra
*   Jared Hance
*   Jukka Lehtosalo
*   Kyle Benesch
*   Logan Hunt
*   Marc Mueller
*   Nikita Sobolev
*   Richard Si
*   Shantanu
*   Stavros Ntentos
*   Valentin Stanciu

Posted by Valentin Stanciu


## Mypy 1.4

[Tuesday, 20 June 2023](https://mypy-lang.blogspot.com/2023/06/mypy-140-released.html)

We’ve just uploaded mypy 1.4 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### The Override Decorator

Mypy can now ensure that when renaming a method, overrides are also renamed. You can explicitly mark a method as overriding a base class method by using the @typing.override decorator ([PEP 698](https://peps.python.org/pep-0698/)). If the method is then renamed in the base class while the method override is not, mypy will generate an error. The decorator will be available in typing in Python 3.12, but you can also use the backport from a recent version of `typing_extensions` on all supported Python versions.

This feature was contributed byThomas M Kehrenberg (PR [14609](https://github.com/python/mypy/pull/14609)).

### Propagating Type Narrowing to Nested Functions

Previously, type narrowing was not propagated to nested functions because it would not be sound if the narrowed variable changed between the definition of the nested function and the call site. Mypy will now propagate the narrowed type if the variable is not assigned to after the definition of the nested function:

```python
def outer(x: str | None = None) -> None:
    if x is None:
        x = calculate_default()
    reveal_type(x)  # "str" (narrowed)

    def nested() -> None:
        reveal_type(x)  # Now "str" (used to be "str | None")

    nested()
```

This may generate some new errors because asserts that were previously necessary may become tautological or no-ops.

This was contributed by Jukka Lehtosalo (PR [15133](https://github.com/python/mypy/pull/15133)).

### Narrowing Enum Values Using “==”

Mypy now allows narrowing enum types using the \== operator. Previously this was only supported when using the is operator. This makes exhaustiveness checking with enum types more usable, as the requirement to use the is operator was not very intuitive. In this example mypy can detect that the developer forgot to handle the value MyEnum.C in example

```python
from enum import Enum

class MyEnum(Enum):
    A = 0
    B = 1
    C = 2

def example(e: MyEnum) -> str:  # Error: Missing return statement
    if e == MyEnum.A:
        return 'x'
    elif e == MyEnum.B:
        return 'y'
```

Adding an extra elif case resolves the error:

```python
...
def example(e: MyEnum) -> str:  # No error -- all values covered
    if e == MyEnum.A:
        return 'x'
    elif e == MyEnum.B:
        return 'y'
    elif e == MyEnum.C:
        return 'z'
```

This change can cause false positives in test cases that have assert statements like assert o.x == SomeEnum.X when using \--strict-equality. Example:

```python
# mypy: strict-equality

from enum import Enum

class MyEnum(Enum):
    A = 0
    B = 1

class C:
    x: MyEnum
    ...

def test_something() -> None:
    c = C(...)
    assert c.x == MyEnum.A
    c.do_something_that_changes_x()
    assert c.x == MyEnum.B  # Error: Non-overlapping equality check
```

These errors can be ignored using \# type: ignore\[comparison-overlap\], or you can perform the assertion using a temporary variable as a workaround:

```python
...
def test_something() -> None:
    ...
    x = c.x
    assert x == MyEnum.A  # Does not narrow c.x
    c.do_something_that_changes_x()
    x = c.x
    assert x == MyEnum.B  # OK
```

This feature was contributed by Shantanu (PR [11521](https://github.com/python/mypy/pull/11521)).

### Performance Improvements

*   Speed up simplification of large union types and also fix a recursive tuple crash (Shantanu, PR [15128](https://github.com/python/mypy/pull/15128))
*   Speed up union subtyping (Shantanu, PR [15104](https://github.com/python/mypy/pull/15104))
*   Don't type check most function bodies when type checking third-party library code, or generally when ignoring errors (Jukka Lehtosalo, PR [14150](https://github.com/python/mypy/pull/14150))

### Improvements to Plugins

*   attrs.evolve: Support generics and unions (Ilya Konstantinov, PR [15050](https://github.com/python/mypy/pull/15050))
*   Fix ctypes plugin (Alex Waygood)

### Fixes to Crashes

*   Fix a crash when function-scope recursive alias appears as upper bound (Ivan Levkivskyi, PR [15159](https://github.com/python/mypy/pull/15159))
*   Fix crash on follow\_imports\_for\_stubs (Ivan Levkivskyi, PR [15407](https://github.com/python/mypy/pull/15407))
*   Fix stubtest crash in explicit init subclass (Shantanu, PR [15399](https://github.com/python/mypy/pull/15399))
*   Fix crash when indexing TypedDict with empty key (Shantanu, PR [15392](https://github.com/python/mypy/pull/15392))
*   Fix crash on NamedTuple as attribute (Ivan Levkivskyi, PR [15404](https://github.com/python/mypy/pull/15404))
*   Correctly track loop depth for nested functions/classes (Ivan Levkivskyi, PR [15403](https://github.com/python/mypy/pull/15403))
*   Fix crash on joins with recursive tuples (Ivan Levkivskyi, PR [15402](https://github.com/python/mypy/pull/15402))
*   Fix crash with custom ErrorCode subclasses (Marc Mueller, PR [15327](https://github.com/python/mypy/pull/15327))
*   Fix crash in dataclass protocol with self attribute assignment (Ivan Levkivskyi, PR [15157](https://github.com/python/mypy/pull/15157))
*   Fix crash on lambda in generic context with generic method in body (Ivan Levkivskyi, PR [15155](https://github.com/python/mypy/pull/15155))
*   Fix recursive type alias crash in make\_simplified\_union (Ivan Levkivskyi, PR [15216](https://github.com/python/mypy/pull/15216))

### Improvements to Error Messages

*   Use lower-case built-in collection types such as list\[…\] instead of List\[…\] in errors when targeting Python 3.9+ (Max Murin, PR [15070](https://github.com/python/mypy/pull/15070))
*   Use X | Y union syntax in error messages when targeting Python 3.10+ (Omar Silva, PR [15102](https://github.com/python/mypy/pull/15102))
*   Use type instead of Type in errors when targeting Python 3.9+ (Rohit Sanjay, PR [15139](https://github.com/python/mypy/pull/15139))
*   Do not show unused-ignore errors in unreachable code, and make it a real error code (Ivan Levkivskyi, PR [15164](https://github.com/python/mypy/pull/15164))
*   Don’t limit the number of errors shown by default (Rohit Sanjay, PR [15138](https://github.com/python/mypy/pull/15138))
*   Improver message for truthy functions (madt2709, PR [15193](https://github.com/python/mypy/pull/15193))
*   Output distinct types when type names are ambiguous (teresa0605, PR [15184](https://github.com/python/mypy/pull/15184))
*   Update message about invalid exception type in try (AJ Rasmussen, PR [15131](https://github.com/python/mypy/pull/15131))
*   Add explanation if argument type is incompatible because of an unsupported numbers type (Jukka Lehtosalo, PR [15137](https://github.com/python/mypy/pull/15137))
*   Add more detail to 'signature incompatible with supertype' messages for non-callables (Ilya Priven, PR [15263](https://github.com/python/mypy/pull/15263))

### Documentation Updates

*   Add \--local-partial-types note to dmypy docs (Alan Du, PR [15259](https://github.com/python/mypy/pull/15259))
*   Update getting started docs for mypyc for Windows (Valentin Stanciu, PR [15233](https://github.com/python/mypy/pull/15233))
*   Clarify usage of callables regarding type object in docs (Viicos, PR [15079](https://github.com/python/mypy/pull/15079))
*   Clarify difference between disallow\_untyped\_defs and disallow\_incomplete\_defs (Ilya Priven, PR [15247](https://github.com/python/mypy/pull/15247))
*   Use attrs and @attrs.define in documentation and tests (Ilya Priven, PR [15152](https://github.com/python/mypy/pull/15152))

### Mypyc Improvements

*   Fix unexpected TypeError for certain variables with an inferred optional type (Richard Si, PR [15206](https://github.com/python/mypy/pull/15206))
*   Inline math literals (Logan Hunt, PR [15324](https://github.com/python/mypy/pull/15324))
*   Support unpacking mappings in dict display (Richard Si, PR [15203](https://github.com/python/mypy/pull/15203))

### Changes to Stubgen

*   Do not remove Generic from base classes (Ali Hamdan, PR [15316](https://github.com/python/mypy/pull/15316))
*   Support yield from statements (Ali Hamdan, PR [15271](https://github.com/python/mypy/pull/15271))
*   Fix missing total from TypedDict class (Ali Hamdan, PR [15208](https://github.com/python/mypy/pull/15208))
*   Fix call-based namedtuple omitted from class bases (Ali Hamdan, PR [14680](https://github.com/python/mypy/pull/14680))
*   Support TypedDict alternative syntax (Ali Hamdan, PR [14682](https://github.com/python/mypy/pull/14682))
*   Make stubgen respect MYPY\_CACHE\_DIR (Henrik Bäärnhielm, PR [14722](https://github.com/python/mypy/pull/14722))
*   Fixes and simplifications (Ali Hamdan, PR [15232](https://github.com/python/mypy/pull/15232))

### Other Notable Fixes and Improvements

*   Fix nested async functions when using TypeVar value restriction (Jukka Lehtosalo, PR [14705](https://github.com/python/mypy/pull/14705))
*   Always allow returning Any from lambda (Ivan Levkivskyi, PR [15413](https://github.com/python/mypy/pull/15413))
*   Add foundation for TypeVar defaults (PEP 696) (Marc Mueller, PR [14872](https://github.com/python/mypy/pull/14872))
*   Update semantic analyzer for TypeVar defaults (PEP 696) (Marc Mueller, PR [14873](https://github.com/python/mypy/pull/14873))
*   Make dict expression inference more consistent (Ivan Levkivskyi, PR [15174](https://github.com/python/mypy/pull/15174))
*   Do not block on duplicate base classes (Nikita Sobolev, PR [15367](https://github.com/python/mypy/pull/15367))
*   Generate an error when both staticmethod and classmethod decorators are used (Juhi Chandalia, PR [15118](https://github.com/python/mypy/pull/15118))
*   Fix assert\_type behaviour with literals (Carl Karsten, PR [15123](https://github.com/python/mypy/pull/15123))
*   Fix match subject ignoring redefinitions (Vincent Vanlaer, PR [15306](https://github.com/python/mypy/pull/15306))
*   Support `__all__`.remove (Shantanu, PR [15279](https://github.com/python/mypy/pull/15279))

### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=877e06ad1cfd9fd9967c0b0340a86d0c23ea89ce+0&branch=main&path=stdlib) for full list of typeshed changes.

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Adrian Garcia Badaracco
*   AJ Rasmussen
*   Alan Du
*   Alex Waygood
*   Ali Hamdan
*   Carl Karsten
*   dosisod
*   Ethan Smith
*   Gregory Santosa
*   Heather White
*   Henrik Bäärnhielm
*   Ilya Konstantinov
*   Ilya Priven
*   Ivan Levkivskyi
*   Juhi Chandalia
*   Jukka Lehtosalo
*   Logan Hunt
*   madt2709
*   Marc Mueller
*   Max Murin
*   Nikita Sobolev
*   Omar Silva
*   Özgür
*   Richard Si
*   Rohit Sanjay
*   Shantanu
*   teresa0605
*   Thomas M Kehrenberg
*   Tin Tvrtković
*   Tushar Sadhwani
*   Valentin Stanciu
*   Viicos
*   Vincent Vanlaer
*   Wesley Collin Wright
*   William Santosa
*   yaegassy

I’d also like to thank my employer, Dropbox, for supporting mypy development.

Posted by Jared Hance


## Mypy 1.3

[Wednesday, 10 May 2023](https://mypy-lang.blogspot.com/2023/05/mypy-13-released.html)

 We’ve just uploaded mypy 1.3 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Performance Improvements

*   Improve performance of union subtyping (Shantanu, PR [15104](https://github.com/python/mypy/pull/15104))
*   Add negative subtype caches (Ivan Levkivskyi, PR [14884](https://github.com/python/mypy/pull/14884))

### Stub Tooling Improvements

*   Stubtest: Check that the stub is abstract if the runtime is, even when the stub is an overloaded method (Alex Waygood, PR [14955](https://github.com/python/mypy/pull/14955))
*   Stubtest: Verify stub methods or properties are decorated with @final if they are decorated with @final at runtime (Alex Waygood, PR [14951](https://github.com/python/mypy/pull/14951))
*   Stubtest: Fix stubtest false positives with TypedDicts at runtime (Alex Waygood, PR [14984](https://github.com/python/mypy/pull/14984))
*   Stubgen: Support @functools.cached\_property (Nikita Sobolev, PR [14981](https://github.com/python/mypy/pull/14981))
*   Improvements to stubgenc (Chad Dombrova, PR [14564](https://github.com/python/mypy/pull/14564))

### Improvements to attrs

*   Add support for converters with TypeVars on generic attrs classes (Chad Dombrova, PR [14908](https://github.com/python/mypy/pull/14908))
*   Fix attrs.evolve on bound TypeVar (Ilya Konstantinov, PR [15022](https://github.com/python/mypy/pull/15022))

### Documentation Updates

*   Improve async documentation (Shantanu, PR [14973](https://github.com/python/mypy/pull/14973))
*   Improvements to cheat sheet (Shantanu, PR [14972](https://github.com/python/mypy/pull/14972))
*   Add documentation for bytes formatting error code (Shantanu, PR [14971](https://github.com/python/mypy/pull/14971))
*   Convert insecure links to use HTTPS (Marti Raudsepp, PR [14974](https://github.com/python/mypy/pull/14974))
*   Also mention overloads in async iterator documentation (Shantanu, PR [14998](https://github.com/python/mypy/pull/14998))
*   stubtest: Improve allowlist documentation (Shantanu, PR [15008](https://github.com/python/mypy/pull/15008))
*   Clarify "Using types... but not at runtime" (Jon Shea, PR [15029](https://github.com/python/mypy/pull/15029))
*   Fix alignment of cheat sheet example (Ondřej Cvacho, PR [15039](https://github.com/python/mypy/pull/15039))
*   Fix error for callback protocol matching against callable type object (Shantanu, PR [15042](https://github.com/python/mypy/pull/15042))

### Error Reporting Improvements

*   Improve bytes formatting error (Shantanu, PR [14959](https://github.com/python/mypy/pull/14959))

### Mypyc Improvements

*   Fix unions of bools and ints (Tomer Chachamu, PR [15066](https://github.com/python/mypy/pull/15066))

### Other Fixes and Improvements

*   Fix narrowing union types that include Self with isinstance (Christoph Tyralla, PR [14923](https://github.com/python/mypy/pull/14923))
*   Allow objects matching SupportsKeysAndGetItem to be unpacked (Bryan Forbes, PR [14990](https://github.com/python/mypy/pull/14990))
*   Check type guard validity for staticmethods (EXPLOSION, PR [14953](https://github.com/python/mypy/pull/14953))
*   Fix sys.platform when cross-compiling with emscripten (Ethan Smith, PR [14888](https://github.com/python/mypy/pull/14888))

### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=b0ed50e9392a23e52445b630a808153e0e256976+0&branch=main&path=stdlib) for full list of typeshed changes.

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Alex Waygood
*   Amin Alaee
*   Bryan Forbes
*   Chad Dombrova
*   Charlie Denton
*   Christoph Tyralla
*   dosisod
*   Ethan Smith
*   EXPLOSION
*   Ilya Konstantinov
*   Ivan Levkivskyi
*   Jon Shea
*   Jukka Lehtosalo
*   KotlinIsland
*   Marti Raudsepp
*   Nikita Sobolev
*   Ondřej Cvacho
*   Shantanu
*   sobolevn
*   Tomer Chachamu
*   Yaroslav Halchenko

Posted by Wesley Collin Wright.


## Mypy 1.2

[Thursday, 6 April 2023](https://mypy-lang.blogspot.com/2023/04/mypy-12-released.html)

We’ve just uploaded mypy 1.2 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Improvements to Dataclass Transforms

*   Support implicit default for "init" parameter in field specifiers (Wesley Collin Wright and Jukka Lehtosalo, PR [15010](https://github.com/python/mypy/pull/15010))
*   Support descriptors in dataclass transform (Jukka Lehtosalo, PR [15006](https://github.com/python/mypy/pull/15006))
*   Fix frozen\_default in incremental mode (Wesley Collin Wright)
*   Fix frozen behavior for base classes with direct metaclasses (Wesley Collin Wright, PR [14878](https://github.com/python/mypy/pull/14878))

### Mypyc: Native Floats

Mypyc now uses a native, unboxed representation for values of type float. Previously these were heap-allocated Python objects. Native floats are faster and use less memory. Code that uses floating-point operations heavily can be several times faster when using native floats.

Various float operations and math functions also now have optimized implementations. Refer to the [documentation](https://mypyc.readthedocs.io/en/latest/float_operations.html) for a full list.

This can change the behavior of existing code that uses subclasses of float. When assigning an instance of a subclass of float to a variable with the float type, it gets implicitly converted to a float instance when compiled:

```python
from lib import MyFloat  # MyFloat ia a subclass of "float"

def example() -> None:
    x = MyFloat(1.5)
    y: float = x  # Implicit conversion from MyFloat to float
    print(type(y))  # float, not MyFloat
```

Previously, implicit conversions were applied to int subclasses but not float subclasses.

Also, int values can no longer be assigned to a variable with type float in compiled code, since these types now have incompatible representations. An explicit conversion is required:

```python
def example(n: int) -> None:
    a: float = 1  # Error: cannot assign "int" to "float"
    b: float = 1.0  # OK
    c: float = n  # Error
    d: float = float(n)  # OK
```

This restriction only applies to assignments, since they could otherwise narrow down the type of a variable from float to int. int values can still be implicitly converted to float when passed as arguments to functions that expect float values.

Note that mypyc still doesn’t support arrays of unboxed float values. Using list\[float\] involves heap-allocated float objects, since list can only store boxed values. Support for efficient floating point arrays is one of the next major planned mypyc features.

Related changes:

*   Use a native unboxed representation for floats (Jukka Lehtosalo, PR [14880](https://github.com/python/mypy/pull/14880))
*   Document native floats and integers (Jukka Lehtosalo, PR [14927](https://github.com/python/mypy/pull/14927))
*   Fixes to float to int conversion (Jukka Lehtosalo, PR [14936](https://github.com/python/mypy/pull/14936))

### Mypyc: Native Integers

Mypyc now supports signed 32-bit and 64-bit integer types in addition to the arbitrary-precision int type. You can use the types mypy\_extensions.i32 and mypy\_extensions.i64 to speed up code that uses integer operations heavily.

Simple example:
```python
from mypy_extensions import i64

def inc(x: i64) -> i64:
    return x + 1
```

Refer to the [documentation](https://mypyc.readthedocs.io/en/latest/using_type_annotations.html#native-integer-types) for more information. This feature was contributed by Jukka Lehtosalo.

### Other Mypyc Fixes and Improvements

*   Support iterating over a TypedDict (Richard Si, PR [14747](https://github.com/python/mypy/pull/14747))
*   Faster coercions between different tuple types (Jukka Lehtosalo, PR [14899](https://github.com/python/mypy/pull/14899))
*   Faster calls via type aliases (Jukka Lehtosalo, PR [14784](https://github.com/python/mypy/pull/14784))
*   Faster classmethod calls via cls (Jukka Lehtosalo, PR [14789](https://github.com/python/mypy/pull/14789))

### Fixes to Crashes

*   Fix crash on class-level import in protocol definition (Ivan Levkivskyi, PR [14926](https://github.com/python/mypy/pull/14926))
*   Fix crash on single item union of alias (Ivan Levkivskyi, PR [14876](https://github.com/python/mypy/pull/14876))
*   Fix crash on ParamSpec in incremental mode (Ivan Levkivskyi, PR [14885](https://github.com/python/mypy/pull/14885))

### Documentation Updates

*   Update adopting \--strict documentation for 1.0 (Shantanu, PR [14865](https://github.com/python/mypy/pull/14865))
*   Some minor documentation tweaks (Jukka Lehtosalo, PR [14847](https://github.com/python/mypy/pull/14847))
*   Improve documentation of top level mypy: disable-error-code comment (Nikita Sobolev, PR [14810](https://github.com/python/mypy/pull/14810))

### Error Reporting Improvements

*   Add error code to `typing_extensions` suggestion (Shantanu, PR [14881](https://github.com/python/mypy/pull/14881))
*   Add a separate error code for top-level await (Nikita Sobolev, PR [14801](https://github.com/python/mypy/pull/14801))
*   Don’t suggest two obsolete stub packages (Jelle Zijlstra, PR [14842](https://github.com/python/mypy/pull/14842))
*   Add suggestions for pandas-stubs and lxml-stubs (Shantanu, PR [14737](https://github.com/python/mypy/pull/14737))

### Other Fixes and Improvements

*   Multiple inheritance considers callable objects as subtypes of functions (Christoph Tyralla, PR [14855](https://github.com/python/mypy/pull/14855))
*   stubtest: Respect @final runtime decorator and enforce it in stubs (Nikita Sobolev, PR [14922](https://github.com/python/mypy/pull/14922))
*   Fix false positives related to type\[<type-var>\] (sterliakov, PR [14756](https://github.com/python/mypy/pull/14756))
*   Fix duplication of ParamSpec prefixes and properly substitute ParamSpecs (EXPLOSION, PR [14677](https://github.com/python/mypy/pull/14677))
*   Fix line number if `__iter__` is incorrectly reported as missing (Jukka Lehtosalo, PR [14893](https://github.com/python/mypy/pull/14893))
*   Fix incompatible overrides of overloaded generics with self types (Shantanu, PR [14882](https://github.com/python/mypy/pull/14882))
*   Allow SupportsIndex in slice expressions (Shantanu, PR [14738](https://github.com/python/mypy/pull/14738))
*   Support if statements in bodies of dataclasses and classes that use dataclass\_transform (Jacek Chałupka, PR [14854](https://github.com/python/mypy/pull/14854))
*   Allow iterable class objects to be unpacked (including enums) (Alex Waygood, PR [14827](https://github.com/python/mypy/pull/14827))
*   Fix narrowing for walrus expressions used in match statements (Shantanu, PR [14844](https://github.com/python/mypy/pull/14844))
*   Add signature for attr.evolve (Ilya Konstantinov, PR [14526](https://github.com/python/mypy/pull/14526))
*   Fix Any inference when unpacking iterators that don't directly inherit from typing.Iterator (Alex Waygood, PR [14821](https://github.com/python/mypy/pull/14821))
*   Fix unpack with overloaded `__iter__` method (Nikita Sobolev, PR [14817](https://github.com/python/mypy/pull/14817))
*   Reduce size of JSON data in mypy cache (dosisod, PR [14808](https://github.com/python/mypy/pull/14808))
*   Improve “used before definition” checks when a local definition has the same name as a global definition (Stas Ilinskiy, PR [14517](https://github.com/python/mypy/pull/14517))
*   Honor NoReturn as \_\_setitem\_\_ return type to mark unreachable code (sterliakov, PR [12572](https://github.com/python/mypy/pull/12572))

### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=a544b75320e97424d2d927605316383c755cdac0+0&branch=main&path=stdlib) for full list of typeshed changes.

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Alex Waygood
*   Avasam
*   Christoph Tyralla
*   dosisod
*   EXPLOSION
*   Ilya Konstantinov
*   Ivan Levkivskyi
*   Jacek Chałupka
*   Jelle Zijlstra
*   Jukka Lehtosalo
*   Marc Mueller
*   Max Murin
*   Nikita Sobolev
*   Richard Si
*   Shantanu
*   Stas Ilinskiy
*   sterliakov
*   Wesley Collin Wright

Posted by Jukka Lehtosalo


## Mypy 1.1.1

[Monday, 6 March 2023](https://mypy-lang.blogspot.com/2023/03/mypy-111-released.html)

 We’ve just uploaded mypy 1.1.1 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### Support for `dataclass_transform``

This release adds full support for the dataclass\_transform decorator defined in [PEP 681](https://peps.python.org/pep-0681/#decorator-function-example). This allows decorators, base classes, and metaclasses that generate a \_\_init\_\_ method or other methods based on the properties of that class (similar to dataclasses) to have those methods recognized by mypy.

This was contributed by Wesley Collin Wright.

### Dedicated Error Code for Method Assignments

Mypy can’t safely check all assignments to methods (a form of monkey patching), so mypy generates an error by default. To make it easier to ignore this error, mypy now uses the new error code method-assign for this. By disabling this error code in a file or globally, mypy will no longer complain about assignments to methods if the signatures are compatible.

Mypy also supports the old error code assignment for these assignments to prevent a backward compatibility break. More generally, we can use this mechanism in the future if we wish to split or rename another existing error code without causing backward compatibility issues.

This was contributed by Ivan Levkivskyi (PR [14570](https://github.com/python/mypy/pull/14570)).

### Fixes to Crashes

*   Fix a crash on walrus in comprehension at class scope (Ivan Levkivskyi, PR [14556](https://github.com/python/mypy/pull/14556))
*   Fix crash related to value-constrained TypeVar (Shantanu, PR [14642](https://github.com/python/mypy/pull/14642))

### Fixes to Cache Corruption

*   Fix generic TypedDict/NamedTuple caching (Ivan Levkivskyi, PR [14675](https://github.com/python/mypy/pull/14675))

### Mypyc Fixes and Improvements

*   Raise "non-trait base must be first..." error less frequently (Richard Si, PR [14468](https://github.com/python/mypy/pull/14468))
*   Generate faster code for bool comparisons and arithmetic (Jukka Lehtosalo, PR [14489](https://github.com/python/mypy/pull/14489))
*   Optimize \_\_(a)enter\_\_/\_\_(a)exit\_\_ for native classes (Jared Hance, PR [14530](https://github.com/python/mypy/pull/14530))
*   Detect if attribute definition conflicts with base class/trait (Jukka Lehtosalo, PR [14535](https://github.com/python/mypy/pull/14535))
*   Support \_\_(r)divmod\_\_ dunders (Richard Si, PR [14613](https://github.com/python/mypy/pull/14613))
*   Support \_\_pow\_\_, \_\_rpow\_\_, and \_\_ipow\_\_ dunders (Richard Si, PR [14616](https://github.com/python/mypy/pull/14616))
*   Fix crash on star unpacking to underscore (Ivan Levkivskyi, PR [14624](https://github.com/python/mypy/pull/14624))
*   Fix iterating over a union of dicts (Richard Si, PR [14713](https://github.com/python/mypy/pull/14713))

### Fixes to Detecting Undefined Names (used-before-def)

*   Correctly handle walrus operator (Stas Ilinskiy, PR [14646](https://github.com/python/mypy/pull/14646))
*   Handle walrus declaration in match subject correctly (Stas Ilinskiy, PR [14665](https://github.com/python/mypy/pull/14665))

### Stubgen Improvements

Stubgen is a tool for automatically generating draft stubs for libraries.

*   Allow aliases below the top level (Chad Dombrova, PR [14388](https://github.com/python/mypy/pull/14388))
*   Fix crash with PEP 604 union in type variable bound (Shantanu, PR [14557](https://github.com/python/mypy/pull/14557))
*   Preserve PEP 604 unions in generated .pyi files (hamdanal, PR [14601](https://github.com/python/mypy/pull/14601))

### Stubtest Improvements

Stubtest is a tool for testing that stubs conform to the implementations.

*   Update message format so that it’s easier to go to error location (Avasam, PR [14437](https://github.com/python/mypy/pull/14437))
*   Handle name-mangling edge cases better (Alex Waygood, PR [14596](https://github.com/python/mypy/pull/14596))

### Changes to Error Reporting and Messages

*   Add new TypedDict error code typeddict-unknown-key (JoaquimEsteves, PR [14225](https://github.com/python/mypy/pull/14225))
*   Give arguments a more reasonable location in error messages (Max Murin, PR [14562](https://github.com/python/mypy/pull/14562))
*   In error messages, quote just the module's name (Ilya Konstantinov, PR [14567](https://github.com/python/mypy/pull/14567))
*   Improve misleading message about Enum() (Rodrigo Silva, PR [14590](https://github.com/python/mypy/pull/14590))
*   Suggest importing from `typing_extensions` if definition is not in typing (Shantanu, PR [14591](https://github.com/python/mypy/pull/14591))
*   Consistently use type-abstract error code (Ivan Levkivskyi, PR [14619](https://github.com/python/mypy/pull/14619))
*   Consistently use literal-required error code for TypedDicts (Ivan Levkivskyi, PR [14621](https://github.com/python/mypy/pull/14621))
*   Adjust inconsistent dataclasses plugin error messages (Wesley Collin Wright, PR [14637](https://github.com/python/mypy/pull/14637))
*   Consolidate literal bool argument error messages (Wesley Collin Wright, PR [14693](https://github.com/python/mypy/pull/14693))

### Other Fixes and Improvements

*   Check that type guards accept a positional argument (EXPLOSION, PR [14238](https://github.com/python/mypy/pull/14238))
*   Fix bug with in operator used with a union of Container and Iterable (Max Murin, PR [14384](https://github.com/python/mypy/pull/14384))
*   Support protocol inference for type\[T\] via metaclass (Ivan Levkivskyi, PR [14554](https://github.com/python/mypy/pull/14554))
*   Allow overlapping comparisons between bytes-like types (Shantanu, PR [14658](https://github.com/python/mypy/pull/14658))
*   Fix mypy daemon documentation link in README (Ivan Levkivskyi, PR [14644](https://github.com/python/mypy/pull/14644))

### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=5ebf892d0710a6e87925b8d138dfa597e7bb11cc+0&branch=main&path=stdlib) for full list of typeshed changes.

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Alex Waygood
*   Avasam
*   Chad Dombrova
*   dosisod
*   EXPLOSION
*   hamdanal
*   Ilya Konstantinov
*   Ivan Levkivskyi
*   Jared Hance
*   JoaquimEsteves
*   Jukka Lehtosalo
*   Marc Mueller
*   Max Murin
*   Michael Lee
*   Michael R. Crusoe
*   Richard Si
*   Rodrigo Silva
*   Shantanu
*   Stas Ilinskiy
*   Wesley Collin Wright
*   Yilei "Dolee" Yang
*   Yurii Karabas

We’d also like to thank our employer, Dropbox, for funding the mypy core team.

Posted by Max Murin


## Mypy 1.0

[Monday, 6 February 2023](https://mypy-lang.blogspot.com/2023/02/mypy-10-released.html)

We’ve just uploaded mypy 1.0 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

### New Release Versioning Scheme

Now that mypy reached 1.0, we’ll switch to a new versioning scheme. Mypy version numbers will be of form x.y.z.

Rules:

*   The major release number (x) is incremented if a feature release includes a significant backward incompatible change that affects a significant fraction of users.
*   The minor release number (y) is incremented on each feature release. Minor releases include updated stdlib stubs from typeshed.
*   The point release number (z) is incremented when there are fixes only.

Mypy doesn't use SemVer, since most minor releases have at least minor backward incompatible changes in typeshed, at the very least. Also, many type checking features find new legitimate issues in code. These are not considered backward incompatible changes, unless the number of new errors is very high.

Any significant backward incompatible change must be announced in the blog post for the previous feature release, before making the change. The previous release must also provide a flag to explicitly enable or disable the new behavior (whenever practical), so that users will be able to prepare for the changes and report issues. We should keep the feature flag for at least a few releases after we've switched the default.

See [”Release Process” in the mypy wiki](https://github.com/python/mypy/wiki/Release-Process) for more details and for the most up-to-date version of the versioning scheme.

### Performance Improvements

Mypy 1.0 is up to 40% faster than mypy 0.991 when type checking the Dropbox internal codebase. We also set up a daily job to measure the performance of the most recent development version of mypy to make it easier to track changes in performance.

Many optimizations contributed to this improvement:

*   Improve performance for errors on class with many attributes (Shantanu, PR [14379](https://github.com/python/mypy/pull/14379))
*   Speed up make\_simplified\_union (Jukka Lehtosalo, PR [14370](https://github.com/python/mypy/pull/14370))
*   Micro-optimize get\_proper\_type(s) (Jukka Lehtosalo, PR [14369](https://github.com/python/mypy/pull/14369))
*   Micro-optimize flatten\_nested\_unions (Jukka Lehtosalo, PR [14368](https://github.com/python/mypy/pull/14368))
*   Some semantic analyzer micro-optimizations (Jukka Lehtosalo, PR [14367](https://github.com/python/mypy/pull/14367))
*   A few miscellaneous micro-optimizations (Jukka Lehtosalo, PR [14366](https://github.com/python/mypy/pull/14366))
*   Optimization: Avoid a few uses of contextmanagers in semantic analyzer (Jukka Lehtosalo, PR [14360](https://github.com/python/mypy/pull/14360))
*   Optimization: Enable always defined attributes in Type subclasses (Jukka Lehtosalo, PR [14356](https://github.com/python/mypy/pull/14356))
*   Optimization: Remove expensive context manager in type analyzer (Jukka Lehtosalo, PR [14357](https://github.com/python/mypy/pull/14357))
*   subtypes: fast path for Union/Union subtype check (Hugues, PR [14277](https://github.com/python/mypy/pull/14277))
*   Micro-optimization: avoid Bogus\[int\] types that cause needless boxing (Jukka Lehtosalo, PR [14354](https://github.com/python/mypy/pull/14354))
*   Avoid slow error message logic if errors not shown to user (Jukka Lehtosalo, PR [14336](https://github.com/python/mypy/pull/14336))
*   Speed up the implementation of hasattr() checks (Jukka Lehtosalo, PR [14333](https://github.com/python/mypy/pull/14333))
*   Avoid the use of a context manager in hot code path (Jukka Lehtosalo, PR [14331](https://github.com/python/mypy/pull/14331))
*   Change various type queries into faster bool type queries (Jukka Lehtosalo, PR [14330](https://github.com/python/mypy/pull/14330))
*   Speed up recursive type check (Jukka Lehtosalo, PR [14326](https://github.com/python/mypy/pull/14326))
*   Optimize subtype checking by avoiding a nested function (Jukka Lehtosalo, PR [14325](https://github.com/python/mypy/pull/14325))
*   Optimize type parameter checks in subtype checking (Jukka Lehtosalo, PR [14324](https://github.com/python/mypy/pull/14324))
*   Speed up freshening type variables (Jukka Lehtosalo, PR [14323](https://github.com/python/mypy/pull/14323))
*   Optimize implementation of TypedDict types for \*\*kwds (Jukka Lehtosalo, PR [14316](https://github.com/python/mypy/pull/14316))

### Warn About Variables Used Before Definition

Mypy will now generate an error if you use a variable before it’s defined. This feature is enabled by default. By default mypy reports an error when it infers that a variable is always undefined.
```python
y = x  # E: Name "x" is used before definition [used-before-def]
x = 0
```
This feature was contributed by Stas Ilinskiy.

### Detect Possibly Undefined Variables (Experimental)

A new experimental possibly-undefined error code is now available that will detect variables that may be undefined:
```python
    if b:
        x = 0
    print(x)  # Error: Name "x" may be undefined [possibly-undefined]
```
The error code is disabled be default, since it can generate false positives.

This feature was contributed by Stas Ilinskiy.

### Support the “Self” Type

There is now a simpler syntax for declaring [generic self types](https://mypy.readthedocs.io/en/stable/generics.html#generic-methods-and-generic-self) introduced in [PEP 673](https://peps.python.org/pep-0673/): the Self type. You no longer have to define a type variable to use “self types”, and you can use them with attributes. Example from mypy documentation:
```python
from typing import Self

class Friend:
    other: Self | None = None

    @classmethod
    def make_pair(cls) -> tuple[Self, Self]:
        a, b = cls(), cls()
        a.other = b
        b.other = a
        return a, b

class SuperFriend(Friend):
    pass

# a and b have the inferred type "SuperFriend", not "Friend"
a, b = SuperFriend.make_pair()
```
The feature was introduced in Python 3.11. In earlier Python versions a backport of Self is available in `typing_extensions`.

This was contributed by Ivan Levkivskyi (PR [14041](https://github.com/python/mypy/pull/14041)).

### Support ParamSpec in Type Aliases

ParamSpec and Concatenate can now be used in type aliases. Example:
```python
from typing import ParamSpec, Callable

P = ParamSpec("P")
A = Callable[P, None]

def f(c: A[int, str]) -> None:
    c(1, "x")
```
This feature was contributed by Ivan Levkivskyi (PR [14159](https://github.com/python/mypy/pull/14159)).

### ParamSpec and Generic Self Types No Longer Experimental

Support for ParamSpec ([PEP 612](https://www.python.org/dev/peps/pep-0612/)) and generic self types are no longer considered experimental.

### Miscellaneous New Features

*   Minimal, partial implementation of dataclass\_transform ([PEP 681](https://peps.python.org/pep-0681/)) (Wesley Collin Wright, PR [14523](https://github.com/python/mypy/pull/14523))
*   Add basic support for `typing_extensions`.TypeVar (Marc Mueller, PR [14313](https://github.com/python/mypy/pull/14313))
*   Add \--debug-serialize option (Marc Mueller, PR [14155](https://github.com/python/mypy/pull/14155))
*   Constant fold initializers of final variables (Jukka Lehtosalo, PR [14283](https://github.com/python/mypy/pull/14283))
*   Enable Final instance attributes for attrs (Tin Tvrtković, PR [14232](https://github.com/python/mypy/pull/14232))
*   Allow function arguments as base classes (Ivan Levkivskyi, PR [14135](https://github.com/python/mypy/pull/14135))
*   Allow super() with mixin protocols (Ivan Levkivskyi, PR [14082](https://github.com/python/mypy/pull/14082))
*   Add type inference for dict.keys membership (Matthew Hughes, PR [13372](https://github.com/python/mypy/pull/13372))
*   Generate error for class attribute access if attribute is defined with `__slots__` (Harrison McCarty, PR [14125](https://github.com/python/mypy/pull/14125))
*   Support additional attributes in callback protocols (Ivan Levkivskyi, PR [14084](https://github.com/python/mypy/pull/14084))

### Fixes to Crashes

*   Fix crash on prefixed ParamSpec with forward reference (Ivan Levkivskyi, PR [14569](https://github.com/python/mypy/pull/14569))
*   Fix internal crash when resolving the same partial type twice (Shantanu, PR [14552](https://github.com/python/mypy/pull/14552))
*   Fix crash in daemon mode on new import cycle (Ivan Levkivskyi, PR [14508](https://github.com/python/mypy/pull/14508))
*   Fix crash in mypy daemon (Ivan Levkivskyi, PR [14497](https://github.com/python/mypy/pull/14497))
*   Fix crash on Any metaclass in incremental mode (Ivan Levkivskyi, PR [14495](https://github.com/python/mypy/pull/14495))
*   Fix crash in await inside comprehension outside function (Ivan Levkivskyi, PR [14486](https://github.com/python/mypy/pull/14486))
*   Fix crash in Self type on forward reference in upper bound (Ivan Levkivskyi, PR [14206](https://github.com/python/mypy/pull/14206))
*   Fix a crash when incorrect super() is used outside a method (Ivan Levkivskyi, PR [14208](https://github.com/python/mypy/pull/14208))
*   Fix crash on overriding with frozen attrs (Ivan Levkivskyi, PR [14186](https://github.com/python/mypy/pull/14186))
*   Fix incremental mode crash on generic function appearing in nested position (Ivan Levkivskyi, PR [14148](https://github.com/python/mypy/pull/14148))
*   Fix daemon crash on malformed NamedTuple (Ivan Levkivskyi, PR [14119](https://github.com/python/mypy/pull/14119))
*   Fix crash during ParamSpec inference (Ivan Levkivskyi, PR [14118](https://github.com/python/mypy/pull/14118))
*   Fix crash on nested generic callable (Ivan Levkivskyi, PR [14093](https://github.com/python/mypy/pull/14093))
*   Fix crashes with unpacking SyntaxError (Shantanu, PR [11499](https://github.com/python/mypy/pull/11499))
*   Fix crash on partial type inference within a lambda (Ivan Levkivskyi, PR [14087](https://github.com/python/mypy/pull/14087))
*   Fix crash with enums (Michael Lee, PR [14021](https://github.com/python/mypy/pull/14021))
*   Fix crash with malformed TypedDicts and disllow-any-expr (Michael Lee, PR [13963](https://github.com/python/mypy/pull/13963))

### Error Reporting Improvements

*   More helpful error for missing self (Shantanu, PR [14386](https://github.com/python/mypy/pull/14386))
*   Add error-code truthy-iterable (Marc Mueller, PR [13762](https://github.com/python/mypy/pull/13762))
*   Fix pluralization in error messages (KotlinIsland, PR [14411](https://github.com/python/mypy/pull/14411))

### Mypyc: Support Match Statement

Mypyc can now compile Python 3.10 match statements.

This was contributed by dosisod (PR [13953](https://github.com/python/mypy/pull/13953)).

### Other Mypyc Fixes and Improvements

*   Optimize int(x)/float(x)/complex(x) on instances of native classes (Richard Si, PR [14450](https://github.com/python/mypy/pull/14450))
*   Always emit warnings (Richard Si, PR [14451](https://github.com/python/mypy/pull/14451))
*   Faster bool and integer conversions (Jukka Lehtosalo, PR [14422](https://github.com/python/mypy/pull/14422))
*   Support attributes that override properties (Jukka Lehtosalo, PR [14377](https://github.com/python/mypy/pull/14377))
*   Precompute set literals for "in" operations and iteration (Richard Si, PR [14409](https://github.com/python/mypy/pull/14409))
*   Don't load targets with forward references while setting up non-extension class `__all__` (Richard Si, PR [14401](https://github.com/python/mypy/pull/14401))
*   Compile away NewType type calls (Richard Si, PR [14398](https://github.com/python/mypy/pull/14398))
*   Improve error message for multiple inheritance (Joshua Bronson, PR [14344](https://github.com/python/mypy/pull/14344))
*   Simplify union types (Jukka Lehtosalo, PR [14363](https://github.com/python/mypy/pull/14363))
*   Fixes to union simplification (Jukka Lehtosalo, PR [14364](https://github.com/python/mypy/pull/14364))
*   Fix for typeshed changes to Collection (Shantanu, PR [13994](https://github.com/python/mypy/pull/13994))
*   Allow use of enum.Enum (Shantanu, PR [13995](https://github.com/python/mypy/pull/13995))
*   Fix compiling on Arch Linux (dosisod, PR [13978](https://github.com/python/mypy/pull/13978))

### Documentation Improvements

*   Various documentation and error message tweaks (Jukka Lehtosalo, PR [14574](https://github.com/python/mypy/pull/14574))
*   Improve Generics documentation (Shantanu, PR [14587](https://github.com/python/mypy/pull/14587))
*   Improve protocols documentation (Shantanu, PR [14577](https://github.com/python/mypy/pull/14577))
*   Improve dynamic typing documentation (Shantanu, PR [14576](https://github.com/python/mypy/pull/14576))
*   Improve the Common Issues page (Shantanu, PR [14581](https://github.com/python/mypy/pull/14581))
*   Add a top-level TypedDict page (Shantanu, PR [14584](https://github.com/python/mypy/pull/14584))
*   More improvements to getting started documentation (Shantanu, PR [14572](https://github.com/python/mypy/pull/14572))
*   Move truthy-function documentation from “optional checks” to “enabled by default” (Anders Kaseorg, PR [14380](https://github.com/python/mypy/pull/14380))
*   Avoid use of implicit optional in decorator factory documentation (Tom Schraitle, PR [14156](https://github.com/python/mypy/pull/14156))
*   Clarify documentation surrounding install-types (Shantanu, PR [14003](https://github.com/python/mypy/pull/14003))
*   Improve searchability for module level type ignore errors (Shantanu, PR [14342](https://github.com/python/mypy/pull/14342))
*   Advertise mypy daemon in README (Ivan Levkivskyi, PR [14248](https://github.com/python/mypy/pull/14248))
*   Add link to error codes in README (Ivan Levkivskyi, PR [14249](https://github.com/python/mypy/pull/14249))
*   Document that report generation disables cache (Ilya Konstantinov, PR [14402](https://github.com/python/mypy/pull/14402))
*   Stop saying mypy is beta software (Ivan Levkivskyi, PR [14251](https://github.com/python/mypy/pull/14251))
*   Flycheck-mypy is deprecated, since its functionality was merged to Flycheck (Ivan Levkivskyi, PR [14247](https://github.com/python/mypy/pull/14247))
*   Update code example in "Declaring decorators" (ChristianWitzler, PR [14131](https://github.com/python/mypy/pull/14131))

### Stubtest Improvements

Stubtest is a tool for testing that stubs conform to the implementations.

*   Improve error message for `__all__`\-related errors (Alex Waygood, PR [14362](https://github.com/python/mypy/pull/14362))
*   Improve heuristics for determining whether global-namespace names are imported (Alex Waygood, PR [14270](https://github.com/python/mypy/pull/14270))
*   Catch BaseException on module imports (Shantanu, PR [14284](https://github.com/python/mypy/pull/14284))
*   Associate exported symbol error with `__all__` object\_path (Nikita Sobolev, PR [14217](https://github.com/python/mypy/pull/14217))
*   Add \_\_warningregistry\_\_ to the list of ignored module dunders (Nikita Sobolev, PR [14218](https://github.com/python/mypy/pull/14218))
*   If a default is present in the stub, check that it is correct (Jelle Zijlstra, PR [14085](https://github.com/python/mypy/pull/14085))

### Stubgen Improvements

Stubgen is a tool for automatically generating draft stubs for libraries.

*   Treat dlls as C modules (Shantanu, PR [14503](https://github.com/python/mypy/pull/14503))

### Other Notable Fixes and Improvements

*   Update stub suggestions based on recent typeshed changes (Alex Waygood, PR [14265](https://github.com/python/mypy/pull/14265))
*   Fix attrs protocol check with cache (Marc Mueller, PR [14558](https://github.com/python/mypy/pull/14558))
*   Fix strict equality check if operand item type has custom \_\_eq\_\_ (Jukka Lehtosalo, PR [14513](https://github.com/python/mypy/pull/14513))
*   Don't consider object always truthy (Jukka Lehtosalo, PR [14510](https://github.com/python/mypy/pull/14510))
*   Properly support union of TypedDicts as dict literal context (Ivan Levkivskyi, PR [14505](https://github.com/python/mypy/pull/14505))
*   Properly expand type in generic class with Self and TypeVar with values (Ivan Levkivskyi, PR [14491](https://github.com/python/mypy/pull/14491))
*   Fix recursive TypedDicts/NamedTuples defined with call syntax (Ivan Levkivskyi, PR [14488](https://github.com/python/mypy/pull/14488))
*   Fix type inference issue when a class inherits from Any (Shantanu, PR [14404](https://github.com/python/mypy/pull/14404))
*   Fix false positive on generic base class with six (Ivan Levkivskyi, PR [14478](https://github.com/python/mypy/pull/14478))
*   Don't read scripts without extensions as modules in namespace mode (Tim Geypens, PR [14335](https://github.com/python/mypy/pull/14335))
*   Fix inference for constrained type variables within unions (Christoph Tyralla, PR [14396](https://github.com/python/mypy/pull/14396))
*   Fix Unpack imported from typing (Marc Mueller, PR [14378](https://github.com/python/mypy/pull/14378))
*   Allow trailing commas in ini configuration of multiline values (Nikita Sobolev, PR [14240](https://github.com/python/mypy/pull/14240))
*   Fix false negatives involving Unions and generators or coroutines (Shantanu, PR [14224](https://github.com/python/mypy/pull/14224))
*   Fix ParamSpec constraint for types as callable (Vincent Vanlaer, PR [14153](https://github.com/python/mypy/pull/14153))
*   Fix type aliases with fixed-length tuples (Jukka Lehtosalo, PR [14184](https://github.com/python/mypy/pull/14184))
*   Fix issues with type aliases and new style unions (Jukka Lehtosalo, PR [14181](https://github.com/python/mypy/pull/14181))
*   Simplify unions less aggressively (Ivan Levkivskyi, PR [14178](https://github.com/python/mypy/pull/14178))
*   Simplify callable overlap logic (Ivan Levkivskyi, PR [14174](https://github.com/python/mypy/pull/14174))
*   Try empty context when assigning to union typed variables (Ivan Levkivskyi, PR [14151](https://github.com/python/mypy/pull/14151))
*   Improvements to recursive types (Ivan Levkivskyi, PR [14147](https://github.com/python/mypy/pull/14147))
*   Make non-numeric non-empty FORCE\_COLOR truthy (Shantanu, PR [14140](https://github.com/python/mypy/pull/14140))
*   Fix to recursive type aliases (Ivan Levkivskyi, PR [14136](https://github.com/python/mypy/pull/14136))
*   Correctly handle Enum name on Python 3.11 (Ivan Levkivskyi, PR [14133](https://github.com/python/mypy/pull/14133))
*   Fix class objects falling back to metaclass for callback protocol (Ivan Levkivskyi, PR [14121](https://github.com/python/mypy/pull/14121))
*   Correctly support self types in callable ClassVar (Ivan Levkivskyi, PR [14115](https://github.com/python/mypy/pull/14115))
*   Fix type variable clash in nested positions and in attributes (Ivan Levkivskyi, PR [14095](https://github.com/python/mypy/pull/14095))
*   Allow class variable as implementation for read only attribute (Ivan Levkivskyi, PR [14081](https://github.com/python/mypy/pull/14081))
*   Prevent warnings from causing dmypy to fail (Andrzej Bartosiński, PR [14102](https://github.com/python/mypy/pull/14102))
*   Correctly process nested definitions in mypy daemon (Ivan Levkivskyi, PR [14104](https://github.com/python/mypy/pull/14104))
*   Don't consider a branch unreachable if there is a possible promotion (Ivan Levkivskyi, PR [14077](https://github.com/python/mypy/pull/14077))
*   Fix incompatible overrides of overloaded methods in concrete subclasses (Shantanu, PR [14017](https://github.com/python/mypy/pull/14017))
*   Fix new style union syntax in type aliases (Jukka Lehtosalo, PR [14008](https://github.com/python/mypy/pull/14008))
*   Fix and optimise overload compatibility checking (Shantanu, PR [14018](https://github.com/python/mypy/pull/14018))
*   Improve handling of redefinitions through imports (Shantanu, PR [13969](https://github.com/python/mypy/pull/13969))
*   Preserve (some) implicitly exported types (Shantanu, PR [13967](https://github.com/python/mypy/pull/13967))

### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=ea0ae2155e8a04c9837903c3aff8dd5ad5f36ebc+0&branch=main&path=stdlib) for full list of typeshed changes.

### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Alessio Izzo
*   Alex Waygood
*   Anders Kaseorg
*   Andrzej Bartosiński
*   Avasam
*   ChristianWitzler
*   Christoph Tyralla
*   dosisod
*   Harrison McCarty
*   Hugo van Kemenade
*   Hugues
*   Ilya Konstantinov
*   Ivan Levkivskyi
*   Jelle Zijlstra
*   jhance
*   johnthagen
*   Jonathan Daniel
*   Joshua Bronson
*   Jukka Lehtosalo
*   KotlinIsland
*   Lakshay Bisht
*   Lefteris Karapetsas
*   Marc Mueller
*   Matthew Hughes
*   Michael Lee
*   Nick Drozd
*   Nikita Sobolev
*   Richard Si
*   Shantanu
*   Stas Ilinskiy
*   Tim Geypens
*   Tin Tvrtković
*   Tom Schraitle
*   Valentin Stanciu
*   Vincent Vanlaer

We’d also like to thank our employer, Dropbox, for funding the mypy core team.

Posted by Stas Ilinskiy

## Previous releases

For information about previous releases, refer to the posts at https://mypy-lang.blogspot.com/
