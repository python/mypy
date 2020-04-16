# TESTING mypy
The basic way to run all tests:

    $ pip3 install -r test-requirements.txt
    $ python2 -m pip install -U typing
    $ ./runtests.py

Mypy is tested using `pytest`. This can be installed as shown above, using `test-requirements.txt`. In essence, there are multiple kinds of tests for mypy:
- Unit tests (Found under `./mypy/test/`, [example](mypy/test/testapi.py))
- Data-driven unit and integration tests (Found under `./mypy/test/`, [example pep561](mypy/test/testpep561.py))

As might be clear, some tests are driven by data. For now, this data resides in `./test-data/unit/`. Do note: this syntax of these data-driven tests is parsed by Python test-cases in `./mypy/test/` by specifying the `files=[]` property. Some test files specify their own conditions on the tests (input data, flags, etc.). For more information about the syntax, read the next section.

Such a data-driven test can look like:

```
class PEP561Suite(DataSuite):
    files = ['pep561.test'] # Specify the list of test data files

    def run_case(self, test_case: DataDrivenTestCase) -> None:
        test_pep561(test_case) # Run test (and parse test-file)
```

# Data-driven tests
For more on the data-driven tests, such as how to write tests and how to control
which tests to run, see [Test README.md](test-data/unit/README.md).