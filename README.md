# Self-Hosted Personal Assistant

Ein datenschutzorientierter, selbst gehosteter persönlicher Assistent mit kontrolliertem Markdown-/Obsidian-Wissensspeicher, deterministischem Fast Routing, lokalem LLM-Fallback und nächtlicher Wartungspipeline.

Das Projekt ist als modularer Homelab-Assistent aufgebaut. Häufige und sicher erkennbare Aktionen werden ohne KI ausgeführt. Freie Sprache kann optional durch ein lokal betriebenes Sprachmodell klassifiziert werden. Persönliche Daten bleiben außerhalb des öffentlichen Repositorys.

## Ziel des Projekts

Der Assistent soll alltägliche Informationen, Aufgaben und Dateien über einen Messenger verwalten können, ohne dafür von kostenpflichtigen externen KI-APIs abhängig zu sein.

Das Zielbild umfasst unter anderem:

- natürliche deutschsprachige Texteingaben
- persönliche Notizen in einem Obsidian-/Markdown-Vault
- kontrollierte thematische Zuordnung über Scopes
- Scope-first Memory-Suche
- Einkaufslisten
- Todo-Listen mit Themenbezug und Prioritäten
- Erinnerungen und Scheduler
- Nextcloud-Kalender über CalDAV
- Datei- und PDF-Verarbeitung
- Paperless-ngx-Integration
- nächtliche Wartung, Indexierung und Duplikaterkennung
- optionales lokales Sprachmodell für mehrdeutige Eingaben
- kontrollierte Hintergrundjobs mit niedriger Priorität
- später optional ein sicherer nächtlicher Server-Neustart nach Idle-Prüfung

## Aufbau

Der Bot läuft aktuell über Discord. Eingehende Nachrichten werden zuerst mit normalen Python-Regeln geprüft. Wenn eine Nachricht dort nicht eindeutig erkannt wird, kann als Fallback das lokale Ollama-Modell verwendet werden. Die erkannte Aktion wird anschließend wieder von normalem Python-Code ausgeführt.

Die wichtigsten Teile des Projekts sind aktuell:

- `src/adapters/discord.py` für die Verbindung zu Discord
- `src/core.py` als zentrale Verarbeitung einer Nachricht
- `src/bot/fast_router.py` für schnelle, eindeutige Befehle ohne LLM
- `src/llm/intent_parser.py` für den optionalen Ollama-Fallback
- `src/tasks/` für Einkaufsliste und Todos
- `src/memory/` für Schreiben, Routing und Suche im Obsidian-Vault
- `src/jobs/nightly.py` für die nächtliche Wartung

Die Messenger-Anbindung ist vom Rest getrennt. Dadurch kann später beispielsweise Discord durch Matrix ergänzt oder ersetzt werden, ohne die Memory- oder Todo-Funktionen neu bauen zu müssen.

## Warum aktuell Discord statt Matrix?

Ursprünglich war **Matrix** als bevorzugtes Frontend vorgesehen. Matrix passt besser zum Self-Hosting- und Datenschutz-Ziel, weil auch die Kommunikationsinfrastruktur selbst betrieben werden kann.

Der Assistant läuft jedoch auf einem gemeinsam genutzten Homelab-Server, auf dem bereits weitere Dienste betrieben werden. Ein zusätzlicher Matrix-Homeserver inklusive Datenbank würde dauerhaft zusätzlichen RAM-, CPU- und Wartungsbedarf verursachen.

Für die aktuelle Hardware wurde deshalb **Discord als ressourcenschonender Messenger-Adapter** gewählt.

Das ist eine bewusste Infrastrukturentscheidung und keine feste Abhängigkeit der Anwendung. Der Assistant-Core bleibt messengerunabhängig. Ein Matrix-Adapter ist weiterhin als spätere Erweiterung vorgesehen.

### Datenschutz-Trade-off

Discord ist nicht Ende-zu-Ende-verschlüsselt. Deshalb wird die aktuelle Integration möglichst restriktiv betrieben:

