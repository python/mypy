"""Classes for producing HTML reports about imprecision."""

from __future__ import annotations

import collections
import itertools
import json
import os
import shutil
import sys
import sysconfig
import time
import tokenize
from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Iterator
from operator import attrgetter
from typing import Any, Final, TypeAlias as _TypeAlias
from urllib.request import pathname2url

from mypy import stats
from mypy.defaults import REPORTER_NAMES
from mypy.nodes import Expression, FuncDef, MypyFile
from mypy.options import Options
from mypy.traverser import TraverserVisitor
from mypy.types import Type, TypeOfAny
from mypy.version import __version__

try:
    if sys.version_info >= (3, 14) and bool(sysconfig.get_config_var("Py_GIL_DISABLED")):
        # lxml doesn't support free-threading yet
        LXML_INSTALLED = False
    else:
        from lxml import etree  # type: ignore[import-untyped]

        LXML_INSTALLED = True
except ImportError:
    LXML_INSTALLED = False

type_of_any_name_map: Final[collections.OrderedDict[int, str]] = collections.OrderedDict(
    [
        (TypeOfAny.unannotated, "Unannotated"),
        (TypeOfAny.explicit, "Explicit"),
        (TypeOfAny.from_unimported_type, "Unimported"),
        (TypeOfAny.from_omitted_generics, "Omitted Generics"),
        (TypeOfAny.from_error, "Error"),
        (TypeOfAny.special_form, "Special Form"),
        (TypeOfAny.implementation_artifact, "Implementation Artifact"),
    ]
)

type_of_any_color_map: Final[collections.OrderedDict[int, str]] = collections.OrderedDict(
    [
        (TypeOfAny.unannotated, "red"),
        (TypeOfAny.explicit, "blue"),
        (TypeOfAny.from_unimported_type, "purple"),
        (TypeOfAny.from_omitted_generics, "yellow"),
        (TypeOfAny.from_error, "orange"),
        (TypeOfAny.special_form, "pink"),
        (TypeOfAny.implementation_artifact, "gray"),
    ]
)


class FileInfo:
    def __init__(self, path: str, module: str) -> None:
        self.path = path
        self.module = module
        self.counts: list[int] = [0] * len(stats.TYPE_NAMES)

    def total(self) -> int:
        return sum(self.counts)


def iterate_python_lines(path: str) -> Iterator[tuple[int, str]]:
    with open(path, encoding="utf-8") as f:
        try:
            tokens = tokenize.generate_tokens(f.readline)
            current_line = 0
            for tok_type, tok_str, (start_line, _), (end_line, _), line in tokens:
                if start_line > current_line:
                    current_line = start_line
                    yield start_line, line
        except tokenize.TokenError:
            pass


def should_skip_path(path: str) -> bool:
    return path.startswith(("..", "/", "\\")) or os.path.isabs(path)


reporter_classes: dict[str, type[AbstractReporter]] = {}


def register_reporter(
    name: str, reporter_cls: type[AbstractReporter], needs_lxml: bool = False
) -> None:
    if needs_lxml and not LXML_INSTALLED:
        return
    reporter_classes[name] = reporter_cls


def alias_reporter(old_name: str, new_name: str) -> None:
    if old_name in reporter_classes:
        reporter_classes[new_name] = reporter_classes[old_name]


class Reports:
    def __init__(self, options: Options) -> None:
        self.options = options
        self.reporters: list[AbstractReporter] = []
        self.output_dirs: dict[str, str] = {}
        for report_type, output_dir in options.report_type.items():
            if report_type in reporter_classes:
                reporter_cls = reporter_classes[report_type]
                self.reporters.append(reporter_cls(self, output_dir))
                self.output_dirs[report_type] = output_dir

    def file(
        self,
        tree: MypyFile,
        modules: dict[str, MypyFile],
        type_map: dict[Expression, Type],
        options: Options,
    ) -> None:
        for reporter in self.reporters:
            reporter.on_file(tree, modules, type_map, options)

    def finish(self) -> None:
        for reporter in self.reporters:
            reporter.on_finish()


class AbstractReporter(metaclass=ABCMeta):
    def __init__(self, reports: Reports, output_dir: str) -> None:
        self.reports = reports
        self.output_dir = output_dir

    @abstractmethod
    def on_file(
        self,
        tree: MypyFile,
        modules: dict[str, MypyFile],
        type_map: dict[Expression, Type],
        options: Options,
    ) -> None:
        pass

    @abstractmethod
    def on_finish(self) -> None:
        pass


class AbstractXmlReporter(AbstractReporter):
    def __init__(self, reports: Reports, output_dir: str) -> None:
        super().__init__(reports, output_dir)
        self.memory_xml = MemoryXmlReporter(reports, output_dir)


class MemoryXmlReporter(AbstractReporter):
    def __init__(self, reports: Reports, output_dir: str) -> None:
        super().__init__(reports, output_dir)
        self.last_xml: Any = None
        self.xslt_html_path = os.path.join(output_dir, "mypy-html.xslt")
        self.xslt_txt_path = os.path.join(output_dir, "mypy-txt.xslt")
        self.css_html_path = os.path.join(output_dir, "mypy-html.css")

    def on_file(
        self,
        tree: MypyFile,
        modules: dict[str, MypyFile],
        type_map: dict[Expression, Type],
        options: Options,
    ) -> None:
        pass

    def on_finish(self) -> None:
        pass


