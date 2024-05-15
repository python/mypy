from __future__ import annotations

import sys
from typing import TypeVar
from typing_extensions import assert_type

if sys.version_info >= (3, 11):
    # This can be removed later, but right now Flake8 does not know
    # about these two classes:
    from builtins import BaseExceptionGroup, ExceptionGroup

    # BaseExceptionGroup
    # ==================
    # `BaseExceptionGroup` can work with `BaseException`:
    beg = BaseExceptionGroup("x", [SystemExit(), SystemExit()])
    assert_type(beg, BaseExceptionGroup[SystemExit])
    assert_type(beg.exceptions, tuple[SystemExit | BaseExceptionGroup[SystemExit], ...])

    # Covariance works:
    _beg1: BaseExceptionGroup[BaseException] = beg

    # `BaseExceptionGroup` can work with `Exception`:
    beg2 = BaseExceptionGroup("x", [ValueError()])
    # FIXME: this is not right, runtime returns `ExceptionGroup` instance instead,
    # but I am unable to represent this with types right now.
    assert_type(beg2, BaseExceptionGroup[ValueError])

    # .subgroup()
    # -----------

    assert_type(beg.subgroup(KeyboardInterrupt), BaseExceptionGroup[KeyboardInterrupt] | None)
    assert_type(beg.subgroup((KeyboardInterrupt,)), BaseExceptionGroup[KeyboardInterrupt] | None)

    def is_base_exc(exc: BaseException) -> bool:
        return isinstance(exc, BaseException)

    def is_specific(exc: SystemExit | BaseExceptionGroup[SystemExit]) -> bool:
        return isinstance(exc, SystemExit)

    # This one does not have `BaseExceptionGroup` part,
    # this is why we treat as an error.
    def is_system_exit(exc: SystemExit) -> bool:
        return isinstance(exc, SystemExit)

    def unrelated_subgroup(exc: KeyboardInterrupt) -> bool:
        return False

    assert_type(beg.subgroup(is_base_exc), BaseExceptionGroup[SystemExit] | None)
    assert_type(beg.subgroup(is_specific), BaseExceptionGroup[SystemExit] | None)
    beg.subgroup(is_system_exit)  # type: ignore
    beg.subgroup(unrelated_subgroup)  # type: ignore

    # `Exception`` subgroup returns `ExceptionGroup`:
    assert_type(beg.subgroup(ValueError), ExceptionGroup[ValueError] | None)
    assert_type(beg.subgroup((ValueError,)), ExceptionGroup[ValueError] | None)

    # Callable are harder, we don't support cast to `ExceptionGroup` here.
    # Because callables might return `True` the first time. And `BaseExceptionGroup`
    # will stick, no matter what arguments are.

    def is_exception(exc: Exception) -> bool:
        return isinstance(exc, Exception)

    def is_exception_or_beg(exc: Exception | BaseExceptionGroup[SystemExit]) -> bool:
        return isinstance(exc, Exception)

    # This is an error because of the `Exception` argument type,
    # while `SystemExit` is needed instead.
    beg.subgroup(is_exception_or_beg)  # type: ignore

    # This is an error, because `BaseExceptionGroup` is not an `Exception`
    # subclass. It is required.
    beg.subgroup(is_exception)  # type: ignore

    # .split()
    # --------

    assert_type(
        beg.split(KeyboardInterrupt), tuple[BaseExceptionGroup[KeyboardInterrupt] | None, BaseExceptionGroup[SystemExit] | None]
    )
    assert_type(
        beg.split((KeyboardInterrupt,)),
        tuple[BaseExceptionGroup[KeyboardInterrupt] | None, BaseExceptionGroup[SystemExit] | None],
    )
    assert_type(
        beg.split(ValueError),  # there are no `ValueError` items in there, but anyway
        tuple[ExceptionGroup[ValueError] | None, BaseExceptionGroup[SystemExit] | None],
    )

    excs_to_split: list[ValueError | KeyError | SystemExit] = [ValueError(), KeyError(), SystemExit()]
    to_split = BaseExceptionGroup("x", excs_to_split)
    assert_type(to_split, BaseExceptionGroup[ValueError | KeyError | SystemExit])

    # Ideally the first part should be `ExceptionGroup[ValueError]` (done)
    # and the second part should be `BaseExceptionGroup[KeyError | SystemExit]`,
    # but we cannot subtract type from a union.
    # We also cannot change `BaseExceptionGroup` to `ExceptionGroup` even if needed
    # in the second part here because of that.
    assert_type(
        to_split.split(ValueError),
        tuple[ExceptionGroup[ValueError] | None, BaseExceptionGroup[ValueError | KeyError | SystemExit] | None],
    )

    def split_callable1(exc: ValueError | KeyError | SystemExit | BaseExceptionGroup[ValueError | KeyError | SystemExit]) -> bool:
        return True

    assert_type(
        to_split.split(split_callable1),  # Concrete type is ok
        tuple[
            BaseExceptionGroup[ValueError | KeyError | SystemExit] | None,
            BaseExceptionGroup[ValueError | KeyError | SystemExit] | None,
        ],
    )
    assert_type(
        to_split.split(is_base_exc),  # Base class is ok
        tuple[
            BaseExceptionGroup[ValueError | KeyError | SystemExit] | None,
            BaseExceptionGroup[ValueError | KeyError | SystemExit] | None,
        ],
    )
    # `Exception` cannot be used: `BaseExceptionGroup` is not a subtype of it.
    to_split.split(is_exception)  # type: ignore

    # .derive()
    # ---------

    assert_type(beg.derive([ValueError()]), ExceptionGroup[ValueError])
    assert_type(beg.derive([KeyboardInterrupt()]), BaseExceptionGroup[KeyboardInterrupt])

    # ExceptionGroup
    # ==============

    # `ExceptionGroup` can work with `Exception`:
    excs: list[ValueError | KeyError] = [ValueError(), KeyError()]
    eg = ExceptionGroup("x", excs)
    assert_type(eg, ExceptionGroup[ValueError | KeyError])
    assert_type(eg.exceptions, tuple[ValueError | KeyError | ExceptionGroup[ValueError | KeyError], ...])

    # Covariance works:
    _eg1: ExceptionGroup[Exception] = eg

    # `ExceptionGroup` cannot work with `BaseException`:
    ExceptionGroup("x", [SystemExit()])  # type: ignore

    # .subgroup()
    # -----------

    # Our decision is to ban cases like::
    #
    #   >>> eg = ExceptionGroup('x', [ValueError()])
    #   >>> eg.subgroup(BaseException)
    #   ExceptionGroup('e', [ValueError()])
    #
    # are possible in runtime.
    # We do it because, it does not make sense for all other base exception types.
    # Supporting just `BaseException` looks like an overkill.
    eg.subgroup(BaseException)  # type: ignore
    eg.subgroup((KeyboardInterrupt, SystemExit))  # type: ignore

    assert_type(eg.subgroup(Exception), ExceptionGroup[Exception] | None)
    assert_type(eg.subgroup(ValueError), ExceptionGroup[ValueError] | None)
    assert_type(eg.subgroup((ValueError,)), ExceptionGroup[ValueError] | None)

    def subgroup_eg1(exc: ValueError | KeyError | ExceptionGroup[ValueError | KeyError]) -> bool:
        return True

    def subgroup_eg2(exc: ValueError | KeyError) -> bool:
        return True

    assert_type(eg.subgroup(subgroup_eg1), ExceptionGroup[ValueError | KeyError] | None)
    assert_type(eg.subgroup(is_exception), ExceptionGroup[ValueError | KeyError] | None)
    assert_type(eg.subgroup(is_base_exc), ExceptionGroup[ValueError | KeyError] | None)
    assert_type(eg.subgroup(is_base_exc), ExceptionGroup[ValueError | KeyError] | None)

    # Does not have `ExceptionGroup` part:
    eg.subgroup(subgroup_eg2)  # type: ignore

    # .split()
    # --------

    assert_type(eg.split(TypeError), tuple[ExceptionGroup[TypeError] | None, ExceptionGroup[ValueError | KeyError] | None])
    assert_type(eg.split((TypeError,)), tuple[ExceptionGroup[TypeError] | None, ExceptionGroup[ValueError | KeyError] | None])
    assert_type(
        eg.split(is_exception), tuple[ExceptionGroup[ValueError | KeyError] | None, ExceptionGroup[ValueError | KeyError] | None]
    )
    assert_type(
        eg.split(is_base_exc),
        # is not converted, because `ExceptionGroup` cannot have
        # direct `BaseException` subclasses inside.
        tuple[ExceptionGroup[ValueError | KeyError] | None, ExceptionGroup[ValueError | KeyError] | None],
    )

    # It does not include `ExceptionGroup` itself, so it will fail:
    def value_or_key_error(exc: ValueError | KeyError) -> bool:
        return isinstance(exc, (ValueError, KeyError))

    eg.split(value_or_key_error)  # type: ignore

    # `ExceptionGroup` cannot have direct `BaseException` subclasses inside.
    eg.split(BaseException)  # type: ignore
    eg.split((SystemExit, GeneratorExit))  # type: ignore

    # .derive()
    # ---------

    assert_type(eg.derive([ValueError()]), ExceptionGroup[ValueError])
    assert_type(eg.derive([KeyboardInterrupt()]), BaseExceptionGroup[KeyboardInterrupt])

    # BaseExceptionGroup Custom Subclass
    # ==================================
    # In some cases `Self` type can be preserved in runtime,
    # but it is impossible to express. That's why we always fallback to
    # `BaseExceptionGroup` and `ExceptionGroup`.

    _BE = TypeVar("_BE", bound=BaseException)

    class CustomBaseGroup(BaseExceptionGroup[_BE]): ...

    cb1 = CustomBaseGroup("x", [SystemExit()])
    assert_type(cb1, CustomBaseGroup[SystemExit])
    cb2 = CustomBaseGroup("x", [ValueError()])
    assert_type(cb2, CustomBaseGroup[ValueError])

    # .subgroup()
    # -----------

    assert_type(cb1.subgroup(KeyboardInterrupt), BaseExceptionGroup[KeyboardInterrupt] | None)
    assert_type(cb2.subgroup((KeyboardInterrupt,)), BaseExceptionGroup[KeyboardInterrupt] | None)

    assert_type(cb1.subgroup(ValueError), ExceptionGroup[ValueError] | None)
    assert_type(cb2.subgroup((KeyError,)), ExceptionGroup[KeyError] | None)

    def cb_subgroup1(exc: SystemExit | CustomBaseGroup[SystemExit]) -> bool:
        return True

    def cb_subgroup2(exc: ValueError | CustomBaseGroup[ValueError]) -> bool:
        return True

    assert_type(cb1.subgroup(cb_subgroup1), BaseExceptionGroup[SystemExit] | None)
    assert_type(cb2.subgroup(cb_subgroup2), BaseExceptionGroup[ValueError] | None)
    cb1.subgroup(cb_subgroup2)  # type: ignore
    cb2.subgroup(cb_subgroup1)  # type: ignore

    # .split()
    # --------

    assert_type(
        cb1.split(KeyboardInterrupt), tuple[BaseExceptionGroup[KeyboardInterrupt] | None, BaseExceptionGroup[SystemExit] | None]
    )
    assert_type(cb1.split(TypeError), tuple[ExceptionGroup[TypeError] | None, BaseExceptionGroup[SystemExit] | None])
    assert_type(cb2.split((TypeError,)), tuple[ExceptionGroup[TypeError] | None, BaseExceptionGroup[ValueError] | None])

    def cb_split1(exc: SystemExit | CustomBaseGroup[SystemExit]) -> bool:
        return True

    def cb_split2(exc: ValueError | CustomBaseGroup[ValueError]) -> bool:
        return True

    assert_type(cb1.split(cb_split1), tuple[BaseExceptionGroup[SystemExit] | None, BaseExceptionGroup[SystemExit] | None])
    assert_type(cb2.split(cb_split2), tuple[BaseExceptionGroup[ValueError] | None, BaseExceptionGroup[ValueError] | None])
    cb1.split(cb_split2)  # type: ignore
    cb2.split(cb_split1)  # type: ignore

    # .derive()
    # ---------

    # Note, that `Self` type is not preserved in runtime.
    assert_type(cb1.derive([ValueError()]), ExceptionGroup[ValueError])
    assert_type(cb1.derive([KeyboardInterrupt()]), BaseExceptionGroup[KeyboardInterrupt])
    assert_type(cb2.derive([ValueError()]), ExceptionGroup[ValueError])
    assert_type(cb2.derive([KeyboardInterrupt()]), BaseExceptionGroup[KeyboardInterrupt])

    # ExceptionGroup Custom Subclass
    # ==============================

    _E = TypeVar("_E", bound=Exception)

    class CustomGroup(ExceptionGroup[_E]): ...

    CustomGroup("x", [SystemExit()])  # type: ignore
    cg1 = CustomGroup("x", [ValueError()])
    assert_type(cg1, CustomGroup[ValueError])

    # .subgroup()
    # -----------

    cg1.subgroup(BaseException)  # type: ignore
    cg1.subgroup((KeyboardInterrupt, SystemExit))  # type: ignore

    assert_type(cg1.subgroup(ValueError), ExceptionGroup[ValueError] | None)
    assert_type(cg1.subgroup((KeyError,)), ExceptionGroup[KeyError] | None)

    def cg_subgroup1(exc: ValueError | CustomGroup[ValueError]) -> bool:
        return True

    def cg_subgroup2(exc: ValueError) -> bool:
        return True

    assert_type(cg1.subgroup(cg_subgroup1), ExceptionGroup[ValueError] | None)
    cg1.subgroup(cb_subgroup2)  # type: ignore

    # .split()
    # --------

    assert_type(cg1.split(TypeError), tuple[ExceptionGroup[TypeError] | None, ExceptionGroup[ValueError] | None])
    assert_type(cg1.split((TypeError,)), tuple[ExceptionGroup[TypeError] | None, ExceptionGroup[ValueError] | None])
    cg1.split(BaseException)  # type: ignore

    def cg_split1(exc: ValueError | CustomGroup[ValueError]) -> bool:
        return True

    def cg_split2(exc: ValueError) -> bool:
        return True

    assert_type(cg1.split(cg_split1), tuple[ExceptionGroup[ValueError] | None, ExceptionGroup[ValueError] | None])
    cg1.split(cg_split2)  # type: ignore

    # .derive()
    # ---------

    # Note, that `Self` type is not preserved in runtime.
    assert_type(cg1.derive([ValueError()]), ExceptionGroup[ValueError])
    assert_type(cg1.derive([KeyboardInterrupt()]), BaseExceptionGroup[KeyboardInterrupt])
