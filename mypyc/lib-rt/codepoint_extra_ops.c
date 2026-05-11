#include "codepoint_extra_ops.h"

// Out-of-line bodies for codepoint helpers that are too large to inline.
// The classification helpers and the ASCII fast paths for case conversion
// stay inline in codepoint_extra_ops.h; this file holds the slow paths
// that round-trip through PyUnicode_FromOrdinal and CPython's Unicode
// machinery. Currently empty; populated as later commits add
// isidentifier, toupper, and tolower.
