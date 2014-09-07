# Stubs for socket
# Ron Murawski <ron@horizonchess.com>

# based on: http://docs.python.org/3.2/library/socket.html
# see: http://hg.python.org/cpython/file/3d0686d90f55/Lib/socket.py
# see: http://nullege.com/codes/search/socket

from typing import Undefined, Any, Tuple, overload, List

# ----- variables and constants -----

AF_UNIX = 0
AF_INET = 0
AF_INET6 = 0
SOCK_STREAM = 0
SOCK_DGRAM = 0
SOCK_RAW = 0
SOCK_RDM = 0
SOCK_SEQPACKET = 0
SOCK_CLOEXEC = 0
SOCK_NONBLOCK = 0
SOMAXCONN = 0
has_ipv6 = False
_GLOBAL_DEFAULT_TIMEOUT = 0.0
SocketType = Undefined(Any)
SocketIO = Undefined(Any)


# the following constants are included with Python 3.2.3 (Ubuntu)
# some of the constants may be Linux-only
# all Windows/Mac-specific constants are absent
AF_APPLETALK = 0
AF_ASH = 0
AF_ATMPVC = 0
AF_ATMSVC = 0
AF_AX25 = 0
AF_BLUETOOTH = 0
AF_BRIDGE = 0
AF_DECnet = 0
AF_ECONET = 0
AF_IPX = 0
AF_IRDA = 0
AF_KEY = 0
AF_LLC = 0
AF_NETBEUI = 0
AF_NETLINK = 0
AF_NETROM = 0
AF_PACKET = 0
AF_PPPOX = 0
AF_ROSE = 0
AF_ROUTE = 0
AF_SECURITY = 0
AF_SNA = 0
AF_TIPC = 0
AF_UNSPEC = 0
AF_WANPIPE = 0
AF_X25 = 0
AI_ADDRCONFIG = 0
AI_ALL = 0
AI_CANONNAME = 0
AI_NUMERICHOST = 0
AI_NUMERICSERV = 0
AI_PASSIVE = 0
AI_V4MAPPED = 0
BDADDR_ANY = 0
BDADDR_LOCAL = 0
BTPROTO_HCI = 0
BTPROTO_L2CAP = 0
BTPROTO_RFCOMM = 0
BTPROTO_SCO = 0
CAPI = 0
EAGAIN = 0
EAI_ADDRFAMILY = 0
EAI_AGAIN = 0
EAI_BADFLAGS = 0
EAI_FAIL = 0
EAI_FAMILY = 0
EAI_MEMORY = 0
EAI_NODATA = 0
EAI_NONAME = 0
EAI_OVERFLOW = 0
EAI_SERVICE = 0
EAI_SOCKTYPE = 0
EAI_SYSTEM = 0
EBADF = 0
EINTR = 0
EWOULDBLOCK = 0
HCI_DATA_DIR = 0
HCI_FILTER = 0
HCI_TIME_STAMP = 0
INADDR_ALLHOSTS_GROUP = 0
INADDR_ANY = 0
INADDR_BROADCAST = 0
INADDR_LOOPBACK = 0
INADDR_MAX_LOCAL_GROUP = 0
INADDR_NONE = 0
INADDR_UNSPEC_GROUP = 0
IPPORT_RESERVED = 0
IPPORT_USERRESERVED = 0
IPPROTO_AH = 0
IPPROTO_DSTOPTS = 0
IPPROTO_EGP = 0
IPPROTO_ESP = 0
IPPROTO_FRAGMENT = 0
IPPROTO_GRE = 0
IPPROTO_HOPOPTS = 0
IPPROTO_ICMP = 0
IPPROTO_ICMPV6 = 0
IPPROTO_IDP = 0
IPPROTO_IGMP = 0
IPPROTO_IP = 0
IPPROTO_IPIP = 0
IPPROTO_IPV6 = 0
IPPROTO_NONE = 0
IPPROTO_PIM = 0
IPPROTO_PUP = 0
IPPROTO_RAW = 0
IPPROTO_ROUTING = 0
IPPROTO_RSVP = 0
IPPROTO_TCP = 0
IPPROTO_TP = 0
IPPROTO_UDP = 0
IPV6_CHECKSUM = 0
IPV6_DSTOPTS = 0
IPV6_HOPLIMIT = 0
IPV6_HOPOPTS = 0
IPV6_JOIN_GROUP = 0
IPV6_LEAVE_GROUP = 0
IPV6_MULTICAST_HOPS = 0
IPV6_MULTICAST_IF = 0
IPV6_MULTICAST_LOOP = 0
IPV6_NEXTHOP = 0
IPV6_PKTINFO = 0
IPV6_RECVDSTOPTS = 0
IPV6_RECVHOPLIMIT = 0
IPV6_RECVHOPOPTS = 0
IPV6_RECVPKTINFO = 0
IPV6_RECVRTHDR = 0
IPV6_RECVTCLASS = 0
IPV6_RTHDR = 0
IPV6_RTHDRDSTOPTS = 0
IPV6_RTHDR_TYPE_0 = 0
IPV6_TCLASS = 0
IPV6_UNICAST_HOPS = 0
IPV6_V6ONLY = 0
IP_ADD_MEMBERSHIP = 0
IP_DEFAULT_MULTICAST_LOOP = 0
IP_DEFAULT_MULTICAST_TTL = 0
IP_DROP_MEMBERSHIP = 0
IP_HDRINCL = 0
IP_MAX_MEMBERSHIPS = 0
IP_MULTICAST_IF = 0
IP_MULTICAST_LOOP = 0
IP_MULTICAST_TTL = 0
IP_OPTIONS = 0
IP_RECVOPTS = 0
IP_RECVRETOPTS = 0
IP_RETOPTS = 0
IP_TOS = 0
IP_TTL = 0
MSG_CTRUNC = 0
MSG_DONTROUTE = 0
MSG_DONTWAIT = 0
MSG_EOR = 0
MSG_OOB = 0
MSG_PEEK = 0
MSG_TRUNC = 0
MSG_WAITALL = 0
NETLINK_DNRTMSG = 0
NETLINK_FIREWALL = 0
NETLINK_IP6_FW = 0
NETLINK_NFLOG = 0
NETLINK_ROUTE = 0
NETLINK_USERSOCK = 0
NETLINK_XFRM = 0
NI_DGRAM = 0
NI_MAXHOST = 0
NI_MAXSERV = 0
NI_NAMEREQD = 0
NI_NOFQDN = 0
NI_NUMERICHOST = 0
NI_NUMERICSERV = 0
PACKET_BROADCAST = 0
PACKET_FASTROUTE = 0
PACKET_HOST = 0
PACKET_LOOPBACK = 0
PACKET_MULTICAST = 0
PACKET_OTHERHOST = 0
PACKET_OUTGOING = 0
PF_PACKET = 0
SHUT_RD = 0
SHUT_RDWR = 0
SHUT_WR = 0
SOL_HCI = 0
SOL_IP = 0
SOL_SOCKET = 0
SOL_TCP = 0
SOL_TIPC = 0
SOL_UDP = 0
SO_ACCEPTCONN = 0
SO_BROADCAST = 0
SO_DEBUG = 0
SO_DONTROUTE = 0
SO_ERROR = 0
SO_KEEPALIVE = 0
SO_LINGER = 0
SO_OOBINLINE = 0
SO_RCVBUF = 0
SO_RCVLOWAT = 0
SO_RCVTIMEO = 0
SO_REUSEADDR = 0
SO_SNDBUF = 0
SO_SNDLOWAT = 0
SO_SNDTIMEO = 0
SO_TYPE = 0
TCP_CORK = 0
TCP_DEFER_ACCEPT = 0
TCP_INFO = 0
TCP_KEEPCNT = 0
TCP_KEEPIDLE = 0
TCP_KEEPINTVL = 0
TCP_LINGER2 = 0
TCP_MAXSEG = 0
TCP_NODELAY = 0
TCP_QUICKACK = 0
TCP_SYNCNT = 0
TCP_WINDOW_CLAMP = 0
TIPC_ADDR_ID = 0
TIPC_ADDR_NAME = 0
TIPC_ADDR_NAMESEQ = 0
TIPC_CFG_SRV = 0
TIPC_CLUSTER_SCOPE = 0
TIPC_CONN_TIMEOUT = 0
TIPC_CRITICAL_IMPORTANCE = 0
TIPC_DEST_DROPPABLE = 0
TIPC_HIGH_IMPORTANCE = 0
TIPC_IMPORTANCE = 0
TIPC_LOW_IMPORTANCE = 0
TIPC_MEDIUM_IMPORTANCE = 0
TIPC_NODE_SCOPE = 0
TIPC_PUBLISHED = 0
TIPC_SRC_DROPPABLE = 0
TIPC_SUBSCR_TIMEOUT = 0
TIPC_SUB_CANCEL = 0
TIPC_SUB_PORTS = 0
TIPC_SUB_SERVICE = 0
TIPC_TOP_SRV = 0
TIPC_WAIT_FOREVER = 0
TIPC_WITHDRAWN = 0
TIPC_ZONE_SCOPE = 0


