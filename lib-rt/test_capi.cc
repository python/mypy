// Test cases

#include <gtest/gtest.h>
#include <Python.h>
#include "CPy.h"

static bool is_initialized = false;
static PyObject *moduleDict;

static PyObject *int_from_str(const char *str) {
    return PyLong_FromString(str, 0, 10);
}

static std::string str_from_object(PyObject *x) {
    PyObject *str = PyObject_Str(x);
    const char *utf8 = PyUnicode_AsUTF8(str);
    return std::string(utf8);
}

static std::string str_from_int(CPyTagged x) {
    return str_from_object(CPyTagged_AsObject(x));
}

static bool is_py_equal(PyObject *x, PyObject *y) {
    int result = PyObject_RichCompareBool(x, y, Py_EQ);
    if (result < 0) {
        std::cout << "ERROR: Rich compare failed";
    }
    return result == 1;
}

static bool is_int_equal(CPyTagged x, CPyTagged y) {
    if (CPyTagged_CheckShort(x)) {
        return x == y;
    } else if (CPyTagged_CheckShort(y)) {
        return false;
    } else {
        return is_py_equal(CPyTagged_LongAsObject(x), CPyTagged_LongAsObject(y));
    }
}

static void fail(std::string message) {
    std::cerr << message << "\n";
    exit(1);
}

static PyObject *eval(std::string expr) {
    PyObject *dict = PyDict_New();
    auto result = PyRun_String(expr.c_str(), Py_eval_input, moduleDict, dict);
    Py_DECREF(dict);
    if (result == 0) {
        fail("Python exception");
    }
    return result;
}

static CPyTagged eval_int(std::string expr) {
    auto o = eval(expr);
    return CPyTagged_FromObject(o);
}

static PyObject *empty_list() {
    PyObject *list = PyList_New(0);
    EXPECT_TRUE(list);
    return list;
}

static void list_append(PyObject *list, std::string expr) {
    PyObject *obj = eval(expr);
    int result = PyList_Append(list, obj);
    EXPECT_TRUE(result == 0);
}

class CAPITest : public ::testing::Test {
protected:
    PyObject *max_short;
    PyObject *min_short;
    PyObject *min_pos_long;
    PyObject *max_neg_long;
    long long c_max_short;
    long long c_min_short;
    long long c_min_pos_long;
    long long c_max_neg_long;

    virtual void SetUp() {
        if (!is_initialized) {
            wchar_t *program = Py_DecodeLocale("test_capi", 0);
            Py_SetProgramName(program);
            Py_Initialize();
            PyObject *module = PyModule_New("test");
            if (module == 0) {
                fail("Could not create module 'test'");
            }
            moduleDict = PyModule_GetDict(module);
            if (module == 0) {
                fail("Could not fine module dictionary");
            }
            is_initialized = true;
        }
        // TODO: Call Py_Finalize() and PyMem_RawFree(program) at the end somehow.

        max_short = int_from_str("4611686018427387903"); // 2**62-1
        min_pos_long = int_from_str("4611686018427387904"); // 2**62
        min_short = int_from_str("-4611686018427387904"); // -2**62
        max_neg_long = int_from_str("-4611686018427387905"); // -(2**62+1)
        c_max_short = 4611686018427387903LL;
        c_min_pos_long = 4611686018427387904LL;
        c_min_short = -4611686018427387904LL;
        c_max_neg_long = -4611686018427387905LL;
    }

    virtual void TearDown() {
        Py_DECREF(max_short);
        Py_DECREF(min_pos_long);
        Py_DECREF(min_short);
        Py_DECREF(max_neg_long);
    }
};

TEST_F(CAPITest, test_cint_conversions) {
    EXPECT_EQ(CPyTagged_ShortFromInt(0), 0);
    EXPECT_EQ(CPyTagged_ShortFromInt(3), 6);
    EXPECT_EQ(CPyTagged_ShortFromInt(-5), -10);
    EXPECT_EQ(CPyTagged_ShortAsLongLong(0), 0);
    EXPECT_EQ(CPyTagged_ShortAsLongLong(6), 3);
    EXPECT_EQ(CPyTagged_ShortAsLongLong(-10), -5);
}

