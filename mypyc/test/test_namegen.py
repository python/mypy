import unittest

from mypyc.namegen import (
    NameGenerator, exported_name, candidate_suffixes, make_module_translation_map
)


class TestNameGen(unittest.TestCase):
    def test_candidate_suffixes(self) -> None:
        assert candidate_suffixes('foo') == ['', 'foo_']
        assert candidate_suffixes('foo.bar') == ['', 'bar_', 'foo_bar_']

    def test_exported_name(self) -> None:
        assert exported_name('foo') == 'foo'
        assert exported_name('foo.bar') == 'foo___bar'

    def test_make_module_translation_map(self) -> None:
        assert make_module_translation_map(
            ['foo', 'bar']) == {'foo': 'foo_', 'bar': 'bar_'}
        assert make_module_translation_map(
            ['foo.bar', 'foo.baz']) == {'foo.bar': 'bar_', 'foo.baz': 'baz_'}
        assert make_module_translation_map(
            ['zar', 'foo.bar', 'foo.baz']) == {'foo.bar': 'bar_',
                                               'foo.baz': 'baz_',
                                               'zar': 'zar_'}
        assert make_module_translation_map(
            ['foo.bar', 'fu.bar', 'foo.baz']) == {'foo.bar': 'foo_bar_',
                                                  'fu.bar': 'fu_bar_',
                                                  'foo.baz': 'baz_'}

    def test_name_generator(self) -> None:
        g = NameGenerator(['foo', 'foo.zar'])
        assert g.private_name('foo', 'f') == 'foo_f'
        assert g.private_name('foo', 'C.x.y') == 'foo_C_x_y'
        assert g.private_name('foo', 'C.x.y') == 'foo_C_x_y'
        assert g.private_name('foo.zar', 'C.x.y') == 'zar_C_x_y'
        assert g.private_name('foo', 'C.x_y') == 'foo_C_x_y_2'
        assert g.private_name('foo', 'C_x_y') == 'foo_C_x_y_3'
        assert g.private_name('foo', 'C_x_y') == 'foo_C_x_y_3'
