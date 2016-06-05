import os
import traceback
from mypy.myunit import SkipTestCaseException
from mypy.myunit import Suite
from mypy.myunit import assert_true

from mypy.test.config import test_data_prefix, test_temp_dir
from mypy.test.data import parse_test_cases, DataDrivenTestCase

from multiprocessing import Process, Queue
from queue import Empty


class AllEvalSuite(Suite):
    def cases(self):
        all_eval_files = [dir_entry.name
                          for dir_entry in os.scandir(test_data_prefix)
                          if '' == dir_entry.name[-5:]]
        c = []
        for f in all_eval_files:
            c += parse_test_cases(os.path.join(test_data_prefix, f),
                                  test_python_eval, test_temp_dir,
                                  optional_out=True)
        return c


def test_python_eval(testcase: DataDrivenTestCase) -> None:

    def run_code(testcase: DataDrivenTestCase, queue: Queue) -> None:
        code = '\n'.join(testcase.input)
        err = None
        try:
            codeobj = compile(code, 'pycode', 'exec')
            exec(codeobj, {}, {})
        except Exception:
            err = (testcase.file + ' ' + str(testcase.line),
                   traceback.format_exc())
        queue.put(err)

    queue = Queue()
    p = Process(target=run_code, args=(testcase, queue,))
    p.start()
    try:
        err = queue.get(timeout=1)
    except Empty:
        p.terminate()
        err = 'Timeout Error'

    assert_true(err is None, err)

if __name__ == '__main__':
    test_suite = AllEvalSuite()
    results = test_suite.cases()
    print(results)
    for index, result in enumerate(results):
        print(index)
        if index == 352:
            print(result)
        # if index == 353:
            # print(error)
        try:
            error = result.run()
        except SkipTestCaseException:
            pass
