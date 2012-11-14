from unittest import Suite, run_test
import testtypes
import testsubtypes
import testlex
import testparse
import testsemanal
import testoutput
import testpythongen
import sys


class AllSuite(Suite):
    def __init__(self):
        self.test_types = testtypes.TypesSuite()
        self.test_lex = testlex.LexerSuite()
        self.test_parse = testparse.ParserSuite()
        self.test_parse_errors = testparse.ParseErrorSuite()
        self.test_semanal = testsemanal.SemAnalSuite()
        self.test_semanal_errors = testsemanal.SemAnalErrorSuite()
        self.test_semanal_symtable = testsemanal.SemAnalSymtableSuite()
        self.test_semanal_typeinfos = testsemanal.SemAnalTypeInfoSuite()
        self.test_output = testoutput.OutputSuite()
        self.test_pythongen = testpythongen.PythonGenerationSuite()
        self.test_subtypes = testsubtypes.SubtypingSuite()
        super().__init__()


run_test(AllSuite(), sys.argv[1:])
