#pragma once
#include <stdint.h>
struct FakeNrfPower { uint32_t RESETREAS; };
extern FakeNrfPower* NRF_POWER;
#define POWER_RESETREAS_SREQ_Msk (1u << 2)
#define POWER_RESETREAS_DOG_Msk (1u << 1)
#define POWER_RESETREAS_RESETPIN_Msk (1u << 0)
