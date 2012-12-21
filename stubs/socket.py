# Stubs for socket
# Ron Murawski <ron@horizonchess.com>

# based on: http://docs.python.org/3.2/library/socket.html
# see: http://hg.python.org/cpython/file/3d0686d90f55/Lib/socket.py
# see: http://nullege.com/codes/search/socket

# ----- variables and constants -----

int AF_UNIX
int AF_INET
int AF_INET6
int SOCK_STREAM
int SOCK_DGRAM
int SOCK_RAW
int SOCK_RDM
int SOCK_SEQPACKET
int SOCK_CLOEXEC
int SOCK_NONBLOCK
int SOMAXCONN
bool has_ipv6
float _GLOBAL_DEFAULT_TIMEOUT
any SocketType
any SocketIO


# the following constants are included with Python 3.2.3 (Ubuntu)
# some of the constants may be Linux-only
# all Windows/Mac-specific constants are absent
int AF_APPLETALK
int AF_ASH
int AF_ATMPVC
int AF_ATMSVC
int AF_AX25
int AF_BLUETOOTH
int AF_BRIDGE
int AF_DECnet
int AF_ECONET
int AF_IPX
int AF_IRDA
int AF_KEY
int AF_LLC
int AF_NETBEUI
int AF_NETLINK
int AF_NETROM
int AF_PACKET
int AF_PPPOX
int AF_ROSE
int AF_ROUTE
int AF_SECURITY
int AF_SNA
int AF_TIPC
int AF_UNSPEC
int AF_WANPIPE
int AF_X25
int AI_ADDRCONFIG
int AI_ALL
int AI_CANONNAME
int AI_NUMERICHOST
int AI_NUMERICSERV
int AI_PASSIVE
int AI_V4MAPPED
int BDADDR_ANY
int BDADDR_LOCAL
int BTPROTO_HCI
int BTPROTO_L2CAP
int BTPROTO_RFCOMM
int BTPROTO_SCO
int CAPI
int EAGAIN
int EAI_ADDRFAMILY
int EAI_AGAIN
int EAI_BADFLAGS
int EAI_FAIL
int EAI_FAMILY
int EAI_MEMORY
int EAI_NODATA
int EAI_NONAME
int EAI_OVERFLOW
int EAI_SERVICE
int EAI_SOCKTYPE
int EAI_SYSTEM
int EBADF
int EINTR
int EWOULDBLOCK
int HCI_DATA_DIR
int HCI_FILTER
int HCI_TIME_STAMP
int INADDR_ALLHOSTS_GROUP
int INADDR_ANY
int INADDR_BROADCAST
int INADDR_LOOPBACK
int INADDR_MAX_LOCAL_GROUP
int INADDR_NONE
int INADDR_UNSPEC_GROUP
int IPPORT_RESERVED
int IPPORT_USERRESERVED
int IPPROTO_AH
int IPPROTO_DSTOPTS
int IPPROTO_EGP
int IPPROTO_ESP
int IPPROTO_FRAGMENT
int IPPROTO_GRE
int IPPROTO_HOPOPTS
int IPPROTO_ICMP
int IPPROTO_ICMPV6
int IPPROTO_IDP
int IPPROTO_IGMP
int IPPROTO_IP
int IPPROTO_IPIP
int IPPROTO_IPV6
int IPPROTO_NONE
int IPPROTO_PIM
int IPPROTO_PUP
int IPPROTO_RAW
int IPPROTO_ROUTING
int IPPROTO_RSVP
int IPPROTO_TCP
int IPPROTO_TP
int IPPROTO_UDP
int IPV6_CHECKSUM
int IPV6_DSTOPTS
int IPV6_HOPLIMIT
int IPV6_HOPOPTS
int IPV6_JOIN_GROUP
int IPV6_LEAVE_GROUP
int IPV6_MULTICAST_HOPS
int IPV6_MULTICAST_IF
int IPV6_MULTICAST_LOOP
int IPV6_NEXTHOP
int IPV6_PKTINFO
int IPV6_RECVDSTOPTS
int IPV6_RECVHOPLIMIT
int IPV6_RECVHOPOPTS
int IPV6_RECVPKTINFO
int IPV6_RECVRTHDR
int IPV6_RECVTCLASS
int IPV6_RTHDR
int IPV6_RTHDRDSTOPTS
int IPV6_RTHDR_TYPE_0
int IPV6_TCLASS
int IPV6_UNICAST_HOPS
int IPV6_V6ONLY
int IP_ADD_MEMBERSHIP
int IP_DEFAULT_MULTICAST_LOOP
int IP_DEFAULT_MULTICAST_TTL
int IP_DROP_MEMBERSHIP
int IP_HDRINCL
int IP_MAX_MEMBERSHIPS
int IP_MULTICAST_IF
int IP_MULTICAST_LOOP
int IP_MULTICAST_TTL
int IP_OPTIONS
int IP_RECVOPTS
int IP_RECVRETOPTS
int IP_RETOPTS
int IP_TOS
int IP_TTL
int MSG_CTRUNC
int MSG_DONTROUTE
int MSG_DONTWAIT
int MSG_EOR
int MSG_OOB
int MSG_PEEK
int MSG_TRUNC
int MSG_WAITALL
int NETLINK_DNRTMSG
int NETLINK_FIREWALL
int NETLINK_IP6_FW
int NETLINK_NFLOG
int NETLINK_ROUTE
int NETLINK_USERSOCK
int NETLINK_XFRM
int NI_DGRAM
int NI_MAXHOST
int NI_MAXSERV
int NI_NAMEREQD
int NI_NOFQDN
int NI_NUMERICHOST
int NI_NUMERICSERV
int PACKET_BROADCAST
int PACKET_FASTROUTE
int PACKET_HOST
int PACKET_LOOPBACK
int PACKET_MULTICAST
int PACKET_OTHERHOST
int PACKET_OUTGOING
int PF_PACKET
int SHUT_RD
int SHUT_RDWR
int SHUT_WR
int SOL_HCI
int SOL_IP
int SOL_SOCKET
int SOL_TCP
int SOL_TIPC
int SOL_UDP
int SO_ACCEPTCONN
int SO_BROADCAST
int SO_DEBUG
int SO_DONTROUTE
int SO_ERROR
int SO_KEEPALIVE
int SO_LINGER
int SO_OOBINLINE
int SO_RCVBUF
int SO_RCVLOWAT
int SO_RCVTIMEO
int SO_REUSEADDR
int SO_SNDBUF
int SO_SNDLOWAT
int SO_SNDTIMEO
int SO_TYPE
int TCP_CORK
int TCP_DEFER_ACCEPT
int TCP_INFO
int TCP_KEEPCNT
int TCP_KEEPIDLE
int TCP_KEEPINTVL
int TCP_LINGER2
int TCP_MAXSEG
int TCP_NODELAY
int TCP_QUICKACK
int TCP_SYNCNT
int TCP_WINDOW_CLAMP
int TIPC_ADDR_ID
int TIPC_ADDR_NAME
int TIPC_ADDR_NAMESEQ
int TIPC_CFG_SRV
int TIPC_CLUSTER_SCOPE
int TIPC_CONN_TIMEOUT
int TIPC_CRITICAL_IMPORTANCE
int TIPC_DEST_DROPPABLE
int TIPC_HIGH_IMPORTANCE
int TIPC_IMPORTANCE
int TIPC_LOW_IMPORTANCE
int TIPC_MEDIUM_IMPORTANCE
int TIPC_NODE_SCOPE
int TIPC_PUBLISHED
int TIPC_SRC_DROPPABLE
int TIPC_SUBSCR_TIMEOUT
int TIPC_SUB_CANCEL
int TIPC_SUB_PORTS
int TIPC_SUB_SERVICE
int TIPC_TOP_SRV
int TIPC_WAIT_FOREVER
int TIPC_WITHDRAWN
int TIPC_ZONE_SCOPE

