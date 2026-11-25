#!/usr/bin/env python3
"""Apply the XIAO nRF52840 Gateway Advanced integration to tagged MeshCore v1.18.0.

This patch is fail-closed: unknown upstream content, wrong anchors and repeated
applications fail before writing source files.
"""
from pathlib import Path
import sys

COMMONCLI_INCLUDE = '#include "CommonCLI.h"'
COMMONCLI_HOOK = 'void CommonCLI::handleCommand(uint32_t sender_timestamp, char* command, char* reply) {'
MAIN_SETUP = 'void setup() {'
MAIN_BEGIN = '  the_mesh.begin(fs);'
MAIN_LOOP = '  the_mesh.loop();'
MAIN_SLEEP = '  if (the_mesh.getNodePrefs()->powersaving_enabled && !the_mesh.hasPendingWork()) {'
MESH_HEADER = '  void loop();\n#if defined(WITH_BRIDGE)'
TARGET_RTC = '  rtc_clock.begin(Wire);'
BOARD_WIRE = '  Wire.begin();'


def replace_once(data, old, new, where):
    n = data.count(old)
    if n != 1:
        raise ValueError(f'{where}: expected precisely one anchor, found {n}. Refusing unsafe patch.')
    return data.replace(old, new, 1)


def transform(files):
    main = files['examples/simple_repeater/main.cpp']
    cli = files['src/helpers/CommonCLI.cpp']
    mesh_h = files['examples/simple_repeater/MyMesh.h']
    target = files['variants/xiao_nrf52/target.cpp']
    board = files['variants/xiao_nrf52/XiaoNrf52Board.cpp']
    if 'GatewayAdvanced::earlyResetCapture' in main or 'GatewayAdvanced::handleCommand' in cli:
        raise ValueError('Patch already applied')
    # Include our independent implementation. All CLI entry points use CommonCLI
    # after MeshCore's existing remote-administration authentication step.
    main = replace_once(main, '#include "MyMesh.h"', '#include "MyMesh.h"\n#include "GatewayAdvanced.h"', 'main header')
    main = replace_once(main, MAIN_SETUP, MAIN_SETUP + '\n  GatewayAdvanced::earlyResetCapture();', 'reset capture')
    main = replace_once(main, '  sensors.begin();', '#ifndef XIAO_GATEWAY_EXTRAS\n  sensors.begin();\n#endif', 'disable I2C sensor probes')
    main = replace_once(main, MAIN_BEGIN, MAIN_BEGIN + '\n  GatewayAdvanced::begin();', 'prefs/boot integration')
    main = replace_once(main, '  sensors.loop();', '#ifndef XIAO_GATEWAY_EXTRAS\n  sensors.loop();\n#endif', 'disable periodic I2C sensor polling')
    main = replace_once(main, MAIN_LOOP, '  GatewayAdvanced::loop();\n  if (!GatewayAdvanced::isRadioParked()) the_mesh.loop();', 'main loop')
    main = replace_once(main, MAIN_SLEEP, '  if (!GatewayAdvanced::isRadioParked() && the_mesh.getNodePrefs()->powersaving_enabled && !the_mesh.hasPendingWork()) {', 'keep ADC/USB alive')
    cli = replace_once(cli, COMMONCLI_INCLUDE, COMMONCLI_INCLUDE + '\n#ifdef XIAO_GATEWAY_EXTRAS\n#include "GatewayAdvanced.h"\n#endif', 'common cli include')
    cli = replace_once(cli, COMMONCLI_HOOK, COMMONCLI_HOOK + '\n#ifdef XIAO_GATEWAY_EXTRAS\n    if (GatewayAdvanced::handleCommand(command, reply)) return;\n#endif', 'common cli hook')
    mesh_h = replace_once(mesh_h, MESH_HEADER, '  void loop();\n#ifdef XIAO_GATEWAY_EXTRAS\n  bool gatewayBridgeIsRunning() const { return bridge.isRunning(); }\n#endif\n#if defined(WITH_BRIDGE)', 'bridge status helper')
    target = replace_once(target, TARGET_RTC, '#ifndef XIAO_GATEWAY_EXTRAS\n  rtc_clock.begin(Wire);\n#endif', 'disable RTC probe during radio init')
    board = replace_once(board, BOARD_WIRE, '#ifndef XIAO_GATEWAY_EXTRAS\n  Wire.begin();\n#endif', 'reserve D6/D7 UART not I2C')
    files['variants/xiao_nrf52/target.cpp'] = target
    files['variants/xiao_nrf52/XiaoNrf52Board.cpp'] = board
    files['examples/simple_repeater/main.cpp'] = main
    files['src/helpers/CommonCLI.cpp'] = cli
    files['examples/simple_repeater/MyMesh.h'] = mesh_h
    return files


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else 'firmware')
    paths = ['examples/simple_repeater/main.cpp', 'src/helpers/CommonCLI.cpp', 'examples/simple_repeater/MyMesh.h',
             'variants/xiao_nrf52/target.cpp', 'variants/xiao_nrf52/XiaoNrf52Board.cpp']
    files = {p: (root/p).read_text(encoding='utf-8') for p in paths}
    result = transform(files)
    src = Path(__file__).resolve().parent.parent/'overrides'
    dest = root/'examples/simple_repeater'
    for name in ('GatewayAdvanced.h','GatewayAdvanced.cpp'):
        if (dest/name).exists():
            raise ValueError(f'Unexpected upstream file {name}; refusing to overwrite')
        if not (src/name).is_file():
            raise ValueError(f'Missing recipe override {name}')
    # Only modify after all source-file checks passed.
    for p, content in result.items():
        (root/p).write_text(content, encoding='utf-8')
    for name in ('GatewayAdvanced.h','GatewayAdvanced.cpp'):
        (dest/name).write_bytes((src/name).read_bytes())
    print('Advanced patch applied to officially pinned MeshCore 1.18.0.')

if __name__ == '__main__':
    main()
