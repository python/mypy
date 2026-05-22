// All codepoint helper bodies live in codepoint_extra_ops.h as static
// inline. This translation unit exists so the header is pulled into
// mypyc-compiled extensions via SourceDep("codepoint_extra_ops.c") in
// mypyc/ir/deps.py (which, in include_runtime_files mode, emits
// `#include <codepoint_extra_ops.c>` into the generated __native.c).
#include "codepoint_extra_ops.h"
