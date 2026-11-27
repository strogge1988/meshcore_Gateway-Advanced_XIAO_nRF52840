# Meshcore Gateway – Advanced v5 (Diagnostics + OTA)

> **Experimentelles Community-Projekt.** Diagnose-Build für zwei Seeed XIAO nRF52840 mit Wio-SX1262 als UART-Bridge zwischen zwei MeshCore-LoRa-Profilen. Stand: 27. November 2026. **Nicht offiziell von MeshCore freigegeben; vollständiger GitHub-/Hardware-Build noch ausstehend.**

## Neu in v5 – Diagnose statt Routingänderung

Zoller1 (altes Profil) sendet beobachtete Flood-Pakete, Zoller2 (neues Profil) sendet nicht alle davon weiter. Die aktuellen Einstellungen (`bridge.source logTx`, 115200 Baud, `bridge.delay 500`, aktivierte Regions und PowerSafe OFF) liefern keinen eindeutigen Grund. Dieser Build **ändert keine Flood-Regeln, keine Hash-Caches und keine UART-Filterung**, sondern ergänzt RAM-Zähler für die Strecke.

Alle Projekt-CLI-Kommandos (einschließlich der neuen Diagnosebefehle) laufen über `CommonCLI::handleCommand` und damit über denselben Handler für **USB und authentifizierte MeshCore-Remote-CLI**. Remote-Zugriff erfordert weiterhin funktionierende LoRa-Rückwege, Admin-Rechte und eine aktive Funkverbindung. Alle Befehle müssen nach der Installation **praktisch über Remote-Admin getestet** werden.

### Neue Remote-CLI-Befehle

| Befehl | Bedeutung |
| --- | --- |
| `get gateway.stats` | `lrx`/`ltx`/`lfail`: lokale LoRa-Ereignisse; `cand`: UART-Ausgabeversuche; `utx`: erfolgreich an UART-Treiber übergebene Frames; `urx`: gültig geparste UART-Frames; `queued`: an MeshCore übergebene UART-Pakete |
| `get gateway.drops` | `td`: UART-TX durch Bridge-Duplikatcache; `big`: zu groß; `short`: unvollständig an Treiber geschrieben; `rd`: UART-RX durch Bridge-Duplikatcache; `len`, `crc`: Frame-/Prüfsummenfehler; weitere Fehler unter `get gateway.drops.extra` |
| `get gateway.drops.extra` | `parse`/`mem`/`magic`: zusätzliche Parser-, Paketpuffer- und Synchronisationsfehler |
| `get gateway.trace` / `get gateway.trace 1` (bis 11) | Je drei Ereignisse pro Seite (Seite 0 = neueste, bis zu 36 Ereignisse im RAM). Kurzer 32-Bit-Payload-Fingerprint. Derselbe Payload sollte auf beiden Geräten denselben Wert ergeben. |
| `reset gateway.stats` | Alle Diagnosezähler und Ereignisse im RAM zurücksetzen. Wirkt lokal auf dem angesprochenen Gerät. |

**Hinweise zur Interpretation:** `utx` bedeutet nur, dass der UART-Treiber die Bytes entgegengenommen hat, nicht dass Zoller2 sie empfangen hat. `queued` bedeutet, dass ein Frame zur MeshCore-Verarbeitung eingeplant wurde, **nicht**, dass er als LoRa-Flood ausgesendet wurde. `ltx` ist ein logTx-Ereignis, keine Garantie für erfolgreichen Empfang der Gegenstelle. Die Fingerprints sind nur Diagnosekennungen und **nicht** der offizielle MeshCore-Duplikat-Hash; Kollisionen sind möglich. `magic` zählt Sync-Fehler pro Byte und kann bei Leitungsstörungen hoch sein. **Die Ereignisse werden nicht auf Flash gespeichert und bei Reboot gelöscht. Mit `get gateway.trace 1` bis `get gateway.trace 11` bleiben ältere Einträge sichtbar, selbst wenn Admin-Anfragen zusätzliche Pakete erzeugen.**

### Vorgeschlagener Test

