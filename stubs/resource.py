# Stubs for resource

# NOTE: These are incomplete!

int RLIMIT_CORE

tuple<int, int> getrlimit(int resource): pass
void setrlimit(int resource, tuple<int, int> limits): pass
