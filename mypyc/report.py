import os.path
import re
import sys
from html import escape

from mypy.build import BuildResult
from mypy.nodes import MypyFile
from mypy.util import FancyFormatter
from mypyc.ir.module_ir import ModuleIR
from mypyc.ir.func_ir import FuncIR
from mypyc.ir.ops import CallC


class AnnotatedSource:
    def __init__(self, path: str, annotations: dict[int, str]) -> None:
        self.path = path
        self.annotations = annotations


def generate_report(result: BuildResult, modules: dict[str, ModuleIR]) -> None:
    annotations = []
    for mod, mod_ir in modules.items():
        path = result.graph[mod].path
        tree = result.graph[mod].tree
        annotations.append(generate_annotations(path, tree, mod_ir))
    html = generate_html_report(annotations)
    fnam = "mypyc-report.html"
    with open(fnam, "w") as f:
        f.write(html)

    f = FancyFormatter(sys.stdout, sys.stderr, False)
    formatted = f.style(os.path.abspath(fnam), "none", underline=True, bold=True)
    print(f"\nWrote {formatted} -- open in browser to view\n")


def generate_annotations(path: str, tree: MypyFile, ir: ModuleIR) -> AnnotatedSource:
    anns = {}
    for func_ir in ir.functions:
        anns.update(function_annotations(func_ir))
    return AnnotatedSource(path, anns)


def function_annotations(func_ir: FuncIR) -> dict[int, str]:
    # TODO: check if func_ir.line is -1
    anns = {}
    for block in func_ir.blocks:
        for op in block.ops:
            if isinstance(op, CallC):
                name = op.function_name
                if name == "CPyObject_GetAttr":
                    anns[op.line] = "bad"
                    print(op.line, op.function_name)
    return anns


def generate_html_report(sources: list[AnnotatedSource]) -> str:
    html = []
    html.append("<html><head></head>\n")
    html.append("<body>\n")
    for src in sources:
        html.append(f"<h2><tt>{src.path}</tt></h2>\n")
        html.append("<pre>")
        anns = src.annotations
        with open(src.path) as f:
            lines = f.readlines()
        for i, s in enumerate(lines):
            s = escape(s)
            line = i + 1
            if line in anns:
                s = colorize_line(s)
            html.append(s)
        html.append("</pre>")

    html.append("</body></html>\n")
    return "".join(html)


def colorize_line(s: str) -> str:
    init = re.match("[ \t]*", s).group()
    return init + f'<span style="background-color: #fcc">{s[len(init):]}</span>'
