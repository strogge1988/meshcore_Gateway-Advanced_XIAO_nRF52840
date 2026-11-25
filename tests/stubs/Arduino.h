#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
unsigned long millis();
struct FakeSerial { void println(const char*); };
extern FakeSerial Serial;
#define FILE_O_WRITE 1

// Real Arduino core defines these macros; guard against enum-name collisions.
#define LOW (0x0)
#define HIGH (0x1)
