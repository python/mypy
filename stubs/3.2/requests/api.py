# Stubs for requests.api (Python 3)

import typing

from .models import Response

def request(method: str, url: str, **kwargs) -> Response: pass
def get(url: str, **kwargs) -> Response: pass
def options(url: str, **kwargs) -> Response: pass
def head(url: str, **kwargs) -> Response: pass
def post(url: str, data=None, json=None, **kwargs) -> Response: pass
def put(url: str, data=None, **kwargs) -> Response: pass
def patch(url: str, data=None, **kwargs) -> Response: pass
def delete(url: str, **kwargs) -> Response: pass
