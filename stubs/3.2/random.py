# Stubs for random
# Ron Murawski <ron@horizonchess.com>
# Updated by Jukka Lehtosalo

# based on http://docs.python.org/3.2/library/random.html

# ----- random classes -----

import _random
from typing import (
    Any, typevar, Sequence, List, Function, AbstractSet, Union
)

_T = typevar('_T')

class Random(_random.Random):
    def __init__(self, x: Any = None) -> None: pass
    def seed(self, a: Any = None, version: int = 2) -> None: pass
    def getstate(self) -> tuple: pass
    def setstate(self, state: tuple) -> None: pass
    def getrandbits(self, k: int) -> int: pass
    def randrange(self, start: int, stop: Union[int, None] = None, step: int = 1) -> int: pass
    def randint(self, a: int, b: int) -> int: pass
    def choice(self, seq: Sequence[_T]) -> _T: pass
    def shuffle(self, x: List[Any], random: Union[Function[[], float], None] = None) -> None: pass
    def sample(self, population: Union[Sequence[_T], AbstractSet[_T]], k: int) -> List[_T]: pass
    def random(self) -> float: pass
    def uniform(self, a: float, b: float) -> float: pass
    def triangular(self, low: float = 0.0, high: float = 1.0,
                     mode: float = None) -> float: pass
    def betavariate(self, alpha: float, beta: float) -> float: pass
    def expovariate(self, lambd: float) -> float: pass
    def gammavariate(self, alpha: float, beta: float) -> float: pass
    def gauss(self, mu: float, sigma: float) -> float: pass
    def lognormvariate(self, mu: float, sigma: float) -> float: pass
    def normalvariate(self, mu: float, sigma: float) -> float: pass
    def vonmisesvariate(self, mu: float, kappa: float) -> float: pass
    def paretovariate(self, alpha: float) -> float: pass
    def weibullvariate(self, alpha: float, beta: float) -> float: pass

# SystemRandom is not implemented for all OS's; good on Windows & Linux
class SystemRandom:
    def __init__(self, randseed: object = None) -> None: pass
    def random(self) -> float: pass
    def getrandbits(self, k: int) -> int: pass
    def seed(self, arg: object) -> None: pass

# ----- random function stubs -----
def seed(a: Any = None, version: int = 2) -> None: pass
def getstate() -> object: pass
def setstate(state: object) -> None: pass
def getrandbits(k: int) -> int: pass
def randrange(start: int, stop: Union[None, int] = None, step: int = 1) -> int: pass
def randint(a: int, b: int) -> int: pass
def choice(seq: Sequence[_T]) -> _T: pass
def shuffle(x: List[Any], random: Union[Function[[], float], None] = None) -> None: pass
def sample(population: Union[Sequence[_T], AbstractSet[_T]], k: int) -> List[_T]: pass
def random() -> float: pass
def uniform(a: float, b: float) -> float: pass
def triangular(low: float = 0.0, high: float = 1.0,
               mode: float = None) -> float: pass
def betavariate(alpha: float, beta: float) -> float: pass
def expovariate(lambd: float) -> float: pass
def gammavariate(alpha: float, beta: float) -> float: pass
def gauss(mu: float, sigma: float) -> float: pass
def lognormvariate(mu: float, sigma: float) -> float: pass
def normalvariate(mu: float, sigma: float) -> float: pass
def vonmisesvariate(mu: float, kappa: float) -> float: pass
def paretovariate(alpha: float) -> float: pass
def weibullvariate(alpha: float, beta: float) -> float: pass
