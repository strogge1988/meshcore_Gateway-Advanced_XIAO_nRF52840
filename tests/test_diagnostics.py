import unittest, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import apply_diagnostics

# Small anchored upstream excerpts; these are synthetic fixtures, NOT a full
# upstream build or proof of compatibility. Full sources are checked by CI.
class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.parts={
            'src/helpers/bridges/RS232Bridge.cpp': '#include "RS232Bridge.h"\n// Invalid magic byte, reset and start over\nBRIDGE_DEBUG_PRINTLN("RX invalid length %d, resetting\\n", len);\nif (pkt->readFrom(_rx_buffer + 4, len)) {\nBRIDGE_DEBUG_PRINTLN("RX failed to parse packet\\n");\nBRIDGE_DEBUG_PRINTLN("RX failed to allocate packet\\n");\nBRIDGE_DEBUG_PRINTLN("RX checksum mismatch, rcv=0x%04x\\n", received_checksum);\nif (!_seen_packets.wasSeen(packet)) {\nBRIDGE_DEBUG_PRINTLN("TX packet too large (payload=%d, max=%d)\\n", len, MAX_TRANS_UNIT + 1);\n_serial->write(buffer, len + SERIAL_OVERHEAD);\nBRIDGE_DEBUG_PRINTLN("TX, len=%d crc=0x%04x\\n", len, checksum);\n}\n',
            'src/helpers/bridges/BridgeBase.cpp': '#include "BridgeBase.h"\n_mgr->queueInbound(packet, millis() + _prefs->bridge_delay);\n  } else {\n    _mgr->free(packet);\n  }\n}\n',
            'examples/simple_repeater/MyMesh.cpp': '#include "MyMesh.h"\nvoid MyMesh::logRx(mesh::Packet *pkt, int len, float score) {\n}\nvoid MyMesh::logTx(mesh::Packet *pkt, int len) {\n}\nvoid MyMesh::logTxFail(mesh::Packet *pkt, int len) {\n}\n'
        }
    def test_patch_routes_and_counters(self):
        out=apply_diagnostics.transform(self.parts.copy())
        self.assertIn('UART_RX_BAD_CRC',out['src/helpers/bridges/RS232Bridge.cpp'])
        self.assertIn('UART_RX_DUP',out['src/helpers/bridges/BridgeBase.cpp'])
        self.assertIn('LORA_TX_FAIL',out['examples/simple_repeater/MyMesh.cpp'])
        self.assertIn('UART_TX_DUP',out['src/helpers/bridges/RS232Bridge.cpp'])
    def test_reject_double_patch(self):
        with self.assertRaises(ValueError):
            apply_diagnostics.transform(apply_diagnostics.transform(self.parts.copy()))
    def test_fail_closed_missing_source(self):
        self.parts['src/helpers/bridges/RS232Bridge.cpp']='#include "RS232Bridge.h"'
        with self.assertRaises(ValueError): apply_diagnostics.transform(self.parts)
    def test_remote_cli_integration(self):
        cpp=(ROOT/'overrides/GatewayAdvanced.cpp').read_text()
        self.assertIn('GatewayDiagnostics::handleCommand(command, reply)',cpp)
        self.assertIn('CommonCLI::handleCommand', (ROOT/'scripts/apply_special.py').read_text())
    def test_workflow_ota(self):
        yml=(ROOT/'.github/workflows/build.yml').read_text()
        self.assertIn('adafruit-nrfutil dfu genpkg',yml)
        self.assertIn('firmware-dfu.zip',yml)
        self.assertIn('scripts/apply_diagnostics.py firmware',yml)
        self.assertIn('application-only',yml.lower())
