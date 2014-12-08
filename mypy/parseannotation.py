"""Annotation parse"""

from typing import List, Tuple

from mypy.lex import Token
from mypy import nodes
from mypy.annotations import Annotation, IgnoreAnnotation


class AnnotationParseError(Exception):
    def __init__(self, token: Token, index: int) -> None:
        super().__init__()
        self.token = token
        self.index = index


def parse_annotation(tok: List[Token], index: int) -> Tuple[Annotation, int]:
    """Parse an annotation
    """

    p = AnnotationParser(tok, index)
    return p.parse_annotation(), p.index()

class AnnotationParser:
    def __init__(self, tok: List[Token], ind: int) -> None:
        self.tok = tok
        self.ind = ind

    def index(self) -> int:
        return self.ind

    def parse_annotation(self) -> Annotation:
        """Parse an annotation."""
        t = self.current_token()
        if t.string == 'ignore':
            self.skip()
            return IgnoreAnnotation(t.line)
        else:
            self.parse_error()

    # Helpers:

    def skip(self) -> Token:
        self.ind += 1
        return self.tok[self.ind - 1]

    def current_token(self) -> Token:
        return self.tok[self.ind]

    def parse_error(self) -> None:
        raise AnnotationParseError(self.tok[self.ind], self.ind)