#pragma once

// Experimental project-specific extension for MeshCore 1.18.0 XIAO nRF52840.
// The CLI entry point is shared by local serial and authenticated remote admin.
namespace GatewayAdvanced {
  void earlyResetCapture();
  void begin();
  void loop();
  bool isRadioParked();
  bool handleCommand(const char *command, char *reply);
}
