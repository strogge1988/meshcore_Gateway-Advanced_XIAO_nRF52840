#pragma once
#include <Arduino.h>
struct File { explicit operator bool()const; size_t write(const uint8_t*,size_t); size_t read(uint8_t*,size_t); void close(); };
struct FakeFS { void remove(const char*); File open(const char*); File open(const char*, int); };
extern FakeFS InternalFS;
struct NodePrefs { bool bridge_enabled; float freq, bw; uint8_t sf, cr; int8_t tx_power_dbm; bool rx_boosted_gain; };
struct MyMesh { NodePrefs* getNodePrefs(); void setBridgeState(bool); bool gatewayBridgeIsRunning()const; void savePrefs(); };
extern MyMesh the_mesh;
struct FakeRadio { bool isInRecvMode(); void powerOff(); void begin(); void setParams(float,float,uint8_t,uint8_t); void setTxPower(int8_t); void setRxBoostedGainMode(bool); };
extern FakeRadio radio_driver;
struct FakeBoard { uint16_t getBattMilliVolts(); };
extern FakeBoard board;
bool radio_init();