TEST_F(CAPITest, test_is_long_int) {
    EXPECT_TRUE(CPyTagged_CheckLong(1));
    EXPECT_TRUE(CPyTagged_CheckLong(15));
    EXPECT_FALSE(CPyTagged_CheckLong(0));
    EXPECT_FALSE(CPyTagged_CheckLong(6));
    EXPECT_FALSE(CPyTagged_CheckLong(-4));
}

TEST_F(CAPITest, test_is_short_int) {
    EXPECT_FALSE(CPyTagged_CheckShort(1));
    EXPECT_FALSE(CPyTagged_CheckShort(15));
    EXPECT_TRUE(CPyTagged_CheckShort(0));
    EXPECT_TRUE(CPyTagged_CheckShort(6));
    EXPECT_TRUE(CPyTagged_CheckShort(-4));
}

TEST_F(CAPITest, test_obj_to_short_int) {
    EXPECT_EQ(CPyTagged_FromObject(int_from_str("0")), CPyTagged_ShortFromInt(0));
    EXPECT_EQ(CPyTagged_FromObject(int_from_str("1234")), CPyTagged_ShortFromInt(1234));
    EXPECT_EQ(CPyTagged_FromObject(int_from_str("-1234")), CPyTagged_ShortFromInt(-1234));

    EXPECT_EQ(CPyTagged_FromObject(max_short), CPyTagged_ShortFromLongLong(c_max_short));
    EXPECT_EQ(CPyTagged_FromObject(min_short), CPyTagged_ShortFromLongLong(c_min_short));
}

TEST_F(CAPITest, test_obj_to_long_int) {
    // A value larger than 2**64
    PyObject *large = int_from_str("18464758493694263305");
    PyObject *small = int_from_str("-18464758493694263305");
    CPyTagged x;

    x = CPyTagged_FromObject(large);
    ASSERT_TRUE(CPyTagged_CheckLong(x));
    EXPECT_TRUE(is_py_equal(large, CPyTagged_LongAsObject(x)));

    x = CPyTagged_FromObject(small);
    ASSERT_TRUE(CPyTagged_CheckLong(x));
    EXPECT_TRUE(is_py_equal(small, CPyTagged_LongAsObject(x)));

    x = CPyTagged_FromObject(min_pos_long);
    ASSERT_TRUE(CPyTagged_CheckLong(x));
    EXPECT_TRUE(is_py_equal(min_pos_long, CPyTagged_LongAsObject(x)));

    x = CPyTagged_FromObject(max_neg_long);
    ASSERT_TRUE(CPyTagged_CheckLong(x));
    EXPECT_TRUE(is_py_equal(max_neg_long, CPyTagged_LongAsObject(x)));
}

TEST_F(CAPITest, test_short_int_to_obj) {
    EXPECT_TRUE(is_py_equal(CPyTagged_AsObject(CPyTagged_ShortFromInt(0)), int_from_str("0")));
    EXPECT_TRUE(is_py_equal(CPyTagged_AsObject(CPyTagged_ShortFromInt(1234)),
                            int_from_str("1234")));
    EXPECT_TRUE(is_py_equal(CPyTagged_AsObject(CPyTagged_ShortFromInt(-1234)),
                            int_from_str("-1234")));
    EXPECT_TRUE(is_py_equal(CPyTagged_AsObject(CPyTagged_ShortFromLongLong(c_max_short)),
                            max_short));
    EXPECT_TRUE(is_py_equal(CPyTagged_AsObject(CPyTagged_ShortFromLongLong(c_min_short)),
                            min_short));
}

