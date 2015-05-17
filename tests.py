import sys

import typing

from mypy.myunit import Suite, run_test
from mypy.test import testtypes
from mypy.test import testsubtypes
from mypy.test import testsolve
from mypy.test import testinfer
from mypy.test import testlex
from mypy.test import testparse
from mypy.test import testsemanal
from mypy.test import testtransform
from mypy.test import testcheck
from mypy.test import testtypegen
from mypy.test import teststubgen


class AllSuite(Suite):
    def __init__(self):
        self.test_types = testtypes.TypesSuite()
        self.test_typeops = testtypes.TypeOpsSuite()
        self.test_join = testtypes.JoinSuite()
        self.test_meet = testtypes.MeetSuite()
        self.test_subtypes = testsubtypes.SubtypingSuite()
        self.test_solve = testsolve.SolveSuite()
        self.test_infer = testinfer.MapActualsToFormalsSuite()
        self.test_lex = testlex.LexerSuite()
        self.test_parse = testparse.ParserSuite()
        self.test_parse_errors = testparse.ParseErrorSuite()
        self.test_semanal = testsemanal.SemAnalSuite()
        self.test_semanal_errors = testsemanal.SemAnalErrorSuite()
        self.test_semanal_symtable = testsemanal.SemAnalSymtableSuite()
        self.test_semanal_typeinfos = testsemanal.SemAnalTypeInfoSuite()
        self.test_transform = testtransform.TransformSuite()
        self.test_check = testcheck.TypeCheckSuite()
        self.test_typegen = testtypegen.TypeExportSuite()
        self.test_stubgen = teststubgen.StubgenSuite()
        super().__init__()


if __name__ == '__main__':
    run_test(AllSuite(), sys.argv[1:])