# ----- exceptions -----
class error(IOError):
    pass

class herror(error):
    def __init__(self, herror: int, string: str) -> None: pass

class gaierror(error):
    def __init__(self, error: int, string: str) -> None: pass

class timeout(error):
    pass


# Addresses can be either tuples of varying lengths (AF_INET, AF_INET6,
# AF_NETLINK, AF_TIPC) or strings (AF_UNIX).

# TODO AF_PACKET and AF_BLUETOOTH address objects


# ----- classes -----
class socket:
    family = 0
    type = 0
    proto = 0

    def __init__(self, family: int = AF_INET, type: int = SOCK_STREAM,
                 proto: int = 0, fileno: int = None) -> None: pass

    # --- methods ---
    # second tuple item is an address
    def accept(self) -> Tuple['socket', Any]: pass

    @overload
    def bind(self, address: tuple) -> None: pass
    @overload
    def bind(self, address: str) -> None: pass

    def close(self) -> None: pass

    @overload
    def connect(self, address: tuple) -> None: pass
    @overload
    def connect(self, address: str) -> None: pass

    @overload
    def connect_ex(self, address: tuple) -> int: pass
    @overload
    def connect_ex(self, address: str) -> int: pass

    def detach(self) -> int: pass
    def fileno(self) -> int: pass

    # return value is an address
    def getpeername(self) -> Any: pass
    def getsockname(self) -> Any: pass

    @overload
    def getsockopt(self, level: int, optname: str) -> bytes: pass
    @overload
    def getsockopt(self, level: int, optname: str, buflen: int) -> bytes: pass

    def gettimeout(self) -> float: pass
    def ioctl(self, control: object,
              option: Tuple[int, int, int]) -> None: pass
    def listen(self, backlog: int) -> None: pass
    # TODO the return value may be BinaryIO or TextIO, depending on mode
    def makefile(self, mode: str = 'r', buffering: int = None,
                 encoding: str = None, errors: str = None,
                 newline: str = None) -> Any:
        pass
    def recv(self, bufsize: int, flags: int = 0) -> bytes: pass

    # return type is an address
    def recvfrom(self, bufsize: int, flags: int = 0) -> Any: pass
    def recvfrom_into(self, buffer: bytes, nbytes: int,
                      flags: int = 0) -> Any: pass
    def recv_into(self, buffer: bytes, nbytes: int,
                  flags: int = 0) -> Any: pass
    def send(self, data: bytes, flags=0) -> int: pass
    def sendall(self, data: bytes, flags=0) -> Any:
        pass # return type: None on success

    @overload
    def sendto(self, data: bytes, address: tuple, flags: int = 0) -> int: pass
    @overload
    def sendto(self, data: bytes, address: str, flags: int = 0) -> int: pass

    def setblocking(self, flag: bool) -> None: pass
    # TODO None valid for the value argument
    def settimeout(self, value: float) -> None: pass

    @overload
    def setsockopt(self, level: int, optname: str, value: int) -> None: pass
    @overload
    def setsockopt(self, level: int, optname: str, value: bytes) -> None: pass

    def shutdown(self, how: int) -> None: pass


