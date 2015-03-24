# Stubs for ssl (Python 3.4)

from typing import Undefined, Any
from enum import Enum as _Enum
from socket import socket
from collections import namedtuple

class SSLError(OSError): pass
class SSLEOFError(SSLError): pass
class SSLSyscallError(SSLError): pass
class SSLWantReadError(SSLError): pass
class SSLWantWriteError(SSLError): pass
class SSLZeroReturnError(SSLError): pass

OPENSSL_VERSION = Undefined(str)
OPENSSL_VERSION_INFO = Undefined(Any)
OPENSSL_VERSION_NUMBER = Undefined(int)

VERIFY_CRL_CHECK_CHAIN = Undefined(int)
VERIFY_CRL_CHECK_LEAF = Undefined(int)
VERIFY_DEFAULT = Undefined(int)
VERIFY_X509_STRICT = Undefined(int)

ALERT_DESCRIPTION_ACCESS_DENIED = Undefined(int)
ALERT_DESCRIPTION_BAD_CERTIFICATE = Undefined(int)
ALERT_DESCRIPTION_BAD_CERTIFICATE_HASH_VALUE = Undefined(int)
ALERT_DESCRIPTION_BAD_CERTIFICATE_STATUS_RESPONSE = Undefined(int)
ALERT_DESCRIPTION_BAD_RECORD_MAC = Undefined(int)
ALERT_DESCRIPTION_CERTIFICATE_EXPIRED = Undefined(int)
ALERT_DESCRIPTION_CERTIFICATE_REVOKED = Undefined(int)
ALERT_DESCRIPTION_CERTIFICATE_UNKNOWN = Undefined(int)
ALERT_DESCRIPTION_CERTIFICATE_UNOBTAINABLE = Undefined(int)
ALERT_DESCRIPTION_CLOSE_NOTIFY = Undefined(int)
ALERT_DESCRIPTION_DECODE_ERROR = Undefined(int)
ALERT_DESCRIPTION_DECOMPRESSION_FAILURE = Undefined(int)
ALERT_DESCRIPTION_DECRYPT_ERROR = Undefined(int)
ALERT_DESCRIPTION_HANDSHAKE_FAILURE = Undefined(int)
ALERT_DESCRIPTION_ILLEGAL_PARAMETER = Undefined(int)
ALERT_DESCRIPTION_INSUFFICIENT_SECURITY = Undefined(int)
ALERT_DESCRIPTION_INTERNAL_ERROR = Undefined(int)
ALERT_DESCRIPTION_NO_RENEGOTIATION = Undefined(int)
ALERT_DESCRIPTION_PROTOCOL_VERSION = Undefined(int)
ALERT_DESCRIPTION_RECORD_OVERFLOW = Undefined(int)
ALERT_DESCRIPTION_UNEXPECTED_MESSAGE = Undefined(int)
ALERT_DESCRIPTION_UNKNOWN_CA = Undefined(int)
ALERT_DESCRIPTION_UNKNOWN_PSK_IDENTITY = Undefined(int)
ALERT_DESCRIPTION_UNRECOGNIZED_NAME = Undefined(int)
ALERT_DESCRIPTION_UNSUPPORTED_CERTIFICATE = Undefined(int)
ALERT_DESCRIPTION_UNSUPPORTED_EXTENSION = Undefined(int)
ALERT_DESCRIPTION_USER_CANCELLED = Undefined(int)

OP_ALL = Undefined(int)
OP_CIPHER_SERVER_PREFERENCE = Undefined(int)
OP_NO_COMPRESSION = Undefined(int)
OP_NO_SSLv2 = Undefined(int)
OP_NO_SSLv3 = Undefined(int)
OP_NO_TLSv1 = Undefined(int)
OP_NO_TLSv1_1 = Undefined(int)
OP_NO_TLSv1_2 = Undefined(int)
OP_SINGLE_DH_USE = Undefined(int)
OP_SINGLE_ECDH_USE = Undefined(int)

SSL_ERROR_EOF = Undefined(int)
SSL_ERROR_INVALID_ERROR_CODE = Undefined(int)
SSL_ERROR_SSL = Undefined(int)
SSL_ERROR_SYSCALL = Undefined(int)
SSL_ERROR_WANT_CONNECT = Undefined(int)
SSL_ERROR_WANT_READ = Undefined(int)
SSL_ERROR_WANT_WRITE = Undefined(int)
SSL_ERROR_WANT_X509_LOOKUP = Undefined(int)
SSL_ERROR_ZERO_RETURN = Undefined(int)

CERT_NONE = Undefined(int)
CERT_OPTIONAL = Undefined(int)
CERT_REQUIRED = Undefined(int)

PROTOCOL_SSLv23 = Undefined(int)
PROTOCOL_SSLv3 = Undefined(int)
PROTOCOL_TLSv1 = Undefined(int)
PROTOCOL_TLSv1_1 = Undefined(int)
PROTOCOL_TLSv1_2 = Undefined(int)

HAS_ECDH = Undefined(bool)
HAS_NPN = Undefined(bool)
HAS_SNI = Undefined(bool)

