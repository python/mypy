# Stubs for random
# Ron Murawski <ron@horizonchess.com>
# Tweaks by Jukka Lehtosalo

# based on http://docs.python.org/3.2/library/random.html

# ----- random classes -----

# SystemRandom is not implemented for all OS's; good on Windows & Linux
class SystemRandom:
    void __init__(self, object randseed=None): pass
    int random(self): pass
    int getrandbits(self, int k): pass
    void seed(self, object arg): pass  # ??? seed func does nothing by design

# ----- random function stubs -----
void seed(any a=None, int version=2):
    # a must be int, str, bytes, or bytearray if version == 2
    pass
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
