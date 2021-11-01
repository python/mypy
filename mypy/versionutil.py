from typing import NamedTuple


class VersionInfo(NamedTuple):
    # UNSTABLE, subject to change

    major: int
    minor: int
    patch: int
    release_level: str
    iteration: int
    mypy_version: str
    mypy_release_level: str

    def simple_str(self) -> str:
        result = f"{self.major}.{self.minor}.{self.patch}"
        if self.release_level == "dev":
            result += "+dev"
        if self.release_level == "alpha":
            result += "a"
        elif self.release_level == "beta":
            result += "b"
        elif self.release_level == "rc":
            result += "rc"
        if self.iteration:
            result += str(self.iteration)
        return result