def RAND_add(string, entropy): pass
def RAND_bytes(n): pass
def RAND_egd(path): pass
def RAND_pseudo_bytes(n): pass
def RAND_status(): pass

socket_error = OSError

CHANNEL_BINDING_TYPES = Undefined(Any)

class CertificateError(ValueError): pass

def match_hostname(cert, hostname): pass

DefaultVerifyPaths = namedtuple(
    'DefaultVerifyPaths',
    'cafile capath openssl_cafile_env openssl_cafile openssl_capath_env openssl_capath')

def get_default_verify_paths(): pass

class _ASN1Object:
    def __new__(cls, oid): pass
    @classmethod
    def fromnid(cls, nid): pass
    @classmethod
    def fromname(cls, name): pass

class Purpose(_ASN1Object, _Enum):
    SERVER_AUTH = Undefined(Any)
    CLIENT_AUTH = Undefined(Any)

class _SSLContext:
    check_hostname = Undefined(Any)
    options = Undefined(Any)
    verify_flags = Undefined(Any)
    verify_mode = Undefined(Any)
    def __init__(self, *args, **kwargs): pass
    def _set_npn_protocols(self, *args, **kwargs): pass
    def _wrap_socket(self, *args, **kwargs): pass
    def cert_store_stats(self): pass
    def get_ca_certs(self, binary_form=False): pass
    def load_cert_chain(self, *args, **kwargs): pass
    def load_dh_params(self, *args, **kwargs): pass
    def load_verify_locations(self, *args, **kwargs): pass
    def session_stats(self, *args, **kwargs): pass
    def set_ciphers(self, *args, **kwargs): pass
    def set_default_verify_paths(self, *args, **kwargs): pass
    def set_ecdh_curve(self, *args, **kwargs): pass
    def set_servername_callback(self, method): pass

class SSLContext(_SSLContext):
    def __new__(cls, protocol, *args, **kwargs): pass
    protocol = Undefined(Any)
    def __init__(self, protocol): pass
    def wrap_socket(self, sock, server_side=False, do_handshake_on_connect=True,
                    suppress_ragged_eofs=True, server_hostname=None): pass
    def set_npn_protocols(self, npn_protocols): pass
    def load_default_certs(self, purpose=Undefined): pass

def create_default_context(purpose=Undefined, *, cafile=None, capath=None, cadata=None): pass

class SSLSocket(socket):
    keyfile = Undefined(Any)
    certfile = Undefined(Any)
    cert_reqs = Undefined(Any)
    ssl_version = Undefined(Any)
    ca_certs = Undefined(Any)
    ciphers = Undefined(Any)
    server_side = Undefined(Any)
    server_hostname = Undefined(Any)
    do_handshake_on_connect = Undefined(Any)
    suppress_ragged_eofs = Undefined(Any)
    context = Undefined(Any)  # TODO: This should be a property.
    def __init__(self, sock=None, keyfile=None, certfile=None, server_side=False,
                 cert_reqs=Undefined, ssl_version=Undefined, ca_certs=None,
                 do_handshake_on_connect=True, family=Undefined, type=Undefined, proto=0,
                 fileno=None, suppress_ragged_eofs=True, npn_protocols=None, ciphers=None,
                 server_hostname=None, _context=None): pass
    def dup(self): pass
    def read(self, len=0, buffer=None): pass
    def write(self, data): pass
    def getpeercert(self, binary_form=False): pass
    def selected_npn_protocol(self): pass
    def cipher(self): pass
    def compression(self): pass
    def send(self, data, flags=0): pass
    def sendto(self, data, flags_or_addr, addr=None): pass
    def sendmsg(self, *args, **kwargs): pass
    def sendall(self, data, flags=0): pass
    def recv(self, buflen=1024, flags=0): pass
    def recv_into(self, buffer, nbytes=None, flags=0): pass
    def recvfrom(self, buflen=1024, flags=0): pass
    def recvfrom_into(self, buffer, nbytes=None, flags=0): pass
    def recvmsg(self, *args, **kwargs): pass
    def recvmsg_into(self, *args, **kwargs): pass
    def pending(self): pass
    def shutdown(self, how): pass
    def unwrap(self): pass
    def do_handshake(self, block=False): pass
    def connect(self, addr): pass
    def connect_ex(self, addr): pass
    def accept(self): pass
    def get_channel_binding(self, cb_type=''): pass

def wrap_socket(sock, keyfile=None, certfile=None, server_side=False, cert_reqs=Undefined,
                ssl_version=Undefined, ca_certs=None, do_handshake_on_connect=True,
                suppress_ragged_eofs=True, ciphers=None): pass
def cert_time_to_seconds(cert_time): pass

PEM_HEADER = Undefined(Any)
PEM_FOOTER = Undefined(Any)

def DER_cert_to_PEM_cert(der_cert_bytes): pass
def PEM_cert_to_DER_cert(pem_cert_string): pass
def get_server_certificate(addr, ssl_version=Undefined, ca_certs=None): pass
def get_protocol_name(protocol_code): pass