TEST_F(CAPITest, test_long_int_to_obj) {
    // A value larger than 2**64
    PyObject *large = int_from_str("18464758493694263305");
    PyObject *small = int_from_str("-18464758493694263305");
    PyObject *x;

    x = CPyTagged_AsObject(CPyTagged_FromObject(large));
    EXPECT_TRUE(is_py_equal(large, x));
    x = CPyTagged_AsObject(CPyTagged_FromObject(small));
    EXPECT_TRUE(is_py_equal(small, x));
    x = CPyTagged_AsObject(CPyTagged_FromObject(min_pos_long));
    EXPECT_TRUE(is_py_equal(min_pos_long, x));
    x = CPyTagged_AsObject(CPyTagged_FromObject(max_neg_long));
    EXPECT_TRUE(is_py_equal(max_neg_long, x));
}

#define EXPECT_INT_EQUAL(x, y) \
    do { \
        if (!is_int_equal(x, y)) \
            std::cout << "Failure: " << str_from_int(x) << " != " << str_from_int(y) << \
                "\n"; \
        EXPECT_TRUE(is_int_equal(x, y));  \
    } while (false)

#define ASSERT_ADD(x, y, result) \
    EXPECT_TRUE(is_int_equal(CPyTagged_Add(eval_int(x), eval_int(y)), eval_int(result)))

TEST_F(CAPITest, test_add_short_int) {
    ASSERT_ADD("13", "8", "21");
    ASSERT_ADD("-13", "8", "-5");
    ASSERT_ADD("13", "-7", "6");
    ASSERT_ADD("13", "-14", "-1");
    ASSERT_ADD("-3", "-5", "-8");
}

TEST_F(CAPITest, test_add_long_ints) {
    ASSERT_ADD("2**64", "2**65", "2**64 + 2**65");
    ASSERT_ADD("2**64", "-2**65", "2**64 - 2**65");
}

TEST_F(CAPITest, test_add_long_and_short) {
    ASSERT_ADD("1", "2**65", "1 + 2**65");
    ASSERT_ADD("2**65", "1", "1 + 2**65");
}

TEST_F(CAPITest, test_add_short_overflow) {
    // Overfloat
    ASSERT_ADD("2**62 - 1", "1", "2**62");
    ASSERT_ADD("-2**62", "-1", "-2**62 - 1");
}

TEST_F(CAPITest, test_add_short_edge_cases) {
    // Close but not quite overflow
    ASSERT_ADD("2**62 - 2", "1", "2**62 - 1");
    ASSERT_ADD("-2**62 + 1", "-1", "-2**62");
    // Max magnitudes
    ASSERT_ADD("2**62 - 1", "2**62 - 1", "2**63 - 2");
    ASSERT_ADD("2**62 - 1", "-2**62", "-1");
}

#define ASSERT_SUBTRACT(x, y, result) \
    EXPECT_TRUE(is_int_equal(CPyTagged_Subtract(eval_int(x), eval_int(y)), eval_int(result)))

TEST_F(CAPITest, test_subtract_short_int) {
    ASSERT_SUBTRACT("13", "8", "5");
    ASSERT_SUBTRACT("8", "13", "-5");
    ASSERT_SUBTRACT("-13", "8", "-21");
    ASSERT_SUBTRACT("13", "-7", "20");
    ASSERT_SUBTRACT("-3", "-5", "2");
}

TEST_F(CAPITest, test_subtract_long_int) {
    ASSERT_SUBTRACT("2**65", "2**64", "2**65 - 2**64");
    ASSERT_SUBTRACT("2**65", "-2**64", "2**65 + 2**64");
}

TEST_F(CAPITest, test_subtract_long_and_short) {
    ASSERT_SUBTRACT("1", "2**65", "1 - 2**65");
    ASSERT_SUBTRACT("2**65", "1", "2**65 - 1");
}

