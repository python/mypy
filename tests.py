from unittest import Suite, run_test
import testlex
import testparse


class AllSuite(Suite):
    def __init__(self):
        self.test_lex = testlex.LexerSuite()
        self.test_parse = testparse.ParserSuite()
        super().__init__()


run_test(AllSuite())
