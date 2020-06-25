# Stubs for email.mime.image (Python 3.4)

import sys
from email.mime.nonmultipart import MIMENonMultipart
from email.policy import Policy
from typing import Callable, Optional, Tuple, Union

_ParamsType = Union[str, None, Tuple[str, Optional[str], str]]

class MIMEImage(MIMENonMultipart):
    if sys.version_info >= (3, 6):
        def __init__(
            self,
            _imagedata: Union[str, bytes],
            _subtype: Optional[str] = ...,
            _encoder: Callable[[MIMEImage], None] = ...,
            *,
            policy: Optional[Policy] = ...,
            **_params: _ParamsType,
        ) -> None: ...
    else:
        def __init__(
            self,
            _imagedata: Union[str, bytes],
            _subtype: Optional[str] = ...,
            _encoder: Callable[[MIMEImage], None] = ...,
            **_params: _ParamsType,
        ) -> None: ...