TEST_F(CAPITest, test_subtract_short_overflow) {
    ASSERT_SUBTRACT("2**62-1", "-1", "2**62");
    ASSERT_SUBTRACT("-2**62", "1", "-2**62 - 1");
    ASSERT_SUBTRACT("0", "-2**62", "2**62");
    ASSERT_SUBTRACT("1", "-2**62 + 1", "2**62");
    ASSERT_SUBTRACT("-2", "2**62 - 1", "-2**62 - 1");
}

TEST_F(CAPITest, test_subtract_short_edge_cases) {
    // Close but not quite overflow
    ASSERT_SUBTRACT("2**62 - 2", "-1", "2**62 - 1");
    ASSERT_SUBTRACT("-2**62 + 1", "1", "-2**62");
    // Max magnitudes
    ASSERT_SUBTRACT("2**62 - 1", "-2**62", "2**63 - 1");
    ASSERT_SUBTRACT("-2**62", "2**62 - 1", "-2**63 + 1");
}

#define ASSERT_MULTIPLY(x, y, result) \
    EXPECT_TRUE(is_int_equal(CPyTagged_Multiply(eval_int(x), eval_int(y)), eval_int(result)))

TEST_F(CAPITest, test_multiply_int) {
    ASSERT_MULTIPLY("0", "0", "0");
    ASSERT_MULTIPLY("3", "5", "15");
    ASSERT_MULTIPLY("2**40", "2**40", "2**80");
    ASSERT_MULTIPLY("2**30-1", "2**30-1", "(2**30-1)**2");
    ASSERT_MULTIPLY("2**30", "2**30-1", "2**30 * (2**30-1)");
    ASSERT_MULTIPLY("2**30-1", "2**30", "2**30 * (2**30-1)");
    ASSERT_MULTIPLY("3", "-5", "-15");
    ASSERT_MULTIPLY("-3", "5", "-15");
    ASSERT_MULTIPLY("-3", "-5", "15");
}

#define ASSERT_FLOOR_DIV(x, y, result) \
    EXPECT_INT_EQUAL(CPyTagged_FloorDivide(eval_int(x), eval_int(y)), eval_int(result))

TEST_F(CAPITest, test_floor_divide_short_int) {
    ASSERT_FLOOR_DIV("18", "6", "3");
    ASSERT_FLOOR_DIV("17", "6", "2");
    ASSERT_FLOOR_DIV("12", "6", "2");
    ASSERT_FLOOR_DIV("15", "5", "3");
    ASSERT_FLOOR_DIV("14", "5", "2");
    ASSERT_FLOOR_DIV("11", "5", "2");
    ASSERT_FLOOR_DIV("-18", "6", "-3");
    ASSERT_FLOOR_DIV("-13", "6", "-3");
    ASSERT_FLOOR_DIV("-12", "6", "-2");
    ASSERT_FLOOR_DIV("18", "-6", "-3");
    ASSERT_FLOOR_DIV("13", "-6", "-3");
    ASSERT_FLOOR_DIV("12", "-6", "-2");
    ASSERT_FLOOR_DIV("-3", "-3", "1");
    ASSERT_FLOOR_DIV("-5", "-3", "1");
    ASSERT_FLOOR_DIV("-6", "-3", "2");

    ASSERT_FLOOR_DIV("2**60", "3", "2**60 // 3");
    ASSERT_FLOOR_DIV("-2**62", "-1", "2**62");
    ASSERT_FLOOR_DIV("-2**62", "1", "-2**62");
    ASSERT_FLOOR_DIV("2**62 - 1", "1", "2**62 - 1");
    ASSERT_FLOOR_DIV("2**62 - 1", "-1", "-2**62 + 1");
}

TEST_F(CAPITest, test_floor_divide_long_int) {
    ASSERT_FLOOR_DIV("2**100", "3", "2**100 // 3");
    ASSERT_FLOOR_DIV("3", "2**100", "0");
    ASSERT_FLOOR_DIV("2**100", "2**70 / 3", "2**100 // (2**70 / 3)");
}