- eigener Bot-Account
- minimale Bot-Berechtigungen
- User-ID-Whitelist
- Channel-ID-Whitelist
- Bot-Token ausschließlich über lokale Umgebungsvariablen
- keine Veröffentlichung eines internen Assistant-Backends
- lokale Verarbeitung durch Fast Router und Ollama
- keine Shell-Rechte für das Sprachmodell
- kein uneingeschränkter Dateisystemzugriff durch das LLM

Der Discord-Bot läuft als eigener `systemd`-Service und verbindet sich ausschließlich ausgehend mit Discord. Für den Bot selbst müssen keine zusätzlichen öffentlichen Ports geöffnet werden.

## Intent-Verarbeitung

Der Assistant verwendet bewusst eine Hybrid-Architektur.

### 1. Fast Router

Häufige und eindeutige Nachrichten werden deterministisch in Python erkannt.

```text
"Ich muss noch Mehl kaufen"
        |
        v
Fast Router
        |
        v
shopping_add
        |
        v
Intent Executor
```

Vorteile:

- sehr geringe Latenz
- keine LLM-Inferenz erforderlich
- vorhersehbares Verhalten
- geringer Ressourcenverbrauch
- sicherer für schreibende Aktionen

### 2. Lokaler LLM-Fallback

Nur wenn keine sichere deterministische Regel greift, kann ein kleines lokales Modell über Ollama verwendet werden.

```text
freie / mehrdeutige Eingabe
        |
        v
Fast Router: kein Treffer
        |
        v
lokales LLM
        |
        v
strukturiertes Intent-Objekt
        |
        v
Python-Validierung
        |
        v
kontrollierte Aktion
```

Das Sprachmodell führt selbst keine Aktionen aus. Es klassifiziert ausschließlich Eingaben. Erlaubte Intents, Scopes und Zielpfade werden anschließend durch normalen Python-Code validiert.

Aktuell wird ein sehr kleines lokales Modell verwendet. Auf der vorhandenen Homelab-Hardware ist die Inferenz bewusst stark CPU- und RAM-limitiert. Dadurch kann die LLM-Verarbeitung deutlich langsamer sein als der Fast Router. Der LLM-Pfad ist deshalb aktuell ein **experimenteller Fallback** und nicht Voraussetzung für die Kernfunktionen.

Es werden keine kostenpflichtigen externen KI-APIs benötigt.

## Memory-Konzept

Obsidian-kompatible Markdown-Dateien bilden die Source of Truth.

Die Ordnerstruktur ist kontrolliert. Der Assistant darf nicht beliebig neue Ordner erzeugen. Neue Inhalte werden nur in registrierte Scopes geschrieben. Ist kein eindeutiger Scope vorhanden oder ein Zielordner nicht verfügbar, dient eine Inbox als sicherer Fallback.

### Beispiel

```text
"Bei Immich benötigt Machine Learning viel RAM"
        |
        v
Scope: immich
        |
        v
registrierter Immich-Pfad
        |
        v
Notes.md
```

## Scope-first Memory-Suche

Die Scope-first-Suche ist umgesetzt.

Statt bei jeder Anfrage den gesamten Vault zu durchsuchen, wird zuerst der thematische Bereich erkannt und die Suche auf diesen Scope begrenzt.

```text
"Was habe ich bei Immich über RAM notiert?"
        |
        v
Fast Router
        |
        v
memory_search
        |
        v
Scope: immich
        |
        v
nur registrierter Immich-Bereich
        |
        v
lokale Suche + Ranking
```

Die Suche arbeitet ohne LLM und antwortet dadurch sehr schnell.

Unterstützt werden unter anderem:

```text
was weiß ich über immich
was habe ich bei immich über ram notiert
/search immich machine learning
```

Die Suche verwendet:

- exakte Scope-Erkennung
- Fuzzy-Scope-Erkennung
- lokale Markdown-Suche
- einfache Ähnlichkeitsbewertung
- Begrenzung auf registrierte Vault-Pfade

## Nightly Maintenance

Eine erste nicht-destruktive nächtliche Wartungspipeline ist umgesetzt.

Sie wird als separater `systemd`-Oneshot-Service über einen `systemd`-Timer gestartet. Der Job läuft mit niedriger Prozess- und I/O-Priorität, damit andere Homelab-Dienste bevorzugt werden.

