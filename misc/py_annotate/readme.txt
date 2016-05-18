Sample use:

       python py_annotate.py --pep484 --diff testdata/simple.py testdata/simple.pyi

Regression tests:

testdata/foo.py  : input we want to annotate
testdata/foo.pyi : annotations we want to apply to foo.py (may be intentionally bad)

testdata/foo.nopyi.py   : expected output, ignoring pyi and inserting types as comments
testdata/foo.comment.py : expected output,    using pyi and inserting types as comments
testdata/foo.pep484.py  : expected output,    using pyi and inserting types in PEP484 style
