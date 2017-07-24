# Make file for C API unit tests.

.PHONY: clean test

CFLAGS = -I ../googletest -I ../googletest/include
CFLAGS += -I /Library/Frameworks/Python.framework/Versions/3.6/include/python3.6m
CFLAGS += -std=c++11
CFLAGS += -mmacosx-version-min=10.10
LDFLAGS = -lc -lc++
LDFLAGS += -L/Library/Frameworks/Python.framework/Versions/3.6/lib/python3.6/config-3.6m-darwin
LDFLAGS += -lpython3.6m -lcrt1.o -mmacosx-version-min=10.10

test_capi.o: test_capi.cc CPy.h
	c++ -c -o test_capi.o $(CFLAGS) test_capi.cc # -c

test_capi: test_capi.o
	c++ $(LDFLAGS) -o test_capi test_capi.o ../googletest/make/gtest-all.o

test: test_capi
	./test_capi --gtest_print_time=0

clean:
	rm -f test_capi test_capi.o
