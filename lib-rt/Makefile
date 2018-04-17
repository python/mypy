# Make file for C API unit tests.

.PHONY: clean test

all: test_capi

OS := $(shell uname)
PYTHONCONFIG ?= python3-config

CFLAGS += -I ../external/googletest -I ../external/googletest/include -std=c++11

ifeq ($(OS),Darwin)
    CFLAGS += -I /Library/Frameworks/Python.framework/Versions/3.6/include/python3.6m
    CFLAGS += -mmacosx-version-min=10.10
else
    CFLAGS += $(shell $(PYTHONCONFIG) --cflags)
    CFLAGS += -fPIC
endif

ifeq ($(OS),Darwin)
    LDFLAGS += -lc -lc++
    LDFLAGS += -L/Library/Frameworks/Python.framework/Versions/3.6/lib/python3.6/config-3.6m-darwin
    LDFLAGS += -lpython3.6m -lcrt1.o -mmacosx-version-min=10.10
else
    LDFLAGS += $(shell $(PYTHONCONFIG) --ldflags)
endif

test_capi.o: test_capi.cc CPy.h
	c++ -c -o test_capi.o $(CFLAGS) test_capi.cc

test_capi: test_capi.o
	c++ -o test_capi test_capi.o ../external/googletest/make/gtest-all.o $(LDFLAGS)

test: test_capi
	./test_capi --gtest_print_time=0

clean:
	rm -f test_capi test_capi.o
