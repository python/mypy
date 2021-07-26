from _typeshed import StrOrBytesPath
from typing import NamedTuple, Optional, Union

class SndHeaders(NamedTuple):
    filetype: str
    framerate: int
    nchannels: int
    nframes: int
    sampwidth: Union[int, str]

def what(filename: StrOrBytesPath) -> Optional[SndHeaders]: ...
def whathdr(filename: StrOrBytesPath) -> Optional[SndHeaders]: ...
