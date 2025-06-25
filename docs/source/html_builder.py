from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any

from sphinx.addnodes import document
from sphinx.application import Sphinx
from sphinx.builders.html import StandaloneHTMLBuilder
from sphinx.environment import BuildEnvironment

from mypy.main import define_options


class MypyHTMLBuilder(StandaloneHTMLBuilder):
    strict_file: Path

    def __init__(self, app: Sphinx, env: BuildEnvironment) -> None:
        super().__init__(app, env)
        self._ref_to_doc = {}
        self.strict_file = Path(self.srcdir) / "strict_list.rst"
        self._add_strict_list()

    def write_doc(self, docname: str, doctree: document) -> None:
        super().write_doc(docname, doctree)
        self._ref_to_doc.update({_id: docname for _id in doctree.ids})

    def _add_strict_list(self) -> None:
        strict_flags: list[str]
        _, strict_flags, _ = define_options()
        strict_part = ", ".join(f":option:`{s} <mypy {s}>`" for s in strict_flags)
        if (
            not strict_part
            or strict_part.isspace()
            or len(strict_part) < 20
            or len(strict_part) > 2000
        ):
            raise ValueError(f"{strict_part=}, which doesn't look right (by a simple heuristic).")
        self.strict_file.write_text(
            "For this version of mypy, the list of flags enabled by strict is: " + strict_part
        )

    def _verify_error_codes(self) -> None:
        from mypy.errorcodes import error_codes

        missing_error_codes = {c for c in error_codes if f"code-{c}" not in self._ref_to_doc}
        if missing_error_codes:
            raise ValueError(
                f"Some error codes are not documented: {', '.join(sorted(missing_error_codes))}"
            )

    def _write_ref_redirector(self) -> None:
        if os.getenv("VERIFY_MYPY_ERROR_CODES"):
            self._verify_error_codes()
        p = Path(self.outdir) / "_refs.html"
        data = f"""
        <html>
        <body>
        <script>
        const ref_to_doc = {json.dumps(self._ref_to_doc)};
        const hash = window.location.hash.substring(1);
        const doc = ref_to_doc[hash];
        if (doc) {{
            window.location.href = doc + '.html' + '#' + hash;
        }} else {{
            window.document.innerText = 'Unknown reference: ' + hash;
        }}
        </script>
        </body>
        </html>
        """
        p.write_text(textwrap.dedent(data))

    def finish(self) -> None:
        super().finish()
        self._write_ref_redirector()
        self.strict_file.unlink()


def setup(app: Sphinx) -> dict[str, Any]:
    app.add_builder(MypyHTMLBuilder, override=True)

    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