# ----- functions -----
def create_connection(address: Tuple[str, int],
                      timeout: float = _GLOBAL_DEFAULT_TIMEOUT,
                      source_address: Tuple[str, int] = None) -> socket: pass

# the 5th tuple item is an address
def getaddrinfo(
        host: str, port: int, family: int = 0, type: int = 0, proto: int = 0,
        flags: int = 0) -> List[Tuple[int, int, int, str, tuple]]:
    pass

def getfqdn(name: str = '') -> str: pass
def gethostbyname(hostname: str) -> str: pass
def gethostbyname_ex(hostname: str) -> Tuple[str, List[str], List[str]]: pass
def gethostname() -> str: pass
def gethostbyaddr(ip_address: str) -> Tuple[str, List[str], List[str]]: pass
def getnameinfo(sockaddr: tuple, flags: int) -> Tuple[str, int]: pass
def getprotobyname(protocolname: str) -> int: pass
def getservbyname(servicename: str, protocolname: str = None) -> int: pass
def getservbyport(port: int, protocolname: str = None) -> str: pass
def socketpair(family: int = AF_INET,
               type: int = SOCK_STREAM,
               proto: int = 0) -> Tuple[socket, socket]: pass
def fromfd(fd: int, family: int, type: int, proto: int = 0) -> socket: pass
def ntohl(x: int) -> int: pass  # param & ret val are 32-bit ints
def ntohs(x: int) -> int: pass  # param & ret val are 16-bit ints
def htonl(x: int) -> int: pass  # param & ret val are 32-bit ints
def htons(x: int) -> int: pass  # param & ret val are 16-bit ints
def inet_aton(ip_string: str) -> bytes: pass  # ret val 4 bytes in length
def inet_ntoa(packed_ip: bytes) -> str: pass
def inet_pton(address_family: int, ip_string: str) -> bytes: pass
def inet_ntop(address_family: int, packed_ip: bytes) -> str: pass
# TODO the timeout may be None
def getdefaulttimeout() -> float: pass
def setdefaulttimeout(timeout: float) -> None: pass
