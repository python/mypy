def module_prefix(target: str) -> str:
    # TODO: This assumes no nested modules.
    return target.split('.', 1)[0]