#define ASSERT_REMAINDER(x, y, result) \
    EXPECT_INT_EQUAL(CPyTagged_Remainder(eval_int(x), eval_int(y)), eval_int(result))

TEST_F(CAPITest, test_remainder_short_int) {
    ASSERT_REMAINDER("18", "6", "0");
    ASSERT_REMAINDER("17", "6", "5");
    ASSERT_REMAINDER("13", "6", "1");
    ASSERT_REMAINDER("12", "6", "0");
    ASSERT_REMAINDER("15", "5", "0");
    ASSERT_REMAINDER("14", "5", "4");
    ASSERT_REMAINDER("11", "5", "1");
    ASSERT_REMAINDER("-18", "6", "0");
    ASSERT_REMAINDER("-13", "6", "5");
    ASSERT_REMAINDER("-12", "6", "0");
    ASSERT_REMAINDER("18", "-6", "0");
    ASSERT_REMAINDER("13", "-6", "-5");
    ASSERT_REMAINDER("12", "-6", "0");
    ASSERT_REMAINDER("-3", "-3", "0");
    ASSERT_REMAINDER("-5", "-3", "-2");
    ASSERT_REMAINDER("-6", "-3", "0");

    ASSERT_REMAINDER("-1", "2**62 - 1", "2**62 - 2");
    ASSERT_REMAINDER("1", "-2**62", "-2**62 + 1");
}

TEST_F(CAPITest, test_remainder_long_int) {
    ASSERT_REMAINDER("2**100", "3", "2**100 % 3");
    ASSERT_REMAINDER("3", "2**100", "3");
    ASSERT_REMAINDER("2**100", "2**70 / 3", "2**100 % (2**70 / 3)");
}

#define INT_EQ(x, y) \
    CPyTagged_IsEq(eval_int(x), eval_int(y))

TEST_F(CAPITest, test_int_equality) {
    EXPECT_TRUE(INT_EQ("0", "0"));
    EXPECT_TRUE(INT_EQ("5", "5"));
    EXPECT_TRUE(INT_EQ("-7", "-7"));
    EXPECT_TRUE(INT_EQ("2**65 + 0x1234", "2**65 + 0x1234"));
    EXPECT_TRUE(INT_EQ("-2**65 + 0x1234", "-2**65 + 0x1234"));
    EXPECT_FALSE(INT_EQ("0", "1"));
    EXPECT_FALSE(INT_EQ("5", "4"));
    EXPECT_FALSE(INT_EQ("-7", "7"));
    EXPECT_FALSE(INT_EQ("-7", "-6"));
    EXPECT_FALSE(INT_EQ("-7", "-5"));
    EXPECT_FALSE(INT_EQ("2**65 + 0x1234", "2**65 + 0x1233"));
    EXPECT_FALSE(INT_EQ("2**65 + 0x1234", "2**66 + 0x1234"));
    EXPECT_FALSE(INT_EQ("2**65 + 0x1234", "-2**65 - 0x1234"));
    EXPECT_FALSE(INT_EQ("-2**65 + 0x1234", "-2**65 + 0x1233"));
}

#define INT_NE(x, y) \
    CPyTagged_IsNe(eval_int(x), eval_int(y))

TEST_F(CAPITest, test_int_non_equality) {
    EXPECT_FALSE(INT_NE("0", "0"));
    EXPECT_FALSE(INT_NE("5", "5"));
    EXPECT_FALSE(INT_NE("-7", "-7"));
    EXPECT_FALSE(INT_NE("2**65 + 0x1234", "2**65 + 0x1234"));
    EXPECT_FALSE(INT_NE("-2**65 + 0x1234", "-2**65 + 0x1234"));
    EXPECT_TRUE(INT_NE("0", "1"));
    EXPECT_TRUE(INT_NE("5", "4"));
    EXPECT_TRUE(INT_NE("-7", "7"));
    EXPECT_TRUE(INT_NE("-7", "-6"));
    EXPECT_TRUE(INT_NE("-7", "-5"));
    EXPECT_TRUE(INT_NE("2**65 + 0x1234", "2**65 + 0x1233"));
    EXPECT_TRUE(INT_NE("2**65 + 0x1234", "2**66 + 0x1234"));
    EXPECT_TRUE(INT_NE("2**65 + 0x1234", "-2**65 - 0x1234"));
    EXPECT_TRUE(INT_NE("-2**65 + 0x1234", "-2**65 + 0x1233"));
}

