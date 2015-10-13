import codecs

class IncrementalEncoder(codecs.IncrementalEncoder):
    pass
class IncrementalDecoder(codecs.BufferedIncrementalDecoder):
    pass
class StreamWriter(codecs.StreamWriter):
    pass
class StreamReader(codecs.StreamReader):
    pass

def getregentry() -> codecs.CodecInfo: pass
def encode(input: str, errors: str = 'strict') -> bytes: pass
def decode(input: bytes, errors: str = 'strict') -> str: pass
