import docutils.nodes
import docutils.parsers.rst.states

from typing import Function, Any, List, Dict, Tuple

def register_local_role(name: str,
                        role_fn: Function[[str, str, str, int, docutils.parsers.rst.states.Inliner, Dict, List],
                                          Tuple[List[docutils.nodes.reference], List[docutils.nodes.reference]]]
                        ) -> None:
    pass
