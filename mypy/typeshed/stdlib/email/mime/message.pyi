# Stubs for email.mime.message (Python 3.4)

import sys
from email.message import Message
from email.mime.nonmultipart import MIMENonMultipart
from email.policy import Policy
from typing import Optional

class MIMEMessage(MIMENonMultipart):
    if sys.version_info >= (3, 6):
        def __init__(self, _msg: Message, _subtype: str = ..., *, policy: Optional[Policy] = ...) -> None: ...
    else:
        def __init__(self, _msg: Message, _subtype: str = ...) -> None: ...
