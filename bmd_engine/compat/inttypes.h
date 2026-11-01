#ifndef _INTTYPES_H_COMPAT
#define _INTTYPES_H_COMPAT

#include <stdint.h>

#ifndef PRId64
#define PRId64 "lld"
#endif

#ifndef PRIu64
#define PRIu64 "llu"
#endif

#ifndef PRIx64
#define PRIx64 "llx"
#endif

#endif
