import json
from typing import Dict, Any

json_kwargs : Dict[str, Any] = dict(indent = 2)

json.dumps({}, **json_kwargs)

json_kwargs_error = dict(indent = 0)

json.dumps({}, **json_kwargs_error)