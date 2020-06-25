
import sys
from typing import List, Tuple, Optional

if sys.platform == 'win32':

    ActionText: List[Tuple[str, str, Optional[str]]]
    UIText: List[Tuple[str, Optional[str]]]

    tables: List[str]
