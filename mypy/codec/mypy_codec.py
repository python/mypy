from __future__ import absolute_import

import codecs
import traceback
from encodings import utf_8
from io import BytesIO

from .tokenizer import mypy_tokenize, mypy_untokenize


def mypy_transform(stream):
    try:
        output = mypy_untokenize(mypy_tokenize(stream.readline))
    except Exception as ex:
        print(ex)
        traceback.print_exc()
        raise

    return output


def mypy_transform_string(text):
    stream = BytesIO(text)
    return mypy_transform(stream)


def mypy_decode(input, errors='strict'):
    return utf_8.decode(mypy_transform_string(input), errors)


class MyPyIncrementalDecoder(utf_8.IncrementalDecoder):
    def decode(self, input, final=False):
        self.buffer += input
        if final:
            buff = self.buffer
            self.buffer = ''
            return super(MyPyIncrementalDecoder, self).decode(
                mypy_transform_string(buff), final=True)


class MyPyStreamReader(utf_8.StreamReader):
    def __init__(self, *args, **kwargs):
        codecs.StreamReader.__init__(self, *args, **kwargs)
        self.stream = BytesIO(mypy_transform(self.stream))
