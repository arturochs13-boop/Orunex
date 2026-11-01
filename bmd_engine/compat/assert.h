#ifndef _ASSERT_H_COMPAT
#define _ASSERT_H_COMPAT

#include <stdio.h>
#include <stdlib.h>

#define assert(expr) \
    do { \
        if (!(expr)) { \
            fprintf(stderr, "Assertion failed: %s, file %s, line %d\n", #expr, __FILE__, __LINE__); \
            exit(1); \
        } \
    } while (0)

#endif
