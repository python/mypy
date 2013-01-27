import sys

from myunit import Suite, run_test
import testtypes
import testsubtypes
import testsolve
import testinfer
import testlex
import testparse
import testsemanal
import testcheck
import testtypegen
import testoutput
import testpythongen
import testtransform
import testicodegen


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
        self.test_check = testcheck.TypeCheckSuite()
        self.test_typegen = testtypegen.TypeExportSuite()
        self.test_transform = testtransform.DyncheckTransformSuite()
        self.test_icodegen = testicodegen.IcodeGenerationSuite()
        self.test_output = testoutput.OutputSuite()
        self.test_pythongen = testpythongen.PythonGenerationSuite()
        super().__init__()


if __name__ == '__main__':
    run_test(AllSuite(), sys.argv[1:])
