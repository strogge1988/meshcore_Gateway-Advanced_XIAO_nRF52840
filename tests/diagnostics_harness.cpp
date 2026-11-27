#include "GatewayDiagnostics.h"
#include <cassert>
#include <cstring>
#include <cstdio>
int main() {
  using namespace GatewayDiagnostics;
  char reply[160] = {};
  const unsigned char message[]={1,2,3,4,5};
  record(LORA_TX, 2, message, sizeof(message));
  record(UART_TX_CANDIDATE, 2, message, sizeof(message));
  record(UART_TX_OK, 2, message, sizeof(message));
  assert(handleCommand("get gateway.stats",reply));
  assert(strstr(reply,"ltx:1") && strstr(reply,"utx:1"));
  assert(handleCommand("get gateway.trace",reply));
  assert(strstr(reply,"UCAND") && strstr(reply,"UTX"));
  assert(handleCommand("get gateway.trace 1",reply));
  assert(strstr(reply,"empty"));
  assert(!handleCommand("set powersafe off",reply));
  assert(handleCommand("reset gateway.stats",reply));
  assert(handleCommand("get gateway.stats",reply));
  assert(strstr(reply,"ltx:0") && strstr(reply,"utx:0"));
  std::puts("Diagnostics API smoke test: OK");
}
