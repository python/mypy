"""This file exists as a temporary measure, and will be removed when new
semantic analyzer is the default one.
"""
MYPY = False
if MYPY:
    from typing_extensions import Final

# Files to not run with new semantic analyzer.
new_semanal_blacklist = [
    'check-async-await.test',
    'check-classes.test',
    'check-custom-plugin.test',
    'check-dataclasses.test',
    'check-enum.test',
    'check-expressions.test',
    'check-flags.test',
    'check-functions.test',
    'check-incremental.test',
    'check-literal.test',
    'check-modules.test',
    'check-newtype.test',
    'check-overloading.test',
    'check-protocols.test',
    'check-python2.test',
    'check-semanal-error.test',
    'check-statements.test',
    'check-unions.test',
    'check-unreachable-code.test',
    'semanal-errors.test',
]  # type: Final