#define INT_LT(x, y) \
    CPyTagged_IsLt(eval_int(x), eval_int(y))

TEST_F(CAPITest, test_int_less_than) {
    EXPECT_TRUE(INT_LT("0", "5"));
    EXPECT_TRUE(INT_LT("4", "5"));
    EXPECT_TRUE(INT_LT("-3", "1"));
    EXPECT_TRUE(INT_LT("-3", "0"));
    EXPECT_TRUE(INT_LT("-3", "-2"));

    EXPECT_FALSE(INT_LT("5", "0"));
    EXPECT_FALSE(INT_LT("5", "4"));
    EXPECT_FALSE(INT_LT("1", "-3"));
    EXPECT_FALSE(INT_LT("0", "-3"));
    EXPECT_FALSE(INT_LT("-2", "-3"));
    EXPECT_FALSE(INT_LT("-3", "-3"));
    EXPECT_FALSE(INT_LT("3", "3"));

    EXPECT_TRUE(INT_LT("5", "2**65"));
    EXPECT_TRUE(INT_LT("-2**65", "-5"));
    EXPECT_TRUE(INT_LT("-2**66", "2**65"));
    EXPECT_TRUE(INT_LT("2**65", "2**66"));
    EXPECT_TRUE(INT_LT("-2**66", "-2**65"));

    EXPECT_FALSE(INT_LT("2**65", "5"));
    EXPECT_FALSE(INT_LT("-5", "-2**65"));
    EXPECT_FALSE(INT_LT("2**65", "-2**66"));
    EXPECT_FALSE(INT_LT("2**66", "2**65"));
    EXPECT_FALSE(INT_LT("-2**65", "-2**66"));
    EXPECT_FALSE(INT_LT("-2**65", "-2**65"));
    EXPECT_FALSE(INT_LT("2**65", "2**65"));
}

#define INT_GE(x, y) \
    CPyTagged_IsGe(eval_int(x), eval_int(y))

TEST_F(CAPITest, test_int_greater_than_or_equal) {
    EXPECT_TRUE(INT_GE("3", "2"));
    EXPECT_TRUE(INT_GE("3", "3"));
    EXPECT_FALSE(INT_GE("3", "4"));
    EXPECT_TRUE(INT_GE("3", "-4"));
    EXPECT_TRUE(INT_GE("-3", "-4"));
    EXPECT_TRUE(INT_GE("-3", "-3"));
    EXPECT_FALSE(INT_GE("-3", "-2"));
    EXPECT_FALSE(INT_GE("-3", "2"));

    EXPECT_TRUE(INT_GE("2**65", "2**65"));
    EXPECT_TRUE(INT_GE("2**65", "2**65 - 1"));
    EXPECT_FALSE(INT_GE("2**65", "2**65 + 1"));
    EXPECT_TRUE(INT_GE("2**65", "2**60"));
}

#define INT_GT(x, y) \
    CPyTagged_IsGt(eval_int(x), eval_int(y))