1. Auf Zoller1 und Zoller2 `reset gateway.stats` über die Remote-CLI senden.
2. Auf altem Mesh eine klar identifizierbare neue Flood-Nachricht senden, welche Zoller1 nachweislich per LoRa weiterleitet.
3. Beide Repeater mit `get gateway.stats`, `get gateway.drops`, `get gateway.drops.extra`, `get gateway.trace 0` bis `get gateway.trace 3` abfragen und die Ausgabe vergleichen.
4. Zoller1 hat `ltx`, aber kein entsprechendes `utx` → Bridge-eigene Unterdrückung oder Schreibfehler untersuchen. Zoller1 hat `utx`, Zoller2 kein `urx` → UART-Verkabelung/Framing prüfen. Zoller2 hat `urx` und `queued`, aber kein `ltx` → erst dann MeshCore-Routing/Duplikate untersuchen.

### Build-Artefakte

GitHub Actions soll bereitstellen:

- `firmware.uf2` – USB-Bootloader/Drag & Drop
- `firmware.bin` – Applikationsabbild, für spezielle Flashwerkzeuge
- `firmware-dfu.zip` – **Application-only Adafruit BLE-DFU-Archiv**; Bootloader und SoftDevice werden nicht mitgeschrieben
- `build_info.txt` – Upstream-Tag und Commit

DFU wird mit `adafruit-nrfutil dfu genpkg --dev-type 0x0052 --application firmware.hex` erzeugt. Nutzung über `start ota` und Nordic `nRF Device Firmware Update` in BLE-Reichweite mit **kompatiblem Bootloader**. Wenn der Erstellungs- oder Manifestcheck fehlschlägt, bricht der Workflow ab. **UF2 und DFU-ZIP sind verschiedene Formate; für Bluetooth-DFU die ZIP verwenden.**

### Bleiben Einstellungen beim OTA erhalten?

Bei einem regulären *Application-only*-DFU mit unveränderter Flash-/Dateisystemaufteilung bleiben Repeater-Identität, Admin-Zugänge, LoRa-Profile, Regions sowie gespeicherte `gateway`-/`powersafe`-Werte normalerweise erhalten. Ein Full-Erase, Bootloader-/Partitionierungswechsel oder ein beschädigtes Dateisystem kann dies verhindern. **Vor dem ersten Update Einstellungen sichern; zunächst nur Zoller1 oder Zoller2 aktualisieren.** Kein automatischer Factory Reset vorgesehen.

