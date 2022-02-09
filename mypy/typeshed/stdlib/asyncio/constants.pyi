import enum
import sys
from typing_extensions import Literal

LOG_THRESHOLD_FOR_CONNLOST_WRITES: Literal[5]
ACCEPT_RETRY_DELAY: Literal[1]
DEBUG_STACK_DEPTH: Literal[10]
if sys.version_info >= (3, 7):
    SSL_HANDSHAKE_TIMEOUT: float
    SENDFILE_FALLBACK_READBUFFER_SIZE: Literal[262144]

class _SendfileMode(enum.Enum):
    UNSUPPORTED: int
    TRY_NATIVE: int
    FALLBACK: int
