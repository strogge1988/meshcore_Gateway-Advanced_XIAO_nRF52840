#pragma once
#include <stddef.h>
#include <stdint.h>

// Diagnostics never send, block, or rewrite mesh packets.
// A stable short fingerprint identifies the same *payload* on both gateways.
namespace GatewayDiagnostics {
  enum Event : uint8_t {
    LORA_RX, LORA_TX, LORA_TX_FAIL,
    UART_TX_CANDIDATE, UART_TX_OK, UART_TX_DUP, UART_TX_TOO_LARGE,
    UART_TX_SHORT_WRITE, UART_RX_FRAME, UART_RX_QUEUED, UART_RX_DUP,
    UART_RX_BAD_LENGTH, UART_RX_BAD_CRC, UART_RX_BAD_PARSE,
    UART_RX_NO_MEMORY, UART_RX_BAD_MAGIC,
    EVENT_COUNT
  };
  void record(Event event, uint8_t payload_type = 0, const uint8_t* payload = nullptr, size_t length = 0);
  bool handleCommand(const char* command, char* reply);
  void clear();
}