Quellen: [MeshCore 1.18.0](https://github.com/meshcore-dev/MeshCore/releases/tag/repeater-v1.18.0), [RS232Bridge.cpp](https://github.com/meshcore-dev/MeshCore/blob/81dbae5/src/helpers/bridges/RS232Bridge.cpp), [BridgeBase.cpp](https://github.com/meshcore-dev/MeshCore/blob/81dbae5/src/helpers/bridges/BridgeBase.cpp), [MeshCore OTA-FAQ](https://docs.meshcore.io/faq/), [Adafruit nrfutil](https://github.com/adafruit/Adafruit_nRF52_nrfutil). Projektkonzept und Feldtests: Repository-Betreiber. Build-Rezept, Diagnose-Instrumentierung und Dokumentation: in Zusammenarbeit mit ChatGPT von OpenAI (GPT-6) erstellt. Original-Firmware: meshcore-dev und Mitwirkende.

---

# Meshcore Gateway – Advanced

**Experimentelle bidirektionale UART-Bridge zwischen zwei MeshCore-Funkprofilen**, mit zusätzlichen CLI-Befehlen für Gateway-Steuerung und batteriespannungsabhängigen SX1262-Schlafmodus.

> **Entwicklungsstand (25.11.2026): experimenteller Build-Rezept-Prototyp.** Der vorherige GitHub-Compilerlauf hat einen Arduino-Makronamenskonflikt in `GatewayAdvanced.cpp` aufgedeckt. Dieser ist in v4 korrigiert und durch lokale Python-Tests sowie eine C++-Syntaxprüfung mit Arduino-Makros abgesichert. Ein vollständig erfolgreicher PlatformIO-Build auf GitHub und echte Tests an zwei XIAO nRF52840 stehen noch aus. Insbesondere das Wiederaufwachen des SX1262, die Reset-Ursachenerkennung und die netzübergreifende Remote-Administration sind **nicht hardwarevalidiert**. Keinen unbeaufsichtigten Einsatz ohne Testreihe.

Dies ist ein **inoffizielles Community-Projekt**, keine offizielle MeshCore-Firmware. **Die separate RAW-Version** ohne zusätzliche PowerSafe-Logik heißt **Meshcore Gateway**. Sie wird in einem eigenen Repository gepflegt.


## Änderungen in Advanced v4 (Compiler-Fix)

- **Behoben:** Arduino definiert `LOW` und `HIGH` als globale Makros. In `GatewayAdvanced.cpp` heißen die internen Feld-IDs jetzt `FIELD_LOW`, `FIELD_HIGH` und `FIELD_RECOVERY`, damit der nRF52-Compiler keinen Namenskonflikt auslöst.
- Der C++-Syntaxcheck verwendet nun Test-Stubs mit den echten Arduino-Makronamen (`LOW` und `HIGH`), um diesen Fehler künftig frühzeitig zu erkennen.
- Ein zusätzlicher Regressionstest prüft die neuen Bezeichner.
- **Update von v3:** Nur `overrides/GatewayAdvanced.cpp`, `tests/stubs/Arduino.h` und `tests/test_special.py` im Repository ersetzen; anschließend einen **neuen** GitHub-Actions-Lauf auf dem aktuellen Branch starten.
- **Buildstatus:** Der GitHub-Compilerlauf der Vorversion v3 scheiterte an diesem Bezeichnerkonflikt. Für v4 sind lokale Tests und Host-Syntaxprüfung erfolgreich; ein vollständiger PlatformIO-Build und Hardwaretests stehen noch aus.

## Änderungen gegenüber Advanced v2 (Patch-Fix v3)

- **Bugfix:** `scripts/apply_special.py` patcht den Bridge-Status-Helfer in `MyMesh.h` anhand der eindeutigen öffentlichen Methode `void loop();`. Der bisherige fragile Mehrzeilenanker auf den direkt folgenden `WITH_BRIDGE`-Block entfällt.
- Der Patch prüft weiterhin explizit die Bridge-API von MeshCore und bricht bei unbekannter Quellstruktur sicher ab.
- Zwei zusätzliche Regressionstests decken unterschiedliche Leerzeilen/Einrückungen und eine fehlende Bridge-API ab.
- **Nicht verifiziert:** Ein vollständiger PlatformIO-/GitHub-Actions-Build sowie das Verhalten auf realer Hardware. Bis zum erfolgreichen Build und Hardwaretest bleibt Advanced experimentell.

**Update eines vorhandenen v2-Repositories:** Nur `scripts/apply_special.py` und `tests/test_special.py` aus dem separaten Patch-Fix v3 ersetzen. Danach einen **neuen** GitHub-Actions-Lauf auf dem aktualisierten Branch starten (keinen Re-run eines alten Commits).

## Hardware und Funktionsweise

- 2 × **Seeed Studio XIAO nRF52840** + je 1 × **Wio-SX1262 for XIAO**.
- Zwei eigenständige MeshCore-Repeater, jeder mit eigener Frequenz, Bandbreite, SF und Coding Rate.
- Gekreuzte **3,3-V-UART-Verbindung**, keine echte ±12-V-RS232-Schnittstelle. **D6/D7 sind im offiziellen Board-Target zugleich I²C-Leitungen.** Diese Advanced-Variante deaktiviert deshalb dort die I²C-Initialisierung und automatische Sensor-/RTC-Probes; externe I²C-Sensoren bzw. RTCs auf D6/D7 können in dieser Konfiguration **nicht** parallel betrieben werden. Die interne Fallback-Uhr bleibt für MeshCore verfügbar.
- Originale MeshCore-Pakete werden über UART transportiert: **keine Regions-Übersetzung**, keine Neugenerierung von Senderidentitäten.
- `bridge.source tx` spiegelt die vom jeweiligen Repeater zur LoRa-Aussendung ausgewählten Pakete an die UART-Bridge; **auf beiden XIAOs `tx` verwenden**. Die UART ist trotzdem bidirektional.
- Regions-Regeln sind die **normalen MeshCore-Flood-Filter**, keine allgemeine Firewall für Direct Messages.

```text
  Mesh A / LoRa-Profil A                        Mesh B / LoRa-Profil B
       ~~~~~                                     ~~~~~
  XIAO nRF52840 A    TX D6  ────────>  RX D7    XIAO nRF52840 B
   + Wio-SX1262     RX D7  <────────  TX D6     + Wio-SX1262
                   GND    ──────────  GND
             Beide über geeignete gemeinsame 1S-Versorgung
```

**Wichtig:** Beide USB-Anschlüsse können intern LiPo-Ladeelektronik speisen. Bei gemeinsamem Akkupack muss unbeabsichtigtes paralleles Laden über USB und externen TP4056 vermieden werden.

## Zusätzliche Advanced-Befehle

Diese Befehle **gehören nicht zum offiziellen MeshCore**. Sie werden im gemeinsamen `CommonCLI::handleCommand()` eingehängt, der sowohl von der lokalen seriellen Konsole als auch von der **bereits authentifizierten** MeshCore-Remote-CLI aufgerufen wird. Remote-Zugang und Rückroute müssen funktionieren; keine zusätzlichen Berechtigungen werden umgangen.

| Befehl | Zweck |
|---|---|
| `set gateway on` | UART-Bridge dauerhaft einschalten und Einstellung speichern |
| `set gateway off` | UART-Bridge dauerhaft ausschalten und Einstellung speichern |
| `get gateway` | Gespeicherten Wunsch und tatsächlichen Bridge-Zustand anzeigen |
| `set gateway off 300` | Bridge **temporär** für 300 Sekunden ausschalten; danach automatische Rückkehr (10–86400 s) |
| `set powersafe on` / `off` | Batterieschutz dauerhaft aktivieren/deaktivieren |
| `get powersafe` | Schutzstatus, Low/High-Schwellen und Erholungszeit abfragen |
| `get powersafe.status` | SX1262-Zustand und Batteriespannung auslesen |
| `set powersafe.low 3450` | Untere Schwelle in Millivolt (gültig 3000–3700) |
| `set powersafe.high 3750` | Obere Schwelle in Millivolt (gültig bis 4200, mindestens 151 mV über Low) |
| `set powersafe.recovery 300` | Stabile Spannung vor Funkreaktivierung in Sekunden (30–3600) |
| `get system.resetreason` | Vom Firmware-Start erfasste Reset-Ursache inkl. Registerwert anzeigen |

**Standardwerte:** PowerSafe `off`, Low = 3450 mV, High = 3750 mV, Recovery = 300 Sekunden. ADC-Abfrage alle 30 Sekunden. Nach **drei aufeinanderfolgenden niedrigen Messungen** wird beim nächsten geeigneten RX-Zustand das Funkmodul schlafen gelegt.

PowerSafe stoppt den LoRa-Funkbetrieb und pausiert währenddessen die UART-Bridge. Der nRF52840 bleibt aktiv, damit der Akku weiterhin gemessen werden kann. **Die Funkempfangs- und Fernadministrationsfunktion ist im Sleep-Modus nicht verfügbar.** Die lokalen USB-CLI-Befehle sollen weiterhin erreichbar bleiben. Die SX1262-Versorgung wird nicht physisch getrennt. Das aktuelle Verfahren nutzt `radio_driver.powerOff()` und bei Erholung eine RadioLib-Reinitialisierung; die Zuverlässigkeit muss real getestet werden.

### Neustart- und Recovery-Regeln

| Ereignis | Gateway-Bridge | SX1262 | PowerSafe-Konfiguration |
|---|---|---|---|
| `set gateway off` | OFF | Normalbetrieb | Bleibt bestehen |
| `reboot` über USB oder authentifizierte LoRa-CLI | Gespeicherten ON/OFF-Wunsch übernehmen | Wird neu initialisiert; bei Unterspannung später erneut Sleep | Bleibt bestehen |
| Echter Power-on-Reset oder nicht als Software-Reset erkannter Start | **ON**, wird auch in MeshCore-Preferences gespeichert | Standardmäßig ON, soweit Bootspannung reicht | Bleibt bestehen |
| Watchdog- oder Reset-Pin-Ereignis | **ON**, wiederherstellungsorientiert | Standardmäßig ON, PowerSafe kann anschließend eingreifen | Bleibt bestehen |
| `set gateway off 300`, dann Neustart | **Temporäre Pause endet beim Neustart**; permanenter gespeicherter Wunsch gilt bzw. Power-on setzt ON | Normaler Boot | Bleibt bestehen |
| Niedrige Spannung bei `powersafe on` | Temporär pausiert, gespeicherter ON/OFF-Wunsch unverändert | Sleep | Bleibt bestehen |
| Erholung oberhalb High für Recovery-Dauer | Zustand gemäß gespeichertem Wunsch und eventueller Pause | Aufweckversuch | Bleibt bestehen |

Zur Reset-Unterscheidung wird früh `NRF_POWER->RESETREAS` ausgelesen und anschließend gelöscht. Ein **SREQ**-Software-Reset wird als gewünschter Zustandserhalt behandelt; Watchdog, Reset-Pin und nicht sicher erkannte Neustarts führen vorsichtshalber zur Aktivierung der Bridge. **Grenze:** Bootloader können Reset-Indikatoren beeinflussen. Ein starker Spannungseinbruch ohne vollständiges Power-on kann anders klassifiziert werden; die Logik kann einen hängenden oder stromlosen nRF52840 nicht eigenständig wiederbeleben.

**Remote-Warnung:** `set gateway off` kann gerade den Verbindungsweg unterbrechen, über den der Befehl geschickt wurde. Auch `set gateway off 300` kann die unmittelbare Antwort unterbrechen; nach Ablauf der Zeit wird aber automatisch reaktiviert, sofern der Controller läuft. Deshalb zunächst vor Ort über USB testen.

## Gemeinsame Solarversorgung

Vorgesehene Nutzerschaltung: **2 × 2.000 mAh LiPo**, fachgerecht als **1S2P-Pack** zusammengeführt (nominell 4.000 mAh), über **einen TP4056 mit Akkuschutz**, LOAD-Ausgang an beide XIAO-**BAT+/BAT−**-Pads. Diese Verschaltung muss elektrisch geprüft werden; für parallelgeschaltete Zellen sind geeignete Zellenauswahl, gleicher Ladezustand vor Zusammenschaltung, Schutz und Leitungssicherung erforderlich. Der TP4056 ist **kein MPPT-Solarregler** und kein Power-Path-Controller. PowerSafe ist **keine Akku-Sicherheitsabschaltung**; Lade- und Entladegrenzen müssen durch Hardware gesichert bleiben. LiPo-Akkus nicht ohne geeignete Maßnahmen unter 0 °C laden.

## Firmware bauen (GitHub Actions)

1. ZIP entpacken und **Inhalt direkt ins Repository-Hauptverzeichnis** hochladen (nicht in `recipe/`!). Die versteckte Datei `.github/workflows/build.yml` muss dabei erhalten bleiben.
2. In GitHub **Actions → Build Meshcore Gateway - Advanced → Run workflow** auswählen.
3. Im Feld `meshcore_version` zunächst **`1.18.0`** angeben.
4. Der Workflow prüft die lokalen Patch-Tests, checkt das offizielle **`repeater-v1.18.0`**-Tag aus, führt Kompatibilitätsprüfungen durch, patcht die UART-/I²C-Konfiguration und kopiert unsere C++-Erweiterung ein, kompiliert per PlatformIO und erzeugt eine **`firmware.uf2`**, **`firmware.bin`** sowie **`build_info.txt`**.
5. Erst nach einem **grünen Compilerlauf** und anschließendem Hardwaretest flashen bzw. in Betrieb nehmen. Bei Build-Fehlern den vollständigen Action-Log prüfen; **niemals die Versionssperre blind entfernen**.

### Upstream-Versionen

Der Workflow nimmt als Eingabe `latest` oder eine feste Version wie `1.18.0` entgegen. `latest` bestimmt den neuesten offiziellen `repeater-v*`-Tag. **Wichtig:** Die Advanced-Erweiterung wurde ausschließlich auf MeshCore **1.18.0** ausgelegt. Ergibt `latest` eine neuere Version (z. B. 1.19.0), bricht der Build **bewusst** ab. Zuerst muss das neue Upstream auf geänderte Radio-/CLI-Schnittstellen geprüft und die Erweiterung angepasst werden. `latest` ist also **kein** Garant für eine automatisch kompatible Advanced-Firmware.

### Empfohlene Testabfolge

1. Erst beide Geräte mit **RAW Meshcore Gateway** auf A ↔ B bidirektional testen.
2. Advanced-Build und Repeaterbetrieb zunächst **mit `powersafe off`** testen, einschließlich RX/TX und Regions.
3. `set gateway off 30` und automatische Rückkehr prüfen; dann `set gateway off` / `set gateway on` und Remote-CLI.
4. `get system.resetreason` vor/nach lokalem CLI-`reboot` und echtem vollständigem Stromausfall vergleichen. Nach Power-Cycle muss die Bridge auf ON zurückkehren; nach Software-Reboot bleibt der zuletzt dauerhaft konfigurierte Zustand erhalten.
5. PowerSafe nur an einer **für BAT geeigneten, strombegrenzten Laborversorgung** testen; ADC-Spannung mit Multimeter vergleichen. Niedrig-/Hochgrenzen, tatsächliches SX1262-Sleep, Wiederanlauf, USB-CLI und UART-Rückkopplungen prüfen.
6. Erst nach mehreren zuverlässigen Wiederanläufen an einem unbeaufsichtigten Solarstandort einsetzen.

## Verzeichnis

```text
.github/workflows/build.yml    GitHub-Actions-Build
platformio.local.ini          Custom-XIAO-Repeater-Konfiguration
scripts/resolve_version.sh    Offiziellen Repeater-Tag auflösen
scripts/check_compat.py       Upstream-Anker prüfen
scripts/apply_special.py      Integration in die offiziellen Quelltexte
overrides/GatewayAdvanced.*   C++-Implementierung der CLI- und PowerSafe-Logik
tests/                        Lokale Build-Rezept- und Patchtests
```

## Quellen und Lizenzen

- [MeshCore – offizielles Repository](https://github.com/meshcore-dev/MeshCore)
- [MeshCore – Repeater-Release v1.18.0](https://github.com/meshcore-dev/MeshCore/releases/tag/repeater-v1.18.0)
- [MeshCore – offizielle CLI-Dokumentation](https://github.com/meshcore-dev/MeshCore/blob/main/docs/cli_commands.md)
- [MeshCore – XIAO-nRF52840-Boarddefinition v1.18.0](https://github.com/meshcore-dev/MeshCore/blob/repeater-v1.18.0/variants/xiao_nrf52/platformio.ini)
- [MeshCore – RS232Bridge v1.18.0](https://github.com/meshcore-dev/MeshCore/blob/repeater-v1.18.0/src/helpers/bridges/RS232Bridge.cpp)
- [MeshCore – CommonCLI v1.18.0](https://github.com/meshcore-dev/MeshCore/blob/repeater-v1.18.0/src/helpers/CommonCLI.cpp)
- [Seeed XIAO nRF52840 – Hardwaredokumentation](https://wiki.seeedstudio.com/XIAO_BLE/)
- [Nordic nRF52840 – Produkt- und Reset-Informationen](https://www.nordicsemi.com/Products/nRF52840)
- [Semtech SX1262 – Produktdaten](https://www.semtech.com/products/wireless-rf/lora-connect/sx1262)

Die MeshCore-Basisfirmware ist unter der **MIT-Lizenz** veröffentlicht; die Lizenzhinweise des Upstream-Projekts müssen bei Weiterverteilungen erhalten bleiben. Für die eigenständigen Projektdateien dieses Rezepts gilt die beigefügte `LICENSE` (MIT). Drittanbieter-Abhängigkeiten haben gegebenenfalls eigene Lizenzen.

## Credits

- **Konzept, Anforderungen, Praxistests und Projektleitung:** Initiator/Betreiber des Repositories.
- **Build-Rezept, Advanced-C++-Erweiterung, Patchtests und Dokumentation:** in Zusammenarbeit mit **ChatGPT von OpenAI (GPT-6)** erarbeitet.
- **MeshCore-Protokoll und Basisfirmware:** [meshcore-dev und alle Mitwirkenden](https://github.com/meshcore-dev/MeshCore).

*Weder MeshCore noch Seeed Studio oder OpenAI bestätigen damit eine offizielle Unterstützung oder eine Hardwarefreigabe für dieses Community-Projekt.*
