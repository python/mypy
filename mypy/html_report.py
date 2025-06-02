"""Classes for producing HTML reports about type checking results."""

from __future__ import annotations

import collections
import os
import shutil
from typing import Any

from mypy import stats
from mypy.nodes import Expression, MypyFile
from mypy.options import Options
from mypy.report import AbstractReporter, FileInfo, iterate_python_lines, register_reporter, should_skip_path
from mypy.types import Type, TypeOfAny
from mypy.version import __version__

# Map of TypeOfAny enum values to descriptive strings
type_of_any_name_map = {
    TypeOfAny.unannotated: "Unannotated",
    TypeOfAny.explicit: "Explicit",
    TypeOfAny.from_unimported_type: "Unimported",
    TypeOfAny.from_omitted_generics: "Omitted Generics",
    TypeOfAny.from_error: "Error",
    TypeOfAny.special_form: "Special Form",
    TypeOfAny.implementation_artifact: "Implementation Artifact",
}


class MemoryHtmlReporter(AbstractReporter):
    """Internal reporter that generates HTML in memory.

    This is used by the HTML reporter to avoid duplication.
    """

    def __init__(self, reports: Any, output_dir: str) -> None:
        super().__init__(reports, output_dir)
        self.css_html_path = os.path.join(reports.data_dir, "xml", "mypy-html.css")
        self.last_html: dict[str, str] = {}  # Maps file paths to HTML content
        self.index_html: str | None = None
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

        if should_skip_path(path) or os.path.isdir(path):
            return  # `path` can sometimes be a directory, see #11334

        visitor = stats.StatisticsVisitor(
            inferred=True,
            filename=tree.fullname,
            modules=modules,
            typemap=type_map,
            all_nodes=True,
        )
        tree.accept(visitor)

        file_info = FileInfo(path, tree._fullname)
        
        # Generate HTML for this file
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "    <meta charset='utf-8'>",
            "    <title>Mypy Report: " + path + "</title>",
            "    <link rel='stylesheet' href='../mypy-html.css'>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 20px; }",
            "        h1 { color: #333; }",
            "        table { border-collapse: collapse; width: 100%; }",
            "        th { background-color: #f2f2f2; text-align: left; padding: 8px; }",
            "        td { padding: 8px; border-bottom: 1px solid #ddd; }",
            "        tr.precise { background-color: #dff0d8; }",
            "        tr.imprecise { background-color: #fcf8e3; }",
            "        tr.any { background-color: #f2dede; }",
            "        tr.empty, tr.unanalyzed { background-color: #f9f9f9; }",
            "        pre { margin: 0; white-space: pre-wrap; }",
            "    </style>",
            "</head>",
            "<body>",
            f"    <h1>Mypy Type Check Report for {path}</h1>",
            "    <table>",
            "        <tr>",
            "            <th>Line</th>",
            "            <th>Precision</th>",
            "            <th>Code</th>",
            "            <th>Notes</th>",
            "        </tr>"
        ]

        for lineno, line_text in iterate_python_lines(path):
            status = visitor.line_map.get(lineno, stats.TYPE_EMPTY)
            file_info.counts[status] += 1
            
            precision = stats.precision_names[status]
            any_info = self._get_any_info_for_line(visitor, lineno)
            
            # Escape HTML special characters in the line content
            content = line_text.rstrip("\n")
            content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            # Add CSS class based on precision
            css_class = precision.lower()
            
            html_lines.append(
                f"        <tr class='{css_class}'>"
                f"<td>{lineno}</td>"
                f"<td>{precision}</td>"
                f"<td><pre>{content}</pre></td>"
                f"<td>{any_info}</td>"
                "</tr>"
            )
            
        html_lines.extend([
            "    </table>",
            "</body>",
            "</html>"
        ])
        
        self.last_html[path] = "\n".join(html_lines)
        self.files.append(file_info)

    @staticmethod
    def _get_any_info_for_line(visitor: stats.StatisticsVisitor, lineno: int) -> str:
        if lineno in visitor.any_line_map:
            result = "Any Types on this line: "
            counter: collections.Counter[int] = collections.Counter()
            for typ in visitor.any_line_map[lineno]:
                counter[typ.type_of_any] += 1
            for any_type, occurrences in counter.items():
                result += f"<br>{type_of_any_name_map[any_type]} (x{occurrences})"
            return result
        else:
            return ""

    def on_finish(self) -> None:
        output_files = sorted(self.files, key=lambda x: x.module)
        
        # Generate index HTML
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "    <meta charset='utf-8'>",
            "    <title>Mypy Report Index</title>",
            "    <link rel='stylesheet' href='mypy-html.css'>",
            "    <style>",
            "        body { font-family: Arial, sans-serif; margin: 20px; }",
            "        h1 { color: #333; }",
            "        table { border-collapse: collapse; width: 100%; }",
            "        th { background-color: #f2f2f2; text-align: left; padding: 8px; }",
            "        td { padding: 8px; border-bottom: 1px solid #ddd; }",
            "        a { color: #337ab7; text-decoration: none; }",
            "        a:hover { text-decoration: underline; }",
            "    </style>",
            "</head>",
            "<body>",
            "    <h1>Mypy Type Check Report</h1>",
            "    <p>Generated with mypy " + __version__ + "</p>",
            "    <table>",
            "        <tr>",
            "            <th>Module</th>",
            "            <th>File</th>",
            "            <th>Precise</th>",
            "            <th>Imprecise</th>",
            "            <th>Any</th>",
            "            <th>Empty</th>",
            "            <th>Unanalyzed</th>",
            "            <th>Total</th>",
            "        </tr>"
        ]

        for file_info in output_files:
            counts = file_info.counts
            html_lines.append(
                f"        <tr>"
                f"<td>{file_info.module}</td>"
                f"<td><a href='html/{file_info.name}.html'>{file_info.name}</a></td>"
                f"<td>{counts[stats.TYPE_PRECISE]}</td>"
                f"<td>{counts[stats.TYPE_IMPRECISE]}</td>"
                f"<td>{counts[stats.TYPE_ANY]}</td>"
                f"<td>{counts[stats.TYPE_EMPTY]}</td>"
                f"<td>{counts[stats.TYPE_UNANALYZED]}</td>"
                f"<td>{file_info.total()}</td>"
                "</tr>"
            )
            
        html_lines.extend([
            "    </table>",
            "</body>",
            "</html>"
        ])
        
        self.index_html = "\n".join(html_lines)


