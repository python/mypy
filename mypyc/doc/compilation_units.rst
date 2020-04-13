Compilation units
=================

When you run mypyc to compile a set of modules, these modules form a
*compilation unit*. Mypyc will use early binding for references within
the compilation unit.

If you run mypyc multiple times, each invocation will result in a
distinct compilation unit. Reference between separate compilation
units will fall back to late binding, i.e. looking up names using
Python namespace dictionaries. Also, all calls will use the slower
Python calling convention, where all argument and the return value
will be boxed (and potentially unboxed again in the called function).

For maximal performance, minimize the interactions across compilation
units. The simplest way to achieve this is to compile your entire
program as a single compilation unit.