TEST_F(CAPITest, test_int_greater_than) {
    EXPECT_TRUE(INT_GT("5", "0"));
    EXPECT_TRUE(INT_GT("5", "4"));
    EXPECT_FALSE(INT_GT("5", "5"));
    EXPECT_FALSE(INT_GT("5", "6"));

    EXPECT_TRUE(INT_GT("1", "-3"));
    EXPECT_FALSE(INT_GT("-3", "1"));

    EXPECT_TRUE(INT_GT("0", "-3"));
    EXPECT_TRUE(INT_GT("-2", "-3"));
    EXPECT_FALSE(INT_GT("-2", "-2"));
    EXPECT_FALSE(INT_GT("-2", "-1"));

    EXPECT_TRUE(INT_GT("2**65", "5"));
    EXPECT_TRUE(INT_GT("2**65", "2**65 - 1"));
    EXPECT_FALSE(INT_GT("2**65", "2**65"));
    EXPECT_FALSE(INT_GT("2**65", "2**65 + 1"));

    EXPECT_FALSE(INT_GT("-2**65", "1"));
    EXPECT_TRUE(INT_GT("-2**65", "-2**65 - 1"));
    EXPECT_FALSE(INT_GT("-2**65", "-2**65"));
    EXPECT_FALSE(INT_GT("-2**65", "-2**65 + 1"));
}

#define INT_LE(x, y) \
    CPyTagged_IsLe(eval_int(x), eval_int(y))

TEST_F(CAPITest, test_int_less_than_or_equal) {
    EXPECT_TRUE(INT_LE("0", "5"));
    EXPECT_TRUE(INT_LE("5", "6"));
    EXPECT_TRUE(INT_LE("5", "5"));
    EXPECT_FALSE(INT_LE("5", "4"));

    EXPECT_FALSE(INT_LE("1", "-3"));
    EXPECT_TRUE(INT_LE("-3", "1"));

    EXPECT_TRUE(INT_LT("-3", "0"));
    EXPECT_TRUE(INT_LE("-2", "-1"));
    EXPECT_TRUE(INT_LE("-2", "-2"));
    EXPECT_FALSE(INT_LT("-2", "-3"));

    EXPECT_TRUE(INT_LE("5", "2**65"));
    EXPECT_FALSE(INT_LE("2**65", "5"));
    EXPECT_TRUE(INT_LE("2**65", "2**65 + 1"));
    EXPECT_TRUE(INT_LE("2**65", "2**65"));
    EXPECT_FALSE(INT_LE("2**65", "2**65 - 1"));

    EXPECT_TRUE(INT_LE("-2**65", "1"));
    EXPECT_FALSE(INT_LE("1", "-2**65"));
    EXPECT_TRUE(INT_LE("-2**65", "-2**65 + 1"));
    EXPECT_TRUE(INT_LE("-2**65", "-2**65"));
    EXPECT_FALSE(INT_LE("-2**65", "-2**65 - 1"));
}

#define list_get_eq(list, index, value) \
    is_py_equal(CPyList_GetItem(list, eval_int(index)), eval(value))

TEST_F(CAPITest, test_list_get) {
    auto l = empty_list();
    list_append(l, "3");
    list_append(l, "5");
    list_append(l, "7");
    EXPECT_TRUE(list_get_eq(l, "0", "3"));
    EXPECT_TRUE(list_get_eq(l, "1", "5"));
    EXPECT_TRUE(list_get_eq(l, "2", "7"));
    EXPECT_TRUE(list_get_eq(l, "-1", "7"));
    EXPECT_TRUE(list_get_eq(l, "-2", "5"));
    EXPECT_TRUE(list_get_eq(l, "-3", "3"));
}

TEST_F(CAPITest, test_tagged_as_long_long) {
    auto s = eval_int("3");
    auto neg = eval_int("-1");
    auto l = eval_int("2**128");
    EXPECT_TRUE(CPyTagged_AsLongLong(s) == 3);
    EXPECT_FALSE(PyErr_Occurred());
    EXPECT_TRUE(CPyTagged_AsLongLong(neg) == -1);
    EXPECT_FALSE(PyErr_Occurred());
    EXPECT_TRUE(CPyTagged_AsLongLong(l) == -1);
    EXPECT_TRUE(PyErr_Occurred());
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