class HtmlReporter(AbstractReporter):
    """Public reporter that exports HTML directly.

    This reporter generates HTML files for each Python module and an index.html file.
    """

    def __init__(self, reports: Any, output_dir: str) -> None:
        super().__init__(reports, output_dir)

        memory_reporter = reports.add_report("memory-html", "<memory>")
        assert isinstance(memory_reporter, MemoryHtmlReporter)
        # The dependency will be called first.
        self.memory_html = memory_reporter

    def on_file(
        self,
        tree: MypyFile,
        modules: dict[str, MypyFile],
        type_map: dict[Expression, Type],
        options: Options,
    ) -> None:
        last_html = self.memory_html.last_html
        if not last_html:
            return
        
        path = os.path.relpath(tree.path)
        if path.startswith("..") or path not in last_html:
            return
            
        out_path = os.path.join(self.output_dir, "html", path + ".html")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with open(out_path, "w", encoding="utf-8") as out_file:
            out_file.write(last_html[path])

    def on_finish(self) -> None:
        index_html = self.memory_html.index_html
        if index_html is None:
            return
            
        out_path = os.path.join(self.output_dir, "index.html")
        out_css = os.path.join(self.output_dir, "mypy-html.css")
        
        with open(out_path, "w", encoding="utf-8") as out_file:
            out_file.write(index_html)
            
        # Copy CSS file if it exists
        if os.path.exists(self.memory_html.css_html_path):
            shutil.copyfile(self.memory_html.css_html_path, out_css)
        else:
            # Create a basic CSS file if the original doesn't exist
            with open(out_css, "w", encoding="utf-8") as css_file:
                css_file.write("""
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                table { border-collapse: collapse; width: 100%; }
                th { background-color: #f2f2f2; text-align: left; padding: 8px; }
                td { padding: 8px; border-bottom: 1px solid #ddd; }
                tr.precise { background-color: #dff0d8; }
                tr.imprecise { background-color: #fcf8e3; }
                tr.any { background-color: #f2dede; }
                tr.empty, tr.unanalyzed { background-color: #f9f9f9; }
                pre { margin: 0; white-space: pre-wrap; }
                a { color: #337ab7; text-decoration: none; }
                a:hover { text-decoration: underline; }
                """)
                
        print("Generated HTML report:", os.path.abspath(out_path))


# Register the reporters
register_reporter("memory-html", MemoryHtmlReporter)
register_reporter("html-direct", HtmlReporter)