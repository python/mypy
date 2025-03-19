import os.path
import sys

from mypy.build import BuildResult
from mypy.nodes import MypyFile
from mypy.util import FancyFormatter
from mypyc.ir.module_ir import ModuleIR


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
    return AnnotatedSource(path, {})


def generate_html_report(annotations: list[AnnotatedSource]) -> str:
    html = []
    html.append("<html><head></head>\n")
    html.append("<body>\n")
    html.append("<h1>Mypyc Report\n")
    html.append("</body></html>\n")
    return "".join(html)