Aktuelle Aufgaben:

- Markdown-Dateien im Vault scannen
- Memory-Index als JSON aktualisieren
- Inbox auf eindeutig erkennbare Scope-Kandidaten prüfen
- exakte Duplikate erkennen
- ähnliche Einträge innerhalb von Dateien erkennen
- Wartungsreport als Markdown erzeugen
- Lauf über `journald` protokollieren

### Ablauf

```text
systemd timer
     |
     v
nightly maintenance
     |
     +--> Vault scannen
     +--> Index aktualisieren
     +--> Inbox analysieren
     +--> Duplikate erkennen
     +--> Ähnlichkeiten prüfen
     +--> Report schreiben
```

Die aktuelle Version ist bewusst **nicht-destruktiv**:

- keine automatische Löschung
- kein automatisches Verschieben von Notizen
- keine automatische Zusammenführung von Duplikaten
- kein automatischer Server-Neustart

Damit kann die Wartung analysieren und Kandidaten melden, ohne persönliche Daten versehentlich zu verändern.

## systemd-Deployment

Der laufende Assistant und der Nachtjob werden unabhängig voneinander betrieben.

```text
personal-assistant.service
    -> Discord Adapter
    -> dauerhaft aktiv

personal-assistant-nightly.timer
    -> startet nachts

personal-assistant-nightly.service
    -> Index / Inbox / Duplikate / Report
    -> beendet sich nach erfolgreichem Lauf
```

Beispielkonfigurationen befinden sich unter `deploy/systemd/`.

## Ressourcenstrategie

Der Assistant teilt sich die Hardware mit anderen Homelab-Diensten. Deshalb ist das System auf kontrollierten Ressourcenverbrauch ausgelegt.

```text
HIGH
- Messenger
- Scope-first Memory Search
- spätere Kalender- und Erinnerungsfunktionen
- wichtige laufende Homelab-Dienste

NORMAL
- Memory-Schreibvorgänge
- kleinere Dateioperationen
- leichte Paperless-Aufgaben

BACKGROUND
- lokales LLM ohne Zeitdruck
- Inbox-Analyse
- Reindexierung
- Duplikaterkennung
- größere OCR-Jobs
- nächtliche Wartung
```

Das lokale LLM wird über systemd ressourcenbegrenzt und soll andere Dienste nicht verdrängen.

## Datenschutz und Repository-Trennung

Persönliche Daten werden nicht im öffentlichen Repository gespeichert.

Der produktive Vault wird lokal über `VAULT_PATH` konfiguriert. Ebenso bleiben produktive Routing-Konfigurationen und Zugangsdaten lokal.

Nicht versioniert werden insbesondere:

- `.env`
- Bot-Tokens
- persönliche Discord-IDs
- produktive Routing-Konfiguration
- persönlicher Obsidian-Vault
- private Notizen und Memory-Indizes

Das Repository enthält ausschließlich Code, Beispielkonfigurationen und anonymisierte Demo-Daten.

## Aktueller Stand

| Funktion | Status |
|---|---|
| Discord Messenger Adapter | ✅ umgesetzt |
| Betrieb als systemd-Service | ✅ umgesetzt |
| Fast Router | ✅ umgesetzt |
| lokaler Ollama-LLM-Fallback | ✅ experimentell |
| strukturierte Intent-Verarbeitung | ✅ umgesetzt |
| kontrollierte Scope-Konfiguration | ✅ umgesetzt |
| Obsidian-/Markdown-Vault-Anbindung | ✅ umgesetzt |
| Memory Write | ✅ umgesetzt |
| Scope-first Memory Search | ✅ umgesetzt |
| Einkaufsliste | ✅ umgesetzt |
| Todo-Grundfunktionen | ✅ umgesetzt |
| Memory-Index | ✅ umgesetzt |
| Inbox-Analyse | ✅ umgesetzt |
| exakte Duplikaterkennung | ✅ umgesetzt |
| Near-Duplicate-Erkennung | ✅ Prototyp |
| Nightly Maintenance Report | ✅ umgesetzt |
| systemd-Nacht-Timer | ✅ umgesetzt |
| automatisches Konsolidieren | 🟡 geplant |
| sicherer nächtlicher Neustart | 🟡 geplant |
| Erinnerungen / Scheduler | 🟡 geplant |
| Nextcloud CalDAV | 🟡 geplant |
| PDF- und Dateiwerkzeuge | 🟡 geplant |
| Paperless-ngx | 🟡 geplant |
| Matrix Adapter | 🟡 optional / später |

