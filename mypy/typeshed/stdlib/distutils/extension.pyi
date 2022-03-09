class Extension:
    name: str
    sources: list[str]
    include_dirs: list[str]
    define_macros: list[tuple[str, str | None]]
    undef_macros: list[str]
    library_dirs: list[str]
    libraries: list[str]
    runtime_library_dirs: list[str]
    extra_objects: list[str]
    extra_compile_args: list[str]
    extra_link_args: list[str]
    export_symbols: list[str]
    swig_opts: list[str]
    depends: list[str]
    language: str | None
    optional: bool | None
    def __init__(
        self,
        name: str,
        sources: list[str],
        include_dirs: list[str] | None = ...,
        define_macros: list[tuple[str, str | None]] | None = ...,
        undef_macros: list[str] | None = ...,
        library_dirs: list[str] | None = ...,
        libraries: list[str] | None = ...,
        runtime_library_dirs: list[str] | None = ...,
        extra_objects: list[str] | None = ...,
        extra_compile_args: list[str] | None = ...,
        extra_link_args: list[str] | None = ...,
        export_symbols: list[str] | None = ...,
        swig_opts: list[str] | None = ...,
        depends: list[str] | None = ...,
        language: str | None = ...,
        optional: bool | None = ...,
    ) -> None: ...
