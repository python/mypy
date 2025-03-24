from __future__ import annotations

import os.path
import sys
from html import escape
from typing import Final

from mypy.build import BuildResult
from mypy.nodes import MypyFile, FuncDef, Node, LambdaExpr
from mypy.util import FancyFormatter
from mypy.traverser import TraverserVisitor
from mypyc.ir.func_ir import FuncIR
from mypyc.ir.module_ir import ModuleIR
from mypyc.ir.ops import CallC, LoadLiteral, Value, LoadStatic, LoadLiteral

op_hints: Final = {
    "PyNumber_Add": 'Generic "+" operation.',
    "PyNumber_Subtract": 'Generic "-" operation.',
    "PyNumber_Multiply": 'Generic "*" operation.',
    "PyNumber_TrueDivide": 'Generic "/" operation.',
    "PyNumber_FloorDivide": 'Generic "//" operation.',
    "PyNumber_Positive": 'Generic unary "+" operation.',
    "PyNumber_Negative": 'Generic unary "-" operation.',
    "PyNumber_And": 'Generic "&" operation.',
    "PyNumber_Or": 'Generic "|" operation.',
    "PyNumber_Xor": 'Generic "^" operation.',
    "PyNumber_Lshift": 'Generic "<<" operation.',
    "PyNumber_Rshift": 'Generic ">>" operation.',
    "PyNumber_Invert": 'Generic "~" operation.',
    "PySequence_Contains": 'Generic "in" operation.',
    "PyObject_Call": 'Generic call operation.',
}

CSS = """\
.collapsible {
    cursor: pointer;
}

.content {
    display: block;
    margin-top: 10px;
    margin-bottom: 10px;
}

.hint {
    display: inline;
    border: 1px solid #ccc;
    padding: 5px;
}
"""

JS = """\
document.querySelectorAll('.collapsible').forEach(function(collapsible) {
    collapsible.addEventListener('click', function() {
        const content = this.nextElementSibling;
        if (content.style.display === 'none') {
            content.style.display = 'block';
        } else {
            content.style.display = 'none';
        }
    });
});
"""


class AnnotatedSource:
    def __init__(self, path: str, annotations: dict[int, list[str]]) -> None:
        self.path = path
        self.annotations = annotations


def generate_annotated_html(
    html_fnam: str, result: BuildResult, modules: dict[str, ModuleIR]
) -> None:
    annotations = []
    for mod, mod_ir in modules.items():
        path = result.graph[mod].path
        tree = result.graph[mod].tree
        assert tree is not None
        annotations.append(generate_annotations(path or "<source>", tree, mod_ir))
    html = generate_html_report(annotations)
    with open(html_fnam, "w") as f:
        f.write(html)

    formatter = FancyFormatter(sys.stdout, sys.stderr, False)
    formatted = formatter.style(os.path.abspath(html_fnam), "none", underline=True, bold=True)
    print(f"\nWrote {formatted} -- open in browser to view\n")


def generate_annotations(path: str, tree: MypyFile, ir: ModuleIR) -> AnnotatedSource:
    anns = {}
    for func_ir in ir.functions:
        anns.update(function_annotations(func_ir))
    visitor = ASTAnnotateVisitor()
    for defn in tree.defs:
        defn.accept(visitor)
    anns.update(visitor.anns)
    return AnnotatedSource(path, anns)


def function_annotations(func_ir: FuncIR) -> dict[int, list[str]]:
    # TODO: check if func_ir.line is -1
    anns: dict[int, list[str]] = {}
    for block in func_ir.blocks:
        for op in block.ops:
            if isinstance(op, CallC):
                name = op.function_name
                ann = None
                if name == "CPyObject_GetAttr":
                    attr_name = get_str_literal(op.args[1])
                    if attr_name:
                        ann = f'Get non-native attribute "{attr_name}".'
                    else:
                        ann = "Dynamic attribute lookup."
                elif name == "PyObject_VectorcallMethod":
                    method_name = get_str_literal(op.args[0])
                    if method_name:
                        ann = f'Call non-native method "{method_name}".'
                    else:
                        ann = "Dynamic method call."
                elif name in op_hints:
                    ann = op_hints[name]
                elif name in ("CPyDict_GetItem", "CPyDict_SetItem"):
                    if isinstance(op.args[0], LoadStatic) and isinstance(op.args[1], LoadLiteral) and func_ir.name != "__top_level__":
                        load = op.args[0]
                        if load.namespace == "static" and load.identifier == "globals":
                            ann = f'Access global "{op.args[1].value}" through namespace ' + 'dictionary (hint: access is faster if you can make it Final).'
                if ann:
                    anns.setdefault(op.line, []).append(ann)
    return anns


class ASTAnnotateVisitor(TraverserVisitor):
    def __init__(self) -> None:
        self.anns: dict[int, list[str]] = {}
        self.func_depth = 0

    def visit_func_def(self, o: FuncDef, /) -> None:
        if self.func_depth > 0:
            self.annotate(o, "A nested function object is allocated each time statement is executed. " + "A module-level function would be faster.")
        self.func_depth += 1
        super().visit_func_def(o)
        self.func_depth -= 1

    def visit_lambda_expr(self, o: LambdaExpr, /) -> None:
        self.annotate(o, "A new object is allocated for lambda each time it is evaluated. " + "A module-level function would be faster.")
        super().visit_lambda_expr(o)

    def annotate(self, o: Node, ann: str) -> None:
        self.anns.setdefault(o.line, []).append(ann)


def get_str_literal(v: Value) -> str | None:
    if isinstance(v, LoadLiteral) and isinstance(v.value, str):
        return v.value
    return None


def generate_html_report(sources: list[AnnotatedSource]) -> str:
    html = []
    html.append("<html>\n<head>\n")
    html.append(f"<style>\n{CSS}\n</style>")
    html.append("</head>\n")
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
            linenum = "%5d" % line
            if line in anns:
                hint = " ".join(anns[line])
                s = colorize_line(linenum, s, hint_html=hint)
            else:
                s = linenum + "  " + s
            html.append(s)
        html.append("</pre>")

    html.append("<script>")
    html.append(JS)
    html.append("</script>")

    html.append("</body></html>\n")
    return "".join(html)


def colorize_line(linenum: str, s: str, hint_html: str) -> str:
    hint_prefix = " " * len(linenum) + "  "
    line_span = f'<div class="collapsible" style="background-color: #fcc">{linenum}  {s}</div>'
    hint_div = f'<div class="content">{hint_prefix}<div class="hint">{hint_html}</div></div>'
    return f"<span>{line_span}{hint_div}</span>"
