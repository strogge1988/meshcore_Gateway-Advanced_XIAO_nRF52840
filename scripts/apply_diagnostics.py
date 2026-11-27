#!/usr/bin/env python3
"""Fail-closed MeshCore 1.18.0 diagnostic instrumentation. No routing changes."""
import sys
import re
from pathlib import Path

def single(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise ValueError(f'{label}: anchor count {n}, expected 1')
    return text.replace(old, new, 1)

def single_regex(text, pattern, replacement, label):
    out, n = re.subn(pattern, replacement, text, count=0, flags=re.MULTILINE)
    if n != 1:
        raise ValueError(f'{label}: anchor count {n}, expected 1')
    return out

def transform(files):
    serial = files['src/helpers/bridges/RS232Bridge.cpp']
    base = files['src/helpers/bridges/BridgeBase.cpp']
    mesh = files['examples/simple_repeater/MyMesh.cpp']
    if 'GatewayDiagnostics::record' in serial or 'GatewayDiagnostics::record' in base or 'GatewayDiagnostics::record' in mesh:
        raise ValueError('diagnostics already applied')
    serial = single(serial, '#include "RS232Bridge.h"', '#include "RS232Bridge.h"\n#include "GatewayDiagnostics.h"', 'serial include')
    base = single(base, '#include "BridgeBase.h"', '#include "BridgeBase.h"\n#include "GatewayDiagnostics.h"', 'bridge base include')
    mesh = single(mesh, '#include "MyMesh.h"', '#include "MyMesh.h"\n#include "GatewayDiagnostics.h"', 'mesh include')

    serial = single(serial,
        'BRIDGE_DEBUG_PRINTLN("RX invalid length %d, resetting\\n", len);',
        'GatewayDiagnostics::record(GatewayDiagnostics::UART_RX_BAD_LENGTH);\n      BRIDGE_DEBUG_PRINTLN("RX invalid length %d, resetting\\n", len);', 'bad length')
    serial = single(serial,
        'if (pkt->readFrom(_rx_buffer + 4, len)) {',
        'if (pkt->readFrom(_rx_buffer + 4, len)) {\n          GatewayDiagnostics::record(GatewayDiagnostics::UART_RX_FRAME, pkt->getPayloadType(), pkt->payload, pkt->payload_len);', 'valid frame')
    serial = single(serial,
        'BRIDGE_DEBUG_PRINTLN("RX failed to parse packet\\n");',
        'GatewayDiagnostics::record(GatewayDiagnostics::UART_RX_BAD_PARSE);\n          BRIDGE_DEBUG_PRINTLN("RX failed to parse packet\\n");', 'parse error')
    serial = single(serial,
        'BRIDGE_DEBUG_PRINTLN("RX failed to allocate packet\\n");',
        'GatewayDiagnostics::record(GatewayDiagnostics::UART_RX_NO_MEMORY);\n          BRIDGE_DEBUG_PRINTLN("RX failed to allocate packet\\n");', 'allocation error')
    serial = single(serial,
        'BRIDGE_DEBUG_PRINTLN("RX checksum mismatch, rcv=0x%04x\\n", received_checksum);',
        'GatewayDiagnostics::record(GatewayDiagnostics::UART_RX_BAD_CRC);\n          BRIDGE_DEBUG_PRINTLN("RX checksum mismatch, rcv=0x%04x\\n", received_checksum);', 'checksum error')
    serial = single(serial,
        '// Invalid magic byte, reset and start over',
        '// Invalid magic byte, reset and start over\n        GatewayDiagnostics::record(GatewayDiagnostics::UART_RX_BAD_MAGIC);', 'magic header')
    serial = single(serial,
        'if (!_seen_packets.wasSeen(packet)) {',
        'GatewayDiagnostics::record(GatewayDiagnostics::UART_TX_CANDIDATE, packet->getPayloadType(), packet->payload, packet->payload_len);\n  if (!_seen_packets.wasSeen(packet)) {', 'tx attempt')
    serial = single(serial,
        'BRIDGE_DEBUG_PRINTLN("TX packet too large (payload=%d, max=%d)\\n", len, MAX_TRANS_UNIT + 1);',
        'GatewayDiagnostics::record(GatewayDiagnostics::UART_TX_TOO_LARGE);\n      BRIDGE_DEBUG_PRINTLN("TX packet too large (payload=%d, max=%d)\\n", len, MAX_TRANS_UNIT + 1);', 'large packet')
    serial = single(serial,
        '_serial->write(buffer, len + SERIAL_OVERHEAD);',
        'size_t written = _serial->write(buffer, len + SERIAL_OVERHEAD);\n  if (written == len + SERIAL_OVERHEAD) {\n    GatewayDiagnostics::record(GatewayDiagnostics::UART_TX_OK, packet->getPayloadType(), packet->payload, packet->payload_len);\n  } else {\n    GatewayDiagnostics::record(GatewayDiagnostics::UART_TX_SHORT_WRITE);\n  }', 'uart write')
    # Add an else on the *outer* duplicate-cache branch (after debug line).
    serial = single_regex(serial,
        r'(BRIDGE_DEBUG_PRINTLN\("TX, len=%d crc=0x%04x\\n", len, checksum\);\s*\})',
        r'\1 else {\n    GatewayDiagnostics::record(GatewayDiagnostics::UART_TX_DUP, packet->getPayloadType(), packet->payload, packet->payload_len);\n  }', 'tx duplicate')
    base = single(base,
        '_mgr->queueInbound(packet, millis() + _prefs->bridge_delay);',
        'GatewayDiagnostics::record(GatewayDiagnostics::UART_RX_QUEUED, packet->getPayloadType(), packet->payload, packet->payload_len);\n    _mgr->queueInbound(packet, millis() + _prefs->bridge_delay);', 'queued for mesh')
    base = single_regex(base,
        r'(}\s*else\s*{\s*)(_mgr->free\(packet\);)',
        r'\1GatewayDiagnostics::record(GatewayDiagnostics::UART_RX_DUP, packet->getPayloadType(), packet->payload, packet->payload_len);\n    \2', 'rx bridge duplicate')
    mesh = single(mesh,
        'void MyMesh::logRx(mesh::Packet *pkt, int len, float score) {',
        'void MyMesh::logRx(mesh::Packet *pkt, int len, float score) {\n  GatewayDiagnostics::record(GatewayDiagnostics::LORA_RX, pkt->getPayloadType(), pkt->payload, pkt->payload_len);', 'lora rx')
    mesh = single(mesh,
        'void MyMesh::logTx(mesh::Packet *pkt, int len) {',
        'void MyMesh::logTx(mesh::Packet *pkt, int len) {\n  GatewayDiagnostics::record(GatewayDiagnostics::LORA_TX, pkt->getPayloadType(), pkt->payload, pkt->payload_len);', 'lora tx')
    mesh = single(mesh,
        'void MyMesh::logTxFail(mesh::Packet *pkt, int len) {',
        'void MyMesh::logTxFail(mesh::Packet *pkt, int len) {\n  GatewayDiagnostics::record(GatewayDiagnostics::LORA_TX_FAIL, pkt->getPayloadType(), pkt->payload, pkt->payload_len);', 'lora tx fail')
    files['src/helpers/bridges/RS232Bridge.cpp'] = serial
    files['src/helpers/bridges/BridgeBase.cpp'] = base
    files['examples/simple_repeater/MyMesh.cpp'] = mesh
    return files

def main():
    root = Path(sys.argv[1] if len(sys.argv)>1 else 'firmware')
    paths = ['src/helpers/bridges/RS232Bridge.cpp', 'src/helpers/bridges/BridgeBase.cpp', 'examples/simple_repeater/MyMesh.cpp']
    files={p:(root/p).read_text(encoding='utf-8') for p in paths}
    new=transform(files)
    for p,s in new.items(): (root/p).write_text(s, encoding='utf-8')
    print('Gateway Advanced v5 diagnostics instrumentation applied.')
if __name__ == '__main__': main()