# ----- classes -----
class socket():
    # --- variables ---
    # socket.error class is a subclass of IOError
    class error(IOError):
        int herror(self, tuple<int, str> address): pass
        int herror(self, tuple<str, int, int, int> address): pass
        int gaierror(self, tuple<int, str> address): pass
        int gaierror(self, tuple<str, int, int, int> address): pass
        int timeout(self, str message=''): pass

    int family
    int type
    int proto
    
    # --- methods ---
    tuple<SocketType, int> accept(self): pass
    void bind(self, str address): pass
    void close(self): pass
    void connect(self, tuple<str, int> address): pass  # AF_INET or AF_UNIX
    void connect(self, tuple<str, int, int, int> address): pass  # AF_INET6
    int connect_ex(self, tuple<str, int> address): pass  # AF_INET or AF_UNIX
    int connect_ex(self, tuple<str, int, int, int> address): pass  # AF_INET6
    int detach(self): pass
    int fileno(self): pass
    
    # return type is tuple<str, int> if AF_INET/AF_UNIX
    # and tuple<str, int, int, int> if AF_INET6
    any getpeername(self): pass
    any getsockname(self): pass
    
    bytes getsockopt(self, int level, str optname): pass
    bytes getsockopt(self, int level, str optname, int buflen): pass
    float gettimeout(self): pass
    void ioctl(self, object control, tuple<int, int, int> option): pass
    void listen(self, int backlog): pass
    SocketIO makefile(self, str mode='r', int buffering=None, 
                      str encoding=None, str errors=None, str newline=None): 
        pass
    bytes recv(self, int bufsize, int flags=0): pass
    
    # return type is tuple<str, int> if AF_INET/AF_UNIX
    # and tuple<str, int, int, int> if AF_INET6
    any recvfrom(self, int bufsize, int flags=0): pass
    any recvfrom_into(self, bytes buffer, int nbytes, int flags=0): pass
    any recv_into(self, bytes buffer, int nbytes, int flags=0): pass
    
    int send(self, bytes data, flags=0): pass
    any sendall(self, bytes data, flags=0): pass  # rettype: None on success
    
    int sendto(self, bytes data, tuple<str, int> address, int flags=0): pass
    int sendto(self, bytes data, tuple<str, int, int, int> address, 
               int flags=0): pass
    void setblocking(self, bool flag): pass
    void settimeout(self, float? value): pass
    setsockopt(self, int level, str optname, int value): pass
    void setsockopt(self, int level, str optname, bytes value): pass
    void shutdown(self, int how): pass
    

