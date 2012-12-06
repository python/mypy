# Stubs for math
# Ron Murawski <ron@horizonchess.com>

# based on: http://docs.python.org/3.2/library/math.html

# ----- variables and constants -----
float e
float pi

# ----- functions -----
int ceil(int x): pass
int ceil(float x): pass
float copysign(int x, int y): pass
float copysign(float x, float y): pass
float fabs(int x): pass
float fabs(float x): pass
int factorial(int x): pass
int floor(int x): pass
int floor(float x): pass
float fmod(int x, int y): pass
float fmod(float x, float y): pass
tuple<float, int> frexp(int x): pass
tuple<float, int> frexp(float x): pass
float fsum(Iterable iterable): pass
bool isfinite(float x): pass
bool isinf(float x): pass
bool isnan(float x): pass
float ldexp(float x, int i): pass
tuple<float, float> modf(float x): pass
float trunc(float x): pass
float exp(int x): pass
float exp(float x): pass
float expm1(int x): pass
float expm1(float x): pass
float log(int x, float base=e): pass
float log(float x, float base=e): pass
float log(int x, int base): pass
float log(float x, int base): pass
float log1p(int x): pass
float log1p(float x): pass
float log10(int x): pass
float log10(float x): pass
float pow(int x, int y): pass
float pow(int x, float y): pass
float pow(float x, int y): pass
float pow(float x, float y): pass
float sqrt(int x): pass
float sqrt(float x): pass
float acos(int x): pass
float acos(float x): pass
float asin(int x): pass
float asin(float x): pass
float atan(int x): pass
float atan(float x): pass
float atan2(int y, int x): pass
float atan2(int y, float x): pass
float atan2(float y, int x): pass
float atan2(float y, float x): pass
float cos(int x): pass
float cos(float x): pass
float hypot(int x, int y): pass
float hypot(int x, float y): pass
float hypot(float x, int y): pass
float hypot(float x, float y): pass
float sin(int x): pass
float sin(float x): pass
float tan(int x): pass
float tan(float x): pass
float degrees(int x): pass
float degrees(float x): pass
float radians(int x): pass
float radians(float x): pass
float acosh(int x): pass
float acosh(float x): pass
float asinh(int x): pass
float asinh(float x): pass
float atanh(int x): pass
float atanh(float x): pass
float cosh(int x): pass
float cosh(float x): pass
float sinh(int x): pass
float sinh(float x): pass
float tanh(int x): pass
float tanh(float x): pass
float erf(object x): pass  # x is an arbitrary expression
float erfc(object x): pass  # x is an arbitrary expression
float gamma(object x): pass  # x is an arbitrary expression
float lgamma(object x): pass  # x is an arbitrary expression
