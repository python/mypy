"""Test cases for finding type annotations in docstrings."""

from mypy.myunit import Suite, assert_equal
from mypy.docstring import parse_docstring, scrubtype


class DocstringSuite(Suite):
    def test_scrubtype_basic(self):
        assert_equal(scrubtype('int'), 'int')
        assert_equal(scrubtype('FooBar'), 'FooBar')
        assert_equal(scrubtype('List[str]'), 'List[str]')

    def test_scrubtype_aliases(self):
        assert_equal(scrubtype('integer'), 'int')
        assert_equal(scrubtype('an integer'), 'int')
        assert_equal(scrubtype('dictionary'), 'Dict[Any, Any]')

    def test_scrubtype_patterns(self):
        assert_equal(scrubtype('list of integer'), 'List[int]')

    def test_scrubtype_patterns_known_only(self):

        def check(source, expected):
            assert_equal(scrubtype(source, only_known=True), expected)

        check('FooBar', None)
        check('a FooBar', None)
        check('int, int', None)

        check('None', 'None')
        check('str', 'str')
        check('Sequence[FooBar]', 'Sequence[FooBar]')
        check('an integer', 'int')
        check('list of integer', 'List[int]')

    def test_no_annotations(self):
        self.assert_no_annotation('')
        self.assert_no_annotation('''foo\

List[int] bar''')

    def test_full_annotation(self):
        self.assert_annotation('''Do something.

Args:
    x (int): An argument.
    y (bool): Another argument.
        More description.
    z (str): Last argument.

Returns:
    Dict[str, int]: A dictionary.

Raises:
    IOError: Something happened.
''', {'x': 'int', 'y': 'bool', 'z': 'str'}, 'Dict[str, int]')

    def test_partial_annotations(self):
        self.assert_annotation('''\
Args:
    x: list
    y (str): dict

Returns:
    status''', {'x': None, 'y': 'str'}, None)

    def test_generic_types(self):
        self.assert_annotation('''\
Args:
    x (List[int]): list
    y (MyDict[int, List[str]]): dict

Returns:
    bool: status''', {'x': 'List[int]', 'y': 'MyDict[int, List[str]]'}, 'bool')

    def test_simple_return_with_no_description(self):
        self.assert_annotation('''\
Args:
    x (an integer): a thing

Returns:
    an integer''', {'x': 'int'}, 'int')
        self.assert_annotation('''\
Args:
    x (int): a thing
Returns:
    FooBar''', {'x': 'int'}, None)

    def test_return_without_newline(self):
        self.assert_annotation('''\
Args:
    x (int): a thing
Returns:
    int''', {'x': 'int'}, 'int')

    def test_alternative_arg_headers(self):
        self.assert_annotation('''\
Arguments:
    x (int): a thing
Returns:
    int''', {'x': 'int'}, 'int')
        self.assert_annotation('''\
Params:
  x (int): a thing
Returns:
  int''', {'x': 'int'}, 'int')
        self.assert_no_annotation('''\
Parameters:
    x (int): a thing
Returns:
  int''')

    def test_only_args_no_return(self):
        self.assert_annotation('''\
Arguments:
    x (int): a thing''', {'x': 'int'}, None)

    def test_only_arg_type_no_description(self):
        self.assert_annotation('''\
Arguments:
    x (int)''', {'x': 'int'}, None)

    def assert_no_annotation(self, docstring):
        assert_equal(parse_docstring(docstring), None)

    def assert_annotation(self, docstring, args, rettype):
        parsed = parse_docstring(docstring)
        assert parsed is not None
        assert_equal(parsed.args, args)
        assert_equal(parsed.rettype, rettype)
