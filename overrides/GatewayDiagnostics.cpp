#include "GatewayDiagnostics.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace GatewayDiagnostics {
  // RAM-only counters: no flash wear, reset on every boot.
  static uint32_t counters[EVENT_COUNT] = {};
  static constexpr uint8_t HISTORY = 36;
  struct Trace { uint32_t fingerprint; Event event; };
  static Trace history[HISTORY] = {};
  static uint8_t head = 0, used = 0;

  static uint32_t fingerprint(uint8_t kind, const uint8_t* p, size_t len) {
    // FNV-1a, diagnostics only; not a MeshCore protocol hash.
    uint32_t h = 2166136261UL;
    h = (h ^ kind) * 16777619UL;
    for (size_t i = 0; p && i < len; ++i) h = (h ^ p[i]) * 16777619UL;
    return h;
  }
  static const char* eventName(Event e) {
    switch (e) {
      case LORA_RX: return "LRX";
      case LORA_TX: return "LTX";
      case LORA_TX_FAIL: return "LFAIL";
      case UART_TX_CANDIDATE: return "UCAND";
      case UART_TX_OK: return "UTX";
      case UART_TX_DUP: return "UDUP";
      case UART_TX_TOO_LARGE: return "UBIG";
      case UART_TX_SHORT_WRITE: return "USHORT";
      case UART_RX_FRAME: return "URX";
      case UART_RX_QUEUED: return "QUEUE";
      case UART_RX_DUP: return "RDUP";
      case UART_RX_BAD_LENGTH: return "RLEN";
      case UART_RX_BAD_CRC: return "RCRC";
      case UART_RX_BAD_PARSE: return "RPARSE";
      case UART_RX_NO_MEMORY: return "RMEM";
      case UART_RX_BAD_MAGIC: return "RMAGIC";
      default: return "?";
    }
  }
  void record(Event event, uint8_t type, const uint8_t* data, size_t len) {
    if (event >= EVENT_COUNT) return;
    if (counters[event] != UINT32_MAX) ++counters[event];
    // Avoid history noise from non-packet events that have no stable identity.
    if (!data || len == 0) return;
    history[head] = {fingerprint(type, data, len), event};
    head = (head + 1U) % HISTORY;
    if (used < HISTORY) ++used;
  }
  void clear() {
    memset(counters, 0, sizeof(counters));
    head = used = 0;
    memset(history, 0, sizeof(history));
  }
  bool handleCommand(const char* command, char* reply) {
    // CLI response buffer is owned by MeshCore; stay below 120 bytes.
    if (!strcmp(command, "get gateway.stats")) {
      snprintf(reply, 120, "> lrx:%lu ltx:%lu lfail:%lu cand:%lu utx:%lu urx:%lu queued:%lu",
        (unsigned long)counters[LORA_RX], (unsigned long)counters[LORA_TX],
        (unsigned long)counters[LORA_TX_FAIL], (unsigned long)counters[UART_TX_CANDIDATE],
        (unsigned long)counters[UART_TX_OK], (unsigned long)counters[UART_RX_FRAME],
        (unsigned long)counters[UART_RX_QUEUED]);
      return true;
    }
    if (!strcmp(command, "get gateway.drops")) {
      snprintf(reply, 120, "> td:%lu big:%lu short:%lu rd:%lu len:%lu crc:%lu",
        (unsigned long)counters[UART_TX_DUP], (unsigned long)counters[UART_TX_TOO_LARGE],
        (unsigned long)counters[UART_TX_SHORT_WRITE], (unsigned long)counters[UART_RX_DUP],
        (unsigned long)counters[UART_RX_BAD_LENGTH], (unsigned long)counters[UART_RX_BAD_CRC]);
      return true;
    }
    if (!strcmp(command, "get gateway.drops.extra")) {
      snprintf(reply, 120, "> parse:%lu mem:%lu magic:%lu",
        (unsigned long)counters[UART_RX_BAD_PARSE], (unsigned long)counters[UART_RX_NO_MEMORY],
        (unsigned long)counters[UART_RX_BAD_MAGIC]);
      return true;
    }
    const char* traceCommand = "get gateway.trace";
    if (!strcmp(command, traceCommand) || !strncmp(command, "get gateway.trace ", 18)) {
      unsigned page = 0;
      if (command[17] != '\0') {
        char* end = nullptr;
        long parsed = strtol(command + 18, &end, 10);
        if (end == command + 18 || *end != '\0' || parsed < 0 || parsed > 11) {
          strcpy(reply, "ERR: trace page 0-11");
          return true;
        }
        page = (unsigned)parsed;
      }
      const unsigned skip = page * 3U;
      size_t pos = 0;
      pos += snprintf(reply + pos, 120 - pos, "> p%u:", page);
      if (skip >= used) {
        snprintf(reply + pos, 120 - pos, " empty");
        return true;
      }
      const unsigned available = used - skip;
      const unsigned n = available < 3U ? available : 3U;
      for (unsigned i = 0; i < n; ++i) {
        const unsigned idx = (head + HISTORY - skip - n + i) % HISTORY;
        if (pos >= 110) break;
        const int chars = snprintf(reply + pos, 120 - pos, "%s%08lx:%s",
          i ? "," : "", (unsigned long)history[idx].fingerprint, eventName(history[idx].event));
        if (chars < 0) break;
        pos += (size_t)chars;
      }
      return true;
    }
    if (!strcmp(command, "reset gateway.stats")) {
      clear();
      strcpy(reply, "OK");
      return true;
    }
    return false;
  }
}
