"""Generic node traverser visitor"""

from mypy.traverser import TraverserVisitor
from mypy.nodes import Block, MypyFile


class TreeFreer(TraverserVisitor):
    def visit_block(self, block: Block) -> None:
        super().visit_block(block)
        block.body.clear()


def free_tree(tree: MypyFile) -> None:
    tree.accept(TreeFreer())
