#ifndef _CTYPE_H_COMPAT
#define _CTYPE_H_COMPAT

#ifdef __cplusplus
extern "C" {
#endif

int __cdecl isspace(int c);
int __cdecl isdigit(int c);
int __cdecl isalpha(int c);
int __cdecl isalnum(int c);
int __cdecl tolower(int c);
int __cdecl toupper(int c);

#ifdef __cplusplus
}
#endif

#endif
