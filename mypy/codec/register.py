from __future__ import absolute_import

import codecs
import encodings
import sys


def search_function(encoding):
    if encoding != 'mypy':
        return None
    # Assume utf8 encoding
    utf8 = encodings.search_function('utf8')
    if sys.version_info[0] == 3:  # Python 3
        return utf8
    else:  # Python 2
        from .mypy_codec import mypy_decode, MyPyIncrementalDecoder, MyPyStreamReader
        return codecs.CodecInfo(name='mypy',
                                encode=utf8.encode,
                                decode=mypy_decode,
                                incrementalencoder=utf8.incrementalencoder,
                                incrementaldecoder=MyPyIncrementalDecoder,
                                streamreader=MyPyStreamReader,
                                streamwriter=utf8.streamwriter)

codecs.register(search_function)


def main():
    fn = sys.argv[1]
    with open(fn) as fp:
        data = fp.read()
    print(codecs.decode(data, 'mypy'))

if __name__ == '__main__':
    main()
