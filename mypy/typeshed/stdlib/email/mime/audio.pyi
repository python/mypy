# Stubs for email.mime.audio (Python 3.4)

import sys
from email.mime.nonmultipart import MIMENonMultipart
from email.policy import Policy
from typing import Callable, Optional, Tuple, Union

_ParamsType = Union[str, None, Tuple[str, Optional[str], str]]

class MIMEAudio(MIMENonMultipart):
    if sys.version_info >= (3, 6):
        def __init__(
            self,
            _audiodata: Union[str, bytes],
            _subtype: Optional[str] = ...,
            _encoder: Callable[[MIMEAudio], None] = ...,
            *,
            policy: Optional[Policy] = ...,
            **_params: _ParamsType,
        ) -> None: ...
    else:
        def __init__(
            self,
            _audiodata: Union[str, bytes],
            _subtype: Optional[str] = ...,
            _encoder: Callable[[MIMEAudio], None] = ...,
            **_params: _ParamsType,
        ) -> None: ...
