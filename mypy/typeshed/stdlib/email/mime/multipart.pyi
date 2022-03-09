from email.message import Message
from email.mime.base import MIMEBase
from email.policy import Policy
from typing import Optional, Sequence, Union

__all__ = ["MIMEMultipart"]

_ParamsType = Union[str, None, tuple[str, Optional[str], str]]

class MIMEMultipart(MIMEBase):
    def __init__(
        self,
        _subtype: str = ...,
        boundary: str | None = ...,
        _subparts: Sequence[Message] | None = ...,
        *,
        policy: Policy | None = ...,
        **_params: _ParamsType,
    ) -> None: ...
