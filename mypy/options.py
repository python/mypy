from mypy import defaults
from mypy import build

class Options:
    _instance = None  # type: 'Options'

    @classmethod
    def get_options(cls) -> 'Options':
        if cls._instance is None:
            cls._instance = Options()
        return cls._instance

    def __init__(self) -> None:
        # Set default options.
        self.target = build.TYPE_CHECK
        self.build_flags = []  # type: List[str]
        self.pyversion = defaults.PYTHON3_VERSION
        self.custom_typing_module = None  # type: str
        self.report_dirs = {}  # type: Dict[str, str]
        self.python_path = False
        self.dirty_stubs = False
        self.pdb = False
        self.implicit_any = False

