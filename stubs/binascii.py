# Stubs for binascii

# Based on http://docs.python.org/3.2/library/binascii.html

bytes a2b_uu(bytes string): pass
bytes b2a_uu(bytes data): pass
bytes a2b_base64(bytes string): pass
bytes b2a_base64(bytes data): pass
bytes a2b_qp(bytes string, bool header=False): pass
bytes b2a_qp(bytes data, bool quotetabs=False, bool istext=True,
             bool header=False): pass
bytes a2b_hqx(bytes string): pass
bytes rledecode_hqx(bytes data): pass
bytes rlecode_hqx(bytes data): pass
bytes b2a_hqx(bytes data): pass
int crc_hqx(bytes data, int crc): pass
int crc32(bytes data, int crc=None): pass
bytes b2a_hex(bytes data): pass
bytes hexlify(bytes data): pass
bytes a2b_hex(bytes hexstr): pass
bytes unhexlify(bytes hexlify): pass

class Error(Exception): pass
class Incomplete(Exception): pass
