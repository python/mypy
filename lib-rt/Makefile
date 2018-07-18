# Make file for C API unit tests.

.PHONY: clean test

all: test_capi

OS := $(shell uname)
PYTHONCONFIG ?= python3-config

CFLAGS += -I ../external/googletest -I ../external/googletest/include -std=c++11

CFLAGS += $(shell $(PYTHONCONFIG) --cflags)
CFLAGS += -fPIC

LDFLAGS += $(shell $(PYTHONCONFIG) --ldflags)

test_capi.o: test_capi.cc CPy.h Makefile ../mypyc/test/test_external.py
	c++ -c -o test_capi.o $(CFLAGS) test_capi.cc

test_capi: test_capi.o
	c++ -o test_capi test_capi.o ../external/googletest/make/gtest-all.o $(LDFLAGS)

test: test_capi
	./test_capi --gtest_print_time=0

clean:
	rm -f test_capi test_capi.o
