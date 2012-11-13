from unittest import Suite, run_test
import testlex
import testparse
import testparseerr
import testsemanal
import sys


class AllSuite(Suite):
    def __init__(self):
        self.test_lex = testlex.LexerSuite()
        self.test_parse = testparse.ParserSuite()
        self.test_parse_errors = testparseerr.ParseErrorSuite()
        self.test_semanal = testsemanal.SemAnalSuite()
        self.test_semanal_errors = testsemanal.SemAnalErrorSuite()
        self.test_semanal_symtable = testsemanal.SemAnalSymtableSuite()
        self.test_semanal_typeinfos = testsemanal.SemAnalTypeInfoSuite()
        super().__init__()


run_test(AllSuite(), sys.argv[1:])
