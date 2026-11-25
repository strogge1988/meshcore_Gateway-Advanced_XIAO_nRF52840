#include <Arduino.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <nrf.h>
#include "GatewayAdvanced.h"
#include "MyMesh.h"

extern MyMesh the_mesh;

namespace GatewayAdvanced {

// Local configuration persists in the existing nRF52 InternalFS filesystem.
// Only the *configuration* is persistent; sleep and timer state is volatile.
struct Config {
  uint32_t magic;
  uint16_t low_mv;
  uint16_t high_mv;
  uint16_t recovery_secs;
  uint8_t enabled;
  uint8_t reserved;
};
static const uint32_t CFG_MAGIC = 0x47415732UL; // GAW2; distinct from older prototypes
static const char *CFG_PATH = "/gateway_advanced_v2.dat";
static Config cfg = {CFG_MAGIC, 3450, 3750, 300, 0, 0};
static bool parked = false;
static uint8_t low_samples = 0;
static uint16_t last_mv = 0;
static uint32_t next_sample_ms = 0;
static uint32_t high_since_ms = 0;
static bool temp_off = false;
static uint32_t temp_until_ms = 0;
static uint32_t reset_reason = 0;
static bool recovered_from_power = false;

static bool reached(uint32_t now, uint32_t time) {
  return (int32_t)(now - time) >= 0;
}
static bool valid(const Config &c) {
  return c.magic == CFG_MAGIC && c.enabled <= 1 &&
         c.low_mv >= 3000 && c.low_mv <= 3700 &&
         c.high_mv > c.low_mv + 150 && c.high_mv <= 4200 &&
         c.recovery_secs >= 30 && c.recovery_secs <= 3600;
}
static bool save() {
  // nRF52 LittleFS implementation handles normal internal flash writes.
  // It is not transactional against sudden power loss; corrupt files fall
  // back to safe defaults (PowerSafe OFF).
  InternalFS.remove(CFG_PATH);
  File f = InternalFS.open(CFG_PATH, FILE_O_WRITE);
  if (!f) return false;
  const size_t n = f.write((const uint8_t*)&cfg, sizeof(cfg));
  f.close();
  return n == sizeof(cfg);
}
static void load() {
  File f = InternalFS.open(CFG_PATH);
  if (!f) return;
  Config temp = {};
  const size_t n = f.read((uint8_t*)&temp, sizeof(temp));
  f.close();
  if (n == sizeof(temp) && valid(temp)) cfg = temp;
}

void earlyResetCapture() {
  // RESETREAS is sticky. Read then clear immediately. A software-triggered
  // reset sets SREQ; all other/unknown reset types fail open (bridge ON).
  reset_reason = NRF_POWER->RESETREAS;
  NRF_POWER->RESETREAS = reset_reason;
  recovered_from_power = (reset_reason & (POWER_RESETREAS_DOG_Msk | POWER_RESETREAS_RESETPIN_Msk)) != 0 ||
                         (reset_reason & POWER_RESETREAS_SREQ_Msk) == 0;
}

static void applyBridge() {
  // A temporarily disabled bridge or a parked radio must not forward packets.
  const bool requested = the_mesh.getNodePrefs()->bridge_enabled;
  the_mesh.setBridgeState(requested && !parked && !temp_off);
}

void begin() {
  load();
  // MeshCore has now loaded its persisted preferences (and perhaps started
  // the UART bridge). On power-on / watchdog / pin-reset, force bridge ON.
  // Software reboot intentionally retains the persisted bridge preference.
  if (recovered_from_power && !the_mesh.getNodePrefs()->bridge_enabled) {
    the_mesh.getNodePrefs()->bridge_enabled = true;
    the_mesh.savePrefs();
  }
  applyBridge();
  next_sample_ms = millis();
}

bool isRadioParked() { return parked; }

static void parkRadio() {
  // Do not interrupt an ongoing TX. The next ADC tick retries.
  if (!radio_driver.isInRecvMode()) return;
  the_mesh.setBridgeState(false);
  radio_driver.powerOff(); // SX1262 sleep, not a physical power disconnect
  parked = true;
  high_since_ms = 0;
  Serial.println("Gateway Advanced: radio sleeping (low battery)");
}

static bool wakeRadio() {
  // Reinitialisation of RadioLib/SX1262 must be validated on hardware.
  if (!radio_init()) return false;
  radio_driver.begin();
  const NodePrefs* p = the_mesh.getNodePrefs();
  radio_driver.setParams(p->freq, p->bw, p->sf, p->cr);
  radio_driver.setTxPower(p->tx_power_dbm);
  radio_driver.setRxBoostedGainMode(p->rx_boosted_gain);
  parked = false;
  low_samples = 0;
  high_since_ms = 0;
  applyBridge();
  Serial.println("Gateway Advanced: SX1262 reinitialised");
  return true;
}

void loop() {
  const uint32_t now = millis();
  if (temp_off && reached(now, temp_until_ms)) {
    temp_off = false;
    applyBridge();
  }
  if (!cfg.enabled && !parked) return;
  if (!reached(now, next_sample_ms)) return;
  next_sample_ms = now + 30000UL;

  // CLI disable requests recovery, even when the battery measurement is
  // invalid. External battery protections still take precedence.
  if (parked && !cfg.enabled) {
    if (!wakeRadio()) Serial.println("Gateway Advanced: radio wake FAILED");
    return;
  }
  last_mv = board.getBattMilliVolts();
  if (last_mv < 2500 || last_mv > 4400) {
    low_samples = 0;
    high_since_ms = 0;
    return;
  }
  if (parked) {
    if (last_mv >= cfg.high_mv) {
      if (high_since_ms == 0) high_since_ms = now;
      else if ((uint32_t)(now - high_since_ms) >= (uint32_t)cfg.recovery_secs * 1000UL) {
        if (!wakeRadio()) Serial.println("Gateway Advanced: radio wake FAILED");
      }
    } else high_since_ms = 0;
  } else if (cfg.enabled) {
    if (last_mv <= cfg.low_mv) {
      if (low_samples < 3) ++low_samples;
      if (low_samples >= 3) parkRadio();
    } else low_samples = 0;
  }
}

static bool parseInt(const char *s, long *value) {
  if (!s || !*s) return false;
  char *end = nullptr;
  long n = strtol(s, &end, 10);
  if (end == s || *end || n < 0) return false;
  *value = n;
  return true;
}

bool handleCommand(const char* command, char* reply) {
  NodePrefs* prefs = the_mesh.getNodePrefs();
  if (strcmp(command, "get gateway") == 0) {
    snprintf(reply, 160, "> gateway:%s effective:%s", prefs->bridge_enabled?"on":"off", the_mesh.gatewayBridgeIsRunning()?"on":"off");
    return true;
  }
  if (strcmp(command, "set gateway on") == 0 || strcmp(command, "set gateway off") == 0) {
    prefs->bridge_enabled = strcmp(command, "set gateway on") == 0;
    temp_off = false;
    applyBridge();
    the_mesh.savePrefs();
    strcpy(reply, "OK");
    return true;
  }
  const char* temporary = "set gateway off ";
  if (strncmp(command, temporary, strlen(temporary)) == 0) {
    long seconds = 0;
    if (!parseInt(command + strlen(temporary), &seconds) || seconds < 10 || seconds > 86400) {
      strcpy(reply, "ERR: duration must be 10-86400 seconds");
      return true;
    }
    if (!prefs->bridge_enabled) {
      strcpy(reply, "ERR: permanent gateway setting OFF; enable first");
      return true;
    }
    temp_off = true;
    temp_until_ms = millis() + (uint32_t)seconds * 1000UL;
    applyBridge();
    strcpy(reply, "OK - temporary bridge off");
    return true;
  }
  if (strcmp(command, "get powersafe") == 0) {
    snprintf(reply, 160, "> powersafe:%s low:%u high:%u recovery:%us", cfg.enabled?"on":"off", cfg.low_mv, cfg.high_mv, cfg.recovery_secs);
    return true;
  }
  if (strcmp(command, "get powersafe.status") == 0) {
    snprintf(reply, 160, "> powersafe:%s radio:%s vbat:%umV", cfg.enabled?"on":"off", parked?"sleep":"active", board.getBattMilliVolts());
    return true;
  }
  if (strcmp(command, "get system.resetreason") == 0) {
    const char* reason = "POWER_ON/UNKNOWN";
    if (reset_reason & POWER_RESETREAS_DOG_Msk) reason = "WATCHDOG";
    else if (reset_reason & POWER_RESETREAS_SREQ_Msk) reason = "SOFTWARE";
    else if (reset_reason & POWER_RESETREAS_RESETPIN_Msk) reason = "RESET_PIN";
    snprintf(reply, 160, "> reset:%s raw:0x%08lx", reason, (unsigned long)reset_reason);
    return true;
  }
  if (strcmp(command, "set powersafe on") == 0 || strcmp(command, "set powersafe off") == 0) {
    const Config previous = cfg;
    cfg.enabled = strcmp(command, "set powersafe on") == 0;
    if (!save()) { cfg = previous; strcpy(reply, "ERR: save failed"); return true; }
    next_sample_ms = millis();
    strcpy(reply, "OK");
    return true;
  }
  const char *value = nullptr;
  enum { FIELD_LOW, FIELD_HIGH, FIELD_RECOVERY } field = FIELD_LOW;
  if (strncmp(command, "set powersafe.low ", 18) == 0) { field=FIELD_LOW; value=command+18; }
  else if (strncmp(command, "set powersafe.high ", 19) == 0) { field=FIELD_HIGH; value=command+19; }
  else if (strncmp(command, "set powersafe.recovery ", 23) == 0) { field=FIELD_RECOVERY; value=command+23; }
  if (value) {
    long n = 0;
    if (!parseInt(value, &n)) { strcpy(reply, "ERR: invalid number"); return true; }
    Config previous = cfg;
    if (field == FIELD_LOW && n >= 3000 && n <= 3700) cfg.low_mv = n;
    else if (field == FIELD_HIGH && n >= 3000 && n <= 4200) cfg.high_mv = n;
    else if (field == FIELD_RECOVERY && n >= 30 && n <= 3600) cfg.recovery_secs = n;
    else { strcpy(reply, "ERR: out of range"); return true; }
    if (!valid(cfg)) { cfg=previous; strcpy(reply, "ERR: high must exceed low by >150mV"); return true; }
    if (!save()) { cfg=previous; strcpy(reply, "ERR: save failed"); return true; }
    strcpy(reply, "OK");
    return true;
  }
  return false;
}
}
