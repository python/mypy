from __future__ import annotations

import os.path
import sys
from html import escape

from mypy.build import BuildResult
from mypy.nodes import MypyFile
from mypy.util import FancyFormatter
from mypyc.ir.func_ir import FuncIR
from mypyc.ir.module_ir import ModuleIR
from mypyc.ir.ops import CallC, LoadLiteral, Value

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
                elif name == "PyNumber_Add":
                    ann = 'Generic "+" operation.'
                if ann:
                    anns.setdefault(op.line, []).append(ann)
    return anns


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
