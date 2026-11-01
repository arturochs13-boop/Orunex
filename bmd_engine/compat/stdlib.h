#ifndef _STDLIB_H_COMPAT
#define _STDLIB_H_COMPAT

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

void* __cdecl malloc(size_t size);
void* __cdecl calloc(size_t num, size_t size);
void* __cdecl realloc(void* ptr, size_t new_size);
void  __cdecl free(void* ptr);
void  __cdecl exit(int status);
int   __cdecl rand(void);
void  __cdecl srand(unsigned int seed);
int   __cdecl atoi(const char* str);
__int64 __cdecl _atoi64(const char* str);
unsigned __int64 __cdecl strtoull(const char* str, char** endptr, int base);
int   __cdecl system(const char* command);
int   __cdecl abs(int n);

#ifdef __cplusplus
}
#endif

#endif
