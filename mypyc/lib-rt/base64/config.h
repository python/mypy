#ifndef BASE64_CONFIG_H
#define BASE64_CONFIG_H

#if !defined(__APPLE__) && ((defined(__x86_64__) && defined(__LP64__)) || defined(_M_X64))
  #define HAVE_SSSE3 1
  #define HAVE_SSE41 1
  #define HAVE_SSE42 1
  #define HAVE_AVX 1
  #define HAVE_AVX2 1
  #define HAVE_AVX512 0
#endif

#define BASE64_WITH_NEON32 0
#define HAVE_NEON32 BASE64_WITH_NEON32

#if defined(__APPLE__) && defined(__aarch64__)
#define BASE64_WITH_NEON64 1
#else
#define BASE64_WITH_NEON64 0
#endif

#define HAVE_NEON64 BASE64_WITH_NEON64

#endif // BASE64_CONFIG_H
