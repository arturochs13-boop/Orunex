#ifndef _TIME_H_COMPAT
#define _TIME_H_COMPAT

#ifdef __cplusplus
extern "C" {
#endif

typedef __int64 time_t;
time_t __cdecl time(time_t* timer);

#ifdef __cplusplus
}
#endif

#endif
