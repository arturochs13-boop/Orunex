#ifndef _STRING_H_COMPAT
#define _STRING_H_COMPAT

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

void*   __cdecl memcpy(void* dst, const void* src, size_t count);
void*   __cdecl memset(void* dst, int val, size_t count);
void*   __cdecl memmove(void* dst, const void* src, size_t count);
int     __cdecl memcmp(const void* buf1, const void* buf2, size_t count);
size_t  __cdecl strlen(const char* str);
char*   __cdecl strcpy(char* dst, const char* src);
char*   __cdecl strncpy(char* dst, const char* src, size_t count);
int     __cdecl strcmp(const char* str1, const char* str2);
int     __cdecl strncmp(const char* str1, const char* str2, size_t count);
char*   __cdecl strchr(const char* str, int ch);
char*   __cdecl strstr(const char* str, const char* substr);
int     __cdecl _stricmp(const char* str1, const char* str2);
char*   __cdecl _strdup(const char* str);

#ifdef __cplusplus
}
#endif

#endif
