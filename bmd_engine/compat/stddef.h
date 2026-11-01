#ifndef _STDDEF_H_COMPAT
#define _STDDEF_H_COMPAT

#ifndef _SIZE_T_DEFINED
typedef unsigned __int64 size_t;
#define _SIZE_T_DEFINED
#endif

#ifndef _PTRDIFF_T_DEFINED
typedef __int64 ptrdiff_t;
#define _PTRDIFF_T_DEFINED
#endif

#ifndef NULL
#ifdef __cplusplus
#define NULL 0
#else
#define NULL ((void *)0)
#endif
#endif

#ifndef offsetof
#define offsetof(s,m) ((size_t)&(((s*)0)->m))
#endif

#endif
