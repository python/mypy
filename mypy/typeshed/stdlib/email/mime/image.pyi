from email.mime.nonmultipart import MIMENonMultipart
from email.policy import Policy
from typing import Callable, Optional, Union

__all__ = ["MIMEImage"]

_ParamsType = Union[str, None, tuple[str, Optional[str], str]]

class MIMEImage(MIMENonMultipart):
    def __init__(
        self,
        _imagedata: str | bytes,
        _subtype: str | None = ...,
        _encoder: Callable[[MIMEImage], None] = ...,
        *,
        policy: Policy | None = ...,
        **_params: _ParamsType,
    ) -> None: ...
