class CompilerOptions:
    def __init__(self, strip_asserts: bool = False, multi_file: bool = False,
                 verbose: bool = False, separate: bool = False) -> None:
        self.strip_asserts = strip_asserts
        self.multi_file = multi_file
        self.verbose = verbose
        self.separate = separate
        self.global_opts = not separate
