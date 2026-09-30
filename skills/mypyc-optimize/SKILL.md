---
name: mypyc-optimize
description: Optimize Python source files that are compiled with mypyc (or
  will be compiled). Apply the performance-related changes from the
  mypyc-migrate skill, and improve type annotations so that mypyc can
  generate faster code.
---

# Optimize Python Code Compiled with Mypyc

This skill builds on the mypyc-migrate skill (`../mypyc-migrate/SKILL.md`).
Read that skill first; it has examples and details for the steps below.

Don't change behavior in significant ways. If an improvement would require
non-trivial refactoring or might change behavior, mention it in your summary
instead.

## Steps from the Migrate Skill

In the target files, make sure that all the changes described in the migrate
skill have been applied. These are especially important for performance:

* Annotate all constants in module top level and class bodies using `Final`
  (import from `typing`). Reading `Final` values is much faster than reading
  regular module-level variables. Don't make a value `Final` if any code or
  test reassigns it.
* Annotate all class variables using `ClassVar` (import from `typing`),
  unless they are already `Final`. Without `ClassVar`, mypyc treats a class
  variable as an instance attribute, which takes space in each instance.
* Add `@final` to classes that aren't intended to be subclassed (see the
  rules in the migrate skill).
* Move classes nested within functions or other classes to the module top
  level.
* Don't cache bound methods or global functions in local variables.

Also go through the compatibility checks in "Code That Won't Compile or Will
Break" in the migrate skill, and fix any issues.

## Improve Type Annotations

Precise type annotations let mypyc use fast, specialized operations. Values
with type `Any` and values in functions without annotations use slow,
generic operations.

* Add type annotations to functions that have missing annotations, including
  missing return type annotations (use `-> None` if a function doesn't return
  a value). A function without any annotations isn't type checked by mypy
  (when using default strictness options), and mypyc compiles it using generic
  operations.
* Replace `Any` types with precise types where possible. For example, use
  `list[str]` or `dict[str, int]` instead of `Any`, `list[Any]` or
  `dict[str, Any]` when the item types are known. Prefer concrete types such
  as `list[...]` over abstract types such as `Sequence[...]` when the concrete
  type is known.
* Annotate variables that get their value from untyped code (for example,
  a library without type annotations), so that the variable doesn't have type
  `Any`.

Only use a type if you are confident that it's correct. Compiled code checks
types at runtime and raises `TypeError` if a value has the wrong type (see
"Annotations Are Enforced at Runtime" in the migrate skill). Check callers,
including tests and non-compiled code, to make sure that they never pass
values of other types, such as `None`. Adding annotations to a function that
previously had none also causes mypy to type check its body; fix any new type
errors that this produces.