# ----- functions -----
# TODO returns socket object
object create_connection(tuple<str, int>address, 
                         float timeout=_GLOBAL_DEFAULT_TIMEOUT,
                         tuple<str, int> source_address=None): pass
object create_connection(tuple<str, int, int, int> address, 
                         float timeout=_GLOBAL_DEFAULT_TIMEOUT,
                         tuple<str, int>source_address=None): pass

# return type is different for AF_INET/AF_UNIX or AF_INET6
any getaddrinfo(str host, int port, int family=0, int type=0, int proto=0, 
                int flags=0): pass
# 5th tuple in return type is sockaddr, a tuple describing a socket address, 
# whose format depends on the returned family (a (address, port) 2-tuple for 
# AF_INET, ie: tuple<int, int, int, str, tuple<str, int>> and
# a (address, port, flow info, scope id) 4-tuple for AF_INET6)
# ie: tuple<int, int, int, str, tuple<str, int, int, int>>
# ret object is meant to be passed to the socket.connect() method.

str getfqdn(str name= ''): pass
str gethostbyname(str hostname): pass
tuple<str, list<str>, list<str>> gethostbyname_ex(str hostname): pass
str gethostname(): pass
tuple<str, list<str>, list<str>> gethostbyaddr(str ip_address): pass
tuple<str, int> getnameinfo(object sockaddr, int flags): pass
int getprotobyname(str protocolname): pass
int getservbyname(str servicename, str protocolname='tcp'): pass
str getservbyport(int port, str protocolname='tcp'): pass
SocketType socket(int family=AF_INET, int type=SOCK_STREAM, int proto=0): pass
tuple<SocketType, SocketType> socketpair(int family=AF_INET,
                                         int type=SOCK_STREAM, int proto=0
                                         ):pass
SocketType fromfd(int fd, family, int type, int proto=0): pass
int ntohl(int x): pass  # param & ret val are 32-bit ints
int ntohs(int x): pass  # param & ret val are 16-bit ints
int htonl(int x): pass  # param & ret val are 32-bit ints
int htons(int x): pass  # param & ret val are 16-bit ints
bytes inet_aton(str ip_string): pass  # ret val 4 bytes in length
str inet_ntoa(bytes packed_ip): pass
bytes inet_pton(int address_family, str ip_string): pass
str inet_ntop(int address_family, bytes packed_ip): pass
float getdefaulttimeout(): pass
void setdefaulttimeout(float timeout): pass

