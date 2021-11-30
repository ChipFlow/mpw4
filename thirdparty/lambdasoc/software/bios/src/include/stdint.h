#ifndef __STDINT_H
#define __STDINT_H

typedef int intptr_t;
typedef unsigned int uintptr_t;

typedef unsigned long long uint64_t;
typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef unsigned char uint8_t;

typedef long long int64_t;
typedef int int32_t;
typedef short int16_t;
typedef signed char int8_t;

typedef signed char int_least8_t;
typedef unsigned char uint_least8_t;
typedef signed short int_least16_t;
typedef unsigned short uint_least16_t;
typedef signed int int_least32_t;
typedef unsigned int uint_least32_t;
typedef signed long long int_least64_t;
typedef unsigned long long uint_least64_t;

#define __int_c_join(a, b) a ## b
#define __int_c(v, suffix) __int_c_join(v, suffix)
#define __uint_c(v, suffix) __int_c_join(v##U, suffix)

#define INT64_C(v) __int_c(v, LL)
#define UINT64_C(v) __uint_c(v, LL)
#define INT32_C(v) v
#define UINT32_C(v) v##U

#endif /* __STDINT_H */
