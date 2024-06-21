import sys
from mypy.test.helpers import Suite
from mypy.config_parser import (str_or_array_as_list, branch_coverage_str_or_array_as_list,
                                convert_to_boolean, branch_coverage_convert_to_boolean)

def print_coverage(branch_coverage):
    total_branches = len(branch_coverage)
    print(f"Total number of branches: {total_branches}\n")
    print("Results:")
    for branch, hit in branch_coverage.items():
        print(f"{branch} was {'hit' if hit else 'not hit'}")
    num_branches_hit = sum(branch_coverage.values())
    print(f"\nNumber of branches hit: {num_branches_hit}")
    print(f"Total branch coverage: {num_branches_hit / total_branches * 100}%")

class StrOrArrayAsListSuite(Suite):
    def test_str_or_array_as_list(self):
        original_stdout = sys.stdout
        with open('test_str_or_array_as_list.txt', 'w') as f:
            sys.stdout = f
            try:
                assert str_or_array_as_list('') == []
                assert str_or_array_as_list(' ') == []
                assert str_or_array_as_list('nonempty_string') == ['nonempty_string']
                assert str_or_array_as_list(' nonempty string to strip ') == ['nonempty string to strip']

                assert str_or_array_as_list([]) == []
                assert str_or_array_as_list(['', ' ', '\t']) == []
                assert str_or_array_as_list(['a', 'b', 'c']) == ['a', 'b', 'c']

                assert str_or_array_as_list(['a', '', ' ', 'b', '\t', 'c']) == ['a', 'b', 'c']
                assert str_or_array_as_list([' a ', ' b ', ' c ']) == ['a', 'b', 'c']

                assert str_or_array_as_list(('a', 'b', 'c')) == ['a', 'b', 'c']

                print("\nAll tests passed.\n")
                print("Coverage results:\n")
                print_coverage(branch_coverage_str_or_array_as_list)
            finally:
                sys.stdout = original_stdout

class ConvertToBooleanSuite(Suite):
    def test_convert_to_boolean(self):
        original_stdout = sys.stdout
        with open('test_convert_to_boolean.txt', 'w') as f:
            sys.stdout = f
            try:
                assert convert_to_boolean(True) == True
                assert convert_to_boolean(False) == False

                assert convert_to_boolean('True') == True
                assert convert_to_boolean('False') == False

                assert convert_to_boolean('yes') == True
                assert convert_to_boolean('no') == False

                assert convert_to_boolean('ON') == True
                assert convert_to_boolean('OFF') == False

                assert convert_to_boolean('1') == True
                assert convert_to_boolean('0') == False

                assert convert_to_boolean(1) == True
                assert convert_to_boolean(0) == False

                try:
                    convert_to_boolean('Invalid')
                except ValueError as e:
                    assert str(e) == 'Not a boolean: Invalid'

                try:
                    convert_to_boolean(2)
                except ValueError as e:
                    assert str(e) == 'Not a boolean: 2'

                print("All tests passed.")
                print("Coverage results:\n")
                print_coverage(branch_coverage_convert_to_boolean)
            finally:
                sys.stdout = original_stdout

