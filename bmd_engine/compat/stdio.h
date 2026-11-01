#ifndef _STDIO_H_COMPAT
#define _STDIO_H_COMPAT

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef _FILE_DEFINED
typedef struct _iobuf {
    void* _Placeholder;
} FILE;
#define _FILE_DEFINED
#endif

#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2

#define EOF (-1)

extern FILE* __cdecl __acrt_iob_func(unsigned int i);
#define stdin  (__acrt_iob_func(0))
#define stdout (__acrt_iob_func(1))
#define stderr (__acrt_iob_func(2))

FILE*   __cdecl fopen(const char* filename, const char* mode);
int     __cdecl fclose(FILE* stream);
size_t  __cdecl fread(void* buffer, size_t size, size_t count, FILE* stream);
size_t  __cdecl fwrite(const void* buffer, size_t size, size_t count, FILE* stream);
int     __cdecl fseek(FILE* stream, long offset, int origin);
long    __cdecl ftell(FILE* stream);
int     __cdecl printf(const char* format, ...);
int     __cdecl fprintf(FILE* stream, const char* format, ...);
int     __cdecl sprintf_s(char* buffer, size_t count, const char* format, ...);
int     __cdecl fflush(FILE* stream);
char*   __cdecl fgets(char* str, int num, FILE* stream);

#ifndef snprintf
#define snprintf sprintf_s
#endif

#ifdef __cplusplus
}
#endif

#endif
