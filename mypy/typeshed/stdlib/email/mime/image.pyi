from collections.abc import Callable
from email import _ParamsType
from email.mime.nonmultipart import MIMENonMultipart
from email.policy import Policy

__all__ = ["MIMEImage"]

class MIMEImage(MIMENonMultipart):
    def __init__(
        self,
        _imagedata: str | bytes | bytearray,
        _subtype: str | None = ...,
        _encoder: Callable[[MIMEImage], object] = ...,
        *,
        policy: Policy | None = ...,
        **_params: _ParamsType,
    ) -> None: ...
