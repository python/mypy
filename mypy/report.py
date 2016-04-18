"""Classes for producing HTML reports about imprecision."""

from abc import ABCMeta, abstractmethod
import cgi
import os
import shutil
import tokenize

from typing import Callable, Dict, List, Tuple, cast

from mypy.nodes import MypyFile, Node, FuncDef
from mypy import stats
from mypy.traverser import TraverserVisitor
from mypy.types import Type


reporter_classes = {}  # type: Dict[str, Callable[[Reports, str], AbstractReporter]]


class Reports:
    def __init__(self, data_dir: str, report_dirs: Dict[str, str]) -> None:
        self.data_dir = data_dir
        self.reporters = []  # type: List[AbstractReporter]
        self.named_reporters = {}  # type: Dict[str, AbstractReporter]

        for report_type, report_dir in sorted(report_dirs.items()):
            self.add_report(report_type, report_dir)

    def add_report(self, report_type: str, report_dir: str) -> 'AbstractReporter':
        try:
            return self.named_reporters[report_type]
        except KeyError:
            pass
        reporter_cls = reporter_classes[report_type]
        reporter = reporter_cls(self, report_dir)
        self.reporters.append(reporter)
        self.named_reporters[report_type] = reporter
        return reporter

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


class FuncCounterVisitor(TraverserVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.counts = [0, 0]

    def visit_func_def(self, defn: FuncDef):
        self.counts[defn.type is not None] += 1


class LineCountReporter(AbstractReporter):
    def __init__(self, reports: Reports, output_dir: str) -> None:
        super().__init__(reports, output_dir)
        self.counts = {}  # type: Dict[str, Tuple[int, int, int, int]]

        stats.ensure_dir_exists(output_dir)

    def on_file(self, tree: MypyFile, type_map: Dict[Node, Type]) -> None:
        physical_lines = len(open(tree.path).readlines())

        func_counter = FuncCounterVisitor()
        tree.accept(func_counter)
        unannotated_funcs, annotated_funcs = func_counter.counts
        total_funcs = annotated_funcs + unannotated_funcs

        imputed_annotated_lines = (physical_lines * annotated_funcs // total_funcs
                                   if total_funcs else physical_lines)

        self.counts[tree._fullname] = (imputed_annotated_lines, physical_lines,
                                       annotated_funcs, total_funcs)

    def on_finish(self) -> None:
        counts = sorted(((c, p) for p, c in self.counts.items()),
                        reverse=True)  # type: List[Tuple[tuple, str]]
        total_counts = tuple(sum(c[i] for c, p in counts)
                             for i in range(4))
        with open(os.path.join(self.output_dir, 'linecount.txt'), 'w') as f:
            f.write('{:7} {:7} {:6} {:6} total\n'.format(*total_counts))
            for c, p in counts:
                f.write('{:7} {:7} {:6} {:6} {}\n'.format(
                    c[0], c[1], c[2], c[3], p))

reporter_classes['linecount'] = LineCountReporter


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


class FileInfo:
    def __init__(self, name: str, module: str) -> None:
        self.name = name
        self.module = module
        self.counts = [0] * len(stats.precision_names)

    def total(self) -> int:
        return sum(self.counts)

    def attrib(self) -> Dict[str, str]:
        return {name: str(val) for name, val in zip(stats.precision_names, self.counts)}


class MemoryXmlReporter(AbstractReporter):
    """Internal reporter that generates XML in memory.

    This is used by all other XML-based reporters to avoid duplication.
    """

    def __init__(self, reports: Reports, output_dir: str) -> None:
        import lxml.etree as etree

        super().__init__(reports, output_dir)

        self.xslt_html_path = os.path.join(reports.data_dir, 'xml', 'mypy-html.xslt')
        self.xslt_txt_path = os.path.join(reports.data_dir, 'xml', 'mypy-txt.xslt')
        self.css_html_path = os.path.join(reports.data_dir, 'xml', 'mypy-html.css')
        xsd_path = os.path.join(reports.data_dir, 'xml', 'mypy.xsd')
        self.schema = etree.XMLSchema(etree.parse(xsd_path))
        self.last_xml = None  # type: etree._ElementTree
        self.files = []  # type: List[FileInfo]

    def on_file(self, tree: MypyFile, type_map: Dict[Node, Type]) -> None:
        import lxml.etree as etree

        self.last_xml = None
        path = os.path.relpath(tree.path)
        if stats.is_special_module(path):
            return
        if path.startswith('..'):
            return
        if 'stubs' in path.split('/'):
            return

        visitor = stats.StatisticsVisitor(inferred=True, typemap=type_map, all_nodes=True)
        tree.accept(visitor)

        root = etree.Element('mypy-report-file', name=path, module=tree._fullname)
        doc = etree.ElementTree(root)
        file_info = FileInfo(path, tree._fullname)

        with tokenize.open(path) as input_file:
            for lineno, line_text in enumerate(input_file, 1):
                status = visitor.line_map.get(lineno, stats.TYPE_EMPTY)
                file_info.counts[status] += 1
                etree.SubElement(root, 'line',
                                 number=str(lineno),
                                 precision=stats.precision_names[status],
                                 content=line_text[:-1])
        # Assumes a layout similar to what XmlReporter uses.
        xslt_path = os.path.relpath('mypy-html.xslt', path)
        transform_pi = etree.ProcessingInstruction('xml-stylesheet',
                'type="text/xsl" href="%s"' % cgi.escape(xslt_path, True))
        root.addprevious(transform_pi)
        self.schema.assertValid(doc)

        self.last_xml = doc
        self.files.append(file_info)

    def on_finish(self) -> None:
        import lxml.etree as etree

        self.last_xml = None
        # index_path = os.path.join(self.output_dir, 'index.xml')
        output_files = sorted(self.files, key=lambda x: x.module)

        root = etree.Element('mypy-report-index', name='index')
        doc = etree.ElementTree(root)

        for file_info in output_files:
            etree.SubElement(root, 'file',
                             file_info.attrib(),
                             total=str(file_info.total()),
                             name=file_info.name,
                             module=file_info.module)
        xslt_path = os.path.relpath('mypy-html.xslt', '.')
        transform_pi = etree.ProcessingInstruction('xml-stylesheet',
                'type="text/xsl" href="%s"' % cgi.escape(xslt_path, True))
        root.addprevious(transform_pi)
        self.schema.assertValid(doc)

        self.last_xml = doc

reporter_classes['memory-xml'] = MemoryXmlReporter


class AbstractXmlReporter(AbstractReporter):
    """Internal abstract class for reporters that work via XML."""

    def __init__(self, reports: Reports, output_dir: str) -> None:
        super().__init__(reports, output_dir)

        memory_reporter = reports.add_report('memory-xml', '<memory>')
        # The dependency will be called first.
        self.memory_xml = cast(MemoryXmlReporter, memory_reporter)


class XmlReporter(AbstractXmlReporter):
    """Public reporter that exports XML.

    The produced XML files contain a reference to the absolute path
    of the html transform, so they will be locally viewable in a browser.

    However, there is a bug in Chrome and all other WebKit-based browsers
    that makes it fail from file:// URLs but work on http:// URLs.
    """

    def on_file(self, tree: MypyFile, type_map: Dict[Node, Type]) -> None:
        last_xml = self.memory_xml.last_xml
        if last_xml is None:
            return
        path = os.path.relpath(tree.path)
        if path.startswith('..'):
            return
        out_path = os.path.join(self.output_dir, 'xml', path + '.xml')
        stats.ensure_dir_exists(os.path.dirname(out_path))
        last_xml.write(out_path, encoding='utf-8')

    def on_finish(self) -> None:
        last_xml = self.memory_xml.last_xml
        out_path = os.path.join(self.output_dir, 'index.xml')
        out_xslt = os.path.join(self.output_dir, 'mypy-html.xslt')
        out_css = os.path.join(self.output_dir, 'mypy-html.css')
        last_xml.write(out_path, encoding='utf-8')
        shutil.copyfile(self.memory_xml.xslt_html_path, out_xslt)
        shutil.copyfile(self.memory_xml.css_html_path, out_css)
        print('Generated XML report:', os.path.abspath(out_path))

reporter_classes['xml'] = XmlReporter


class XsltHtmlReporter(AbstractXmlReporter):
    """Public reporter that exports HTML via XSLT.

    This is slightly different than running `xsltproc` on the .xml files,
    because it passes a parameter to rewrite the links.
    """

    def __init__(self, reports: Reports, output_dir: str) -> None:
        import lxml.etree as etree

        super().__init__(reports, output_dir)

        self.xslt_html = etree.XSLT(etree.parse(self.memory_xml.xslt_html_path))
        self.param_html = etree.XSLT.strparam('html')

    def on_file(self, tree: MypyFile, type_map: Dict[Node, Type]) -> None:
        last_xml = self.memory_xml.last_xml
        if last_xml is None:
            return
        path = os.path.relpath(tree.path)
        if path.startswith('..'):
            return
        out_path = os.path.join(self.output_dir, 'html', path + '.html')
        stats.ensure_dir_exists(os.path.dirname(out_path))
        transformed_html = bytes(self.xslt_html(last_xml, ext=self.param_html))
        with open(out_path, 'wb') as out_file:
            out_file.write(transformed_html)

    def on_finish(self) -> None:
        last_xml = self.memory_xml.last_xml
        out_path = os.path.join(self.output_dir, 'index.html')
        out_css = os.path.join(self.output_dir, 'mypy-html.css')
        transformed_html = bytes(self.xslt_html(last_xml, ext=self.param_html))
        with open(out_path, 'wb') as out_file:
            out_file.write(transformed_html)
        shutil.copyfile(self.memory_xml.css_html_path, out_css)
        print('Generated HTML report (via XSLT):', os.path.abspath(out_path))

reporter_classes['xslt-html'] = XsltHtmlReporter


class XsltTxtReporter(AbstractXmlReporter):
    """Public reporter that exports TXT via XSLT.

    Currently this only does the summary, not the individual reports.
    """

    def __init__(self, reports: Reports, output_dir: str) -> None:
        import lxml.etree as etree

        super().__init__(reports, output_dir)

        self.xslt_txt = etree.XSLT(etree.parse(self.memory_xml.xslt_txt_path))

    def on_file(self, tree: MypyFile, type_map: Dict[Node, Type]) -> None:
        pass

    def on_finish(self) -> None:
        last_xml = self.memory_xml.last_xml
        out_path = os.path.join(self.output_dir, 'index.txt')
        stats.ensure_dir_exists(os.path.dirname(out_path))
        transformed_txt = bytes(self.xslt_txt(last_xml))
        with open(out_path, 'wb') as out_file:
            out_file.write(transformed_txt)
        print('Generated TXT report (via XSLT):', os.path.abspath(out_path))

reporter_classes['xslt-txt'] = XsltTxtReporter

reporter_classes['html'] = reporter_classes['xslt-html']
reporter_classes['txt'] = reporter_classes['xslt-txt']
