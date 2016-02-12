from typing import Any

JsonThing = Any

from mypy.nodes import (NodeVisitor, SymbolTableNode, MypyFile, Import, ImportFrom)


class SerializeVisitor(NodeVisitor[JsonThing]):

    def __init__(self):  # TODO
        self.mod_id = None

    def visit_mypy_file(self, node: MypyFile) -> JsonThing:
        save_mod_id = self.mod_id
        try:
            self.mod_id = node.fullname()
            return {
                '.tag': 'MypyFile',
                'fullname': node.fullname(),
                'path': node.path,
                ## 'defs': [n.accept(self) for n in node.defs],
                'names': {k: v.serialize(self) for k, v in node.names.items()},
                'imports': [n.accept(self) for n in node.imports],
                'is_stub': node.is_stub,
                }
        finally:
            self.mod_id = save_mod_id

    def visit_import_from(self, node: ImportFrom) -> JsonThing:
        return {
            '.tag': 'ImportFrom',
            'id': node.id,
            'names': [[t[0], t[1]] for t in node.names],
            'relative': node.relative,
            }

    def visit_import(self, node: Import) -> JsonThing:
        return {
            '.tag': 'Import',
            'ids': [[t[0], t[1]] for t in node.ids],
            }