class XsltHtmlReporter(AbstractXmlReporter):
    def __init__(self, reports: Reports, output_dir: str) -> None:
        super().__init__(reports, output_dir)
        if LXML_INSTALLED:
            self.xslt_html = etree.XSLT(etree.parse(self.memory_xml.xslt_html_path))
            self.param_html = etree.XSLT.strparam("html")

    def on_file(
        self,
        tree: MypyFile,
        modules: dict[str, MypyFile],
        type_map: dict[Expression, Type],
        options: Options,
    ) -> None:
        pass

    def on_finish(self) -> None:
        if not LXML_INSTALLED:
            return
        last_xml = self.memory_xml.last_xml
        assert last_xml is not None
        out_path = os.path.join(self.output_dir, "index.html")
        out_css = os.path.join(self.output_dir, "mypy-html.css")
        transformed_html = bytes(self.xslt_html(last_xml, ext=self.param_html))
        with open(out_path, "wb") as out_file:
            out_file.write(transformed_html)
        shutil.copyfile(self.memory_xml.css_html_path, out_css)
        print("Generated HTML report (via XSLT):", os.path.abspath(out_path))


register_reporter("xslt-html", XsltHtmlReporter, needs_lxml=True)


class XsltTxtReporter(AbstractXmlReporter):
    def __init__(self, reports: Reports, output_dir: str) -> None:
        super().__init__(reports, output_dir)
        if LXML_INSTALLED:
            self.xslt_txt = etree.XSLT(etree.parse(self.memory_xml.xslt_txt_path))

    def on_file(
        self,
        tree: MypyFile,
        modules: dict[str, MypyFile],
        type_map: dict[Expression, Type],
        options: Options,
    ) -> None:
        pass

    def on_finish(self) -> None:
        if not LXML_INSTALLED:
            return
        last_xml = self.memory_xml.last_xml
        assert last_xml is not None
        out_path = os.path.join(self.output_dir, "index.txt")
        transformed_txt = bytes(self.xslt_txt(last_xml))
        with open(out_path, "wb") as out_file:
            out_file.write(transformed_txt)
        print("Generated TXT report (via XSLT):", os.path.abspath(out_path))


register_reporter("xslt-txt", XsltTxtReporter, needs_lxml=True)

alias_reporter("xslt-html", "html")
alias_reporter("xslt-txt", "txt")


class LinePrecisionReporter(AbstractReporter):
    def __init__(self, reports: Reports, output_dir: str) -> None:
        super().__init__(reports, output_dir)
        self.files: list[FileInfo] = []

    def on_file(
        self,
        tree: MypyFile,
        modules: dict[str, MypyFile],
        type_map: dict[Expression, Type],
        options: Options,
    ) -> None:
        try:
            path = os.path.relpath(tree.path)
        except ValueError:
            return

        if should_skip_path(path):
            return

        visitor = stats.StatisticsVisitor(
            inferred=True,
            filename=tree.fullname,
            modules=modules,
            typemap=type_map,
            all_nodes=True,
        )
        tree.accept(visitor)

        file_info = FileInfo(path, tree._fullname)
        for lineno, _ in iterate_python_lines(path):
            status = visitor.line_map.get(lineno, stats.TYPE_EMPTY)
            file_info.counts[status] += 1

        self.files.append(file_info)

    def on_finish(self) -> None:
        if not self.files:
            return
        output_files = sorted(self.files, key=lambda x: x.module)
        report_file = os.path.join(self.output_dir, "lineprecision.txt")
        width = max(4, max(len(info.module) for info in output_files))
        titles = ("Lines", "Precise", "Imprecise", "Any", "Empty", "Unanalyzed")
        widths = (width,) + tuple(len(t) for t in titles)
        fmt = "{:%d}  {:%d}  {:%d}  {:%d}  {:%d}  {:%d}  {:%d}\n" % widths
        with open(report_file, "w") as f:
            f.write(fmt.format("Name", *titles))
            f.write("-" * (width + 51) + "\n")
            for file_info in output_files:
                counts = file_info.counts
                f.write(
                    fmt.format(
                        file_info.module.ljust(width),
                        file_info.total(),
                        counts[stats.TYPE_PRECISE],
                        counts[stats.TYPE_IMPRECISE],
                        counts[stats.TYPE_ANY],
                        counts[stats.TYPE_EMPTY],
                        counts[stats.TYPE_UNANALYZED],
                    )
                )


register_reporter("lineprecision", LinePrecisionReporter)


class SarifReporter(AbstractReporter):
    """SARIF (Static Analysis Results Interchange Format) v2.1.0 report generator."""

    def __init__(self, reports: Reports, output_dir: str) -> None:
        super().__init__(reports, output_dir)

    def on_file(
        self,
        tree: MypyFile,
        modules: dict[str, MypyFile],
        type_map: dict[Expression, Type],
        options: Options,
    ) -> None:
        pass

    def on_finish(self) -> None:
        out_path = os.path.join(self.output_dir, "mypy-report.sarif")
        sarif_data = {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "mypy",
                            "version": __version__,
                            "informationUri": "https://mypy-lang.org/",
                        }
                    },
                    "results": [],
                }
            ],
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(sarif_data, f, indent=2)


register_reporter("sarif", SarifReporter)
