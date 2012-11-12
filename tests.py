from unittest import Suite, run_test
import testlex
import testparse
import testparseerr
import sys


class AllSuite(Suite):
    def __init__(self):
        self.test_lex = testlex.LexerSuite()
        self.test_parse = testparse.ParserSuite()
        self.test_parse_errors = testparseerr.ParseErrorSuite()
        super().__init__()


run_test(AllSuite(), sys.argv[1:])
