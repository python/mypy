# Stubs for requests.api (Python 3)

from typing import Union

from .models import Response

def request(method: str, url: Union[str, bytes], **kwargs) -> Response: pass
def get(url: Union[str, bytes], **kwargs) -> Response: pass
def options(url: Union[str, bytes], **kwargs) -> Response: pass
def head(url: Union[str, bytes], **kwargs) -> Response: pass
def post(url: Union[str, bytes], data=None, json=None, **kwargs) -> Response: pass
def put(url: Union[str, bytes], data=None, **kwargs) -> Response: pass
def patch(url: Union[str, bytes], data=None, **kwargs) -> Response: pass
def delete(url: Union[str, bytes], **kwargs) -> Response: pass