## Nächste Schritte

### 1. Sicherer Nacht-Neustart

Der Nachtjob soll später optional einen kontrollierten Server-Neustart auslösen können. Ein einfacher zeitgesteuerter `reboot` ist ausdrücklich nicht vorgesehen.

Vor einem Neustart sollen mindestens folgende Bedingungen geprüft werden:

- keine aktiven Jellyfin-Streams
- keine kritischen Datei-Schreibvorgänge
- keine laufenden wichtigen Assistant-Jobs
- keine aktiven Import-/Download-Prozesse, sofern relevant
- Wartungsjob erfolgreich abgeschlossen

Nur bei eindeutigem Idle-Zustand darf ein Neustart erfolgen. Andernfalls wird der Neustart übersprungen und protokolliert.

### 2. Automatische Memory-Konsolidierung

Die bestehende Duplikaterkennung soll erweitert werden um:

- robustere Near-Duplicate-Erkennung
- Zusammenfassung mehrerer ähnlicher Notizen
- sichere Archivierung alter Rohinformationen
- optional Review-Workflow vor schreibenden Änderungen
- automatische Verarbeitung geeigneter Inbox-Einträge

### 3. Erinnerungen und Scheduler

Geplant sind deterministische Befehle für Erinnerungen, beispielsweise:

```text
/remind 18:00 Müll rausbringen
/remind tomorrow 09:00 Termin prüfen
```

Diese Funktionen sollen ohne LLM funktionieren und über einen Scheduler ausgeführt werden.

### 4. Nextcloud Calendar / CalDAV

Der Assistant soll einen privaten Nextcloud-Kalender lesen und schreiben können.

Geplant sind unter anderem:

```text
/today
/calendar
/event 03.09.2026 15:30 Zahnarzt
```

Die CalDAV-Integration soll unabhängig vom LLM arbeiten, damit Kalenderoperationen schnell und deterministisch bleiben.

### 5. PDF- und Dateiwerkzeuge

Geplant sind Messenger-Workflows für:

- Bilder zu PDF
- mehrere PDFs zusammenführen
- einfache Dateikonvertierungen
- Dateien über den Messenger empfangen und zurückgeben

### 6. Paperless-ngx

Später soll Paperless-ngx als Dokumentenarchiv angebunden werden. Denkbar sind Upload, Suche und einfache Dokumenten-Workflows.

### 7. Erweiterter Job Manager

Langfristig sollen Hintergrundaufgaben explizit nach Priorität geplant werden:

- `HIGH`
- `NORMAL`
- `BACKGROUND`

Damit sollen rechenintensive Jobs nur dann laufen, wenn ausreichend Ressourcen vorhanden sind.

### 8. Optionaler Matrix-Adapter

Wenn später mehr Hardware-Ressourcen zur Verfügung stehen oder die Kommunikationsinfrastruktur auf einen separaten Host ausgelagert wird, kann Discord durch Matrix ergänzt oder ersetzt werden.

Die bestehende Adapter-Architektur ist genau für diesen Austausch vorgesehen.

## Projektstatus

**Work in Progress / Portfolio Prototype**

Der aktuelle Stand demonstriert bereits die Kernarchitektur des Projekts:

- modularer Messenger-Adapter
- deterministisches Routing
- lokales LLM als optionaler Fallback
- kontrollierte Obsidian-/Markdown-Persistenz
- schnelle Scope-first Memory-Suche
- getrennte Hintergrundwartung
- Linux-/systemd-Deployment
- Ressourcen- und Sicherheitsgrenzen für lokale KI

Der nächste technische Schwerpunkt liegt auf sicherer Automatisierung im Hintergrund. Kalender, Erinnerungen, PDF-Workflows, Paperless und ein optionaler Matrix-Adapter sind bewusst als weitere Ausbaustufen dokumentiert.