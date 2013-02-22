# Stubs for random
# Ron Murawski <ron@horizonchess.com>
# Updated by Jukka Lehtosalo

# based on http://docs.python.org/3.2/library/random.html

# ----- random classes -----

import _random

class Random(_random.Random):
    void __init__(self, any x=None): pass
    void seed(self, any a=None, int version=2): pass
    tuple getstate(self): pass
    void setstate(self, tuple state): pass
    int getrandbits(self, int k): pass
    int randrange(self, int stop): pass
    int randrange(self, int start, int stop, int step=1): pass
    int randint(self, int a, int b): pass
    t choice<t>(self, Sequence<t> seq): pass
    void shuffle(self, any[] x): pass
    void shuffle(self, any[] x, func<float()> random): pass
    t[] sample<t>(self, Sequence<t> population, int k): pass
    t[] sample<t>(self, Set<t> population, int k): pass
    float random(self): pass
    float uniform(self, float a, float b): pass
    float triangular(self, float low=0.0, float high=1.0,
                     float mode=None): pass
    float betavariate(self, float alpha, float beta): pass
    float expovariate(self, float lambd): pass
    float gammavariate(self, float alpha, float beta): pass
    float gauss(self, float mu, float sigma): pass
    float lognormvariate(self, float mu, float sigma): pass
    float normalvariate(self, float mu, float sigma): pass
    float vonmisesvariate(self, float mu, float kappa): pass
    float paretovariate(self, float alpha): pass
    float weibullvariate(self, float alpha, float beta): pass

# SystemRandom is not implemented for all OS's; good on Windows & Linux
class SystemRandom:
    void __init__(self, object randseed=None): pass
    float random(self): pass
    int getrandbits(self, int k): pass
    void seed(self, object arg): pass  # ??? seed func does nothing by design

# ----- random function stubs -----
void seed(any a=None, int version=2): pass
object getstate(): pass
void setstate(object state): pass
int getrandbits(int k): pass
int randrange(int stop): pass
int randrange(int start, int stop, int step=1): pass
int randint(int a, int b): pass
t choice<t>(Sequence<t> seq): pass
void shuffle(any[] x): pass
void shuffle(any[] x, func<float()> random): pass
t[] sample<t>(Sequence<t> population, int k): pass
t[] sample<t>(Set<t> population, int k): pass
float random(): pass
float uniform(float a, float b): pass
float triangular(float low=0.0, float high=1.0, float mode=None): pass
float betavariate(float alpha, float beta): pass
float expovariate(float lambd): pass
float gammavariate(float alpha, float beta): pass
float gauss(float mu, float sigma): pass
float lognormvariate(float mu, float sigma): pass
float normalvariate(float mu, float sigma): pass
float vonmisesvariate(float mu, float kappa): pass
float paretovariate(float alpha): pass
float weibullvariate(float alpha, float beta): pass
