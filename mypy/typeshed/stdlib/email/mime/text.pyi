# Stubs for email.mime.text (Python 3.4)

import sys
from email.mime.nonmultipart import MIMENonMultipart
from email.policy import Policy
from typing import Optional

class MIMEText(MIMENonMultipart):
    if sys.version_info >= (3, 6):
        def __init__(
            self, _text: str, _subtype: str = ..., _charset: Optional[str] = ..., *, policy: Optional[Policy] = ...
        ) -> None: ...
    else:
        def __init__(self, _text: str, _subtype: str = ..., _charset: Optional[str] = ...) -> None: ...
