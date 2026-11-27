"""Offline recipe checks. NOT a substitute for building against MeshCore upstream."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import apply_special


class GatewayAdvancedPatchTests(unittest.TestCase):
    def setUp(self):
        self.files = {
            'examples/simple_repeater/main.cpp': '#include "MyMesh.h"\nvoid setup() {\n  sensors.begin();\n  the_mesh.begin(fs);\n}\nvoid loop() {\n  the_mesh.loop();\n  sensors.loop();\n  if (the_mesh.getNodePrefs()->powersaving_enabled && !the_mesh.hasPendingWork()) {\n  }\n}\n',
            'src/helpers/CommonCLI.cpp': '#include "CommonCLI.h"\nvoid CommonCLI::handleCommand(uint32_t sender_timestamp, char* command, char* reply) {\n}\n',
            'examples/simple_repeater/MyMesh.h': ('  void loop();\n\n#if defined(WITH_BRIDGE)\n'
                                                 '  void setBridgeState(bool enable) override {\n  }\n'),
            'variants/xiao_nrf52/target.cpp': '  rtc_clock.begin(Wire);\n',
            'variants/xiao_nrf52/XiaoNrf52Board.cpp': '  Wire.begin();\n',
        }

    def test_all_three_upstream_files_patched(self):
        result = apply_special.transform(self.files.copy())
        self.assertIn('GatewayAdvanced::earlyResetCapture();', result['examples/simple_repeater/main.cpp'])
        self.assertIn('GatewayAdvanced::begin();', result['examples/simple_repeater/main.cpp'])
        self.assertIn('if (!GatewayAdvanced::isRadioParked()) the_mesh.loop();', result['examples/simple_repeater/main.cpp'])
        self.assertIn('GatewayAdvanced::handleCommand(command, reply)', result['src/helpers/CommonCLI.cpp'])
        self.assertIn('gatewayBridgeIsRunning()', result['examples/simple_repeater/MyMesh.h'])
        self.assertIn('#ifndef XIAO_GATEWAY_EXTRAS', result['variants/xiao_nrf52/target.cpp'])
        self.assertIn('#ifndef XIAO_GATEWAY_EXTRAS', result['variants/xiao_nrf52/XiaoNrf52Board.cpp'])

    def test_bridge_header_upstream_whitespace_regression(self):
        # v2 patch was too strict about the lines immediately following loop().
        for following in ('\n#if defined(WITH_BRIDGE)',
                          '\n\n#if defined(WITH_BRIDGE)',
                          '\n  #if defined(WITH_BRIDGE)',
                          '\r\n#if defined(WITH_BRIDGE)'):
            files = self.files.copy()
            files['examples/simple_repeater/MyMesh.h'] = (
                'public:\n  void loop();' + following +
                '\n  void setBridgeState(bool enable) override { }\n')
            updated = apply_special.transform(files)['examples/simple_repeater/MyMesh.h']
            self.assertEqual(updated.count('gatewayBridgeIsRunning() const'), 1)
            self.assertIn('void setBridgeState(bool enable) override', updated)
            self.assertIn('WITH_RS232_BRIDGE', updated)

    def test_reject_missing_bridge_api(self):
        self.files['examples/simple_repeater/MyMesh.h'] = '  void loop();\n'
        with self.assertRaisesRegex(ValueError, 'bridge status helper'):
            apply_special.transform(self.files)

    def test_reject_double_application(self):
        with self.assertRaises(ValueError):
            apply_special.transform(apply_special.transform(self.files.copy()))

    def test_reject_unknown_upstream(self):
        self.files['examples/simple_repeater/main.cpp'] = 'void setup() {}'
        with self.assertRaises(ValueError):
            apply_special.transform(self.files)

    def test_feature_battery_limits_and_recovery(self):
        source = (ROOT/'overrides/GatewayAdvanced.cpp').read_text()
        for marker in ('3450, 3750, 300', 'low_samples >= 3', 'parkRadio()',
                       'wakeRadio()', 'radio_driver.powerOff()', 'getBattMilliVolts()',
                       'recovery_secs * 1000UL'):
            self.assertIn(marker, source)

    def test_power_restore_vs_software_reset(self):
        source = (ROOT/'overrides/GatewayAdvanced.cpp').read_text()
        self.assertIn('NRF_POWER->RESETREAS', source)
        self.assertIn('POWER_RESETREAS_SREQ_Msk', source)
        self.assertIn('the_mesh.savePrefs()', source)
        self.assertIn('if (recovered_from_power && !the_mesh.getNodePrefs()->bridge_enabled)', source)

    def test_remote_common_cli_is_shared(self):
        source = (ROOT/'scripts/apply_special.py').read_text()
        self.assertIn('CommonCLI::handleCommand', source)
        self.assertIn('GatewayAdvanced::handleCommand', source)

    def test_temporary_disable_is_nonpersistent(self):
        source = (ROOT/'overrides/GatewayAdvanced.cpp').read_text()
        self.assertIn('set gateway off ', source)
        self.assertIn('temp_off = true;', source)
        self.assertIn('temp_until_ms', source)

    def test_arduino_low_high_macro_collision_regression(self):
        source = (ROOT/'overrides/GatewayAdvanced.cpp').read_text()
        header = (ROOT/'tests/stubs/Arduino.h').read_text()
        self.assertIn('#define LOW (0x0)', header)
        self.assertIn('#define HIGH (0x1)', header)
        self.assertIn('enum { FIELD_LOW, FIELD_HIGH, FIELD_RECOVERY }', source)
        self.assertNotIn('enum { LOW, HIGH, RECOVERY }', source)
        self.assertIn('field == FIELD_LOW', source)
        self.assertIn('field == FIELD_HIGH', source)

    def test_expected_user_commands(self):
        source = (ROOT/'overrides/GatewayAdvanced.cpp').read_text()
        for name in ('get gateway', 'set gateway on', 'set gateway off', 'get powersafe',
                     'set powersafe.low ', 'set powersafe.high ', 'set powersafe.recovery ',
                     'get powersafe.status', 'get system.resetreason'):
            self.assertIn(name, source)
