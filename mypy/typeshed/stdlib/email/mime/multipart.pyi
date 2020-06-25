# Stubs for email.mime.multipart (Python 3.4)

import sys
from email.message import Message
from email.mime.base import MIMEBase
from email.policy import Policy
from typing import Optional, Sequence, Tuple, Union

_ParamsType = Union[str, None, Tuple[str, Optional[str], str]]

class MIMEMultipart(MIMEBase):
    if sys.version_info >= (3, 6):
        def __init__(
            self,
            _subtype: str = ...,
            boundary: Optional[str] = ...,
            _subparts: Optional[Sequence[Message]] = ...,
            *,
            policy: Optional[Policy] = ...,
            **_params: _ParamsType,
        ) -> None: ...
    else:
        def __init__(
            self,
            _subtype: str = ...,
            boundary: Optional[str] = ...,
            _subparts: Optional[Sequence[Message]] = ...,
            **_params: _ParamsType,
        ) -> None: ...
