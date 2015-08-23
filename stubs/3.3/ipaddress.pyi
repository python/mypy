

class _IPAddressBase:

    def __init__(self, address): pass


class _BaseAddress(_IPAddressBase):
    pass


class _BaseV4:
    pass


class IPv4Address(_BaseV4, _BaseAddress):
    pass

