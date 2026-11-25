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
