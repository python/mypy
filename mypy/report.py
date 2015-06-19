"""Classes for producing HTML reports about imprecision."""

from abc import ABCMeta, abstractmethod

from typing import Callable, Dict, List

from mypy.types import Type
from mypy.nodes import MypyFile, Node
from mypy import stats


reporter_classes = {} # type: Dict[str, Callable[[Reports, str], AbstractReporter]]


class Reports:
    def __init__(self, data_dir: str, report_dirs: Dict[str, str]) -> None:
        self.data_dir = data_dir
        self.reporters = [] # type: List[AbstractReporter]

        for report_type, report_dir in sorted(report_dirs.items()):
            self.add_report(report_type, report_dir)

    def add_report(self, report_type: str, report_dir: str) -> 'AbstractReporter':
        reporter_cls = reporter_classes[report_type]
        reporter = reporter_cls(self, report_dir)
        self.reporters.append(reporter)

    def file(self, tree: MypyFile, type_map: Dict[Node, Type]) -> None:
        for reporter in self.reporters:
            reporter.on_file(tree, type_map)

    def finish(self) -> None:
        for reporter in self.reporters:
            reporter.on_finish()


class AbstractReporter(metaclass=ABCMeta):
    def __init__(self, reports: Reports, output_dir: str) -> None:
        self.output_dir = output_dir

    @abstractmethod
    def on_file(self, tree: MypyFile, type_map: Dict[Node, Type]) -> None:
        pass

    @abstractmethod
    def on_finish(self) -> None:
        pass

class OldHtmlReporter(AbstractReporter):
    """Old HTML reporter.

    This just calls the old functions in `stats`, which use global
    variables to preserve state for the index.
    """

    def on_file(self, tree: MypyFile, type_map: Dict[Node, Type]) -> None:
        stats.generate_html_report(tree, tree.path, type_map, self.output_dir)

    def on_finish(self) -> None:
        stats.generate_html_index(self.output_dir)
reporter_classes['old-html'] = OldHtmlReporter

reporter_classes['html'] = reporter_classes['old-html']
