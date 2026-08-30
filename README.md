# Self-Hosted Personal Assistant

Ein datenschutzorientierter, selbst gehosteter persönlicher Assistent mit kontrolliertem Markdown-/Obsidian-Wissensspeicher, lokaler Intent-Erkennung und modularen Integrationen für Messenger, Aufgaben, Erinnerungen, Kalender und Dateiverarbeitung.

## Ziel des Projekts

Der Assistent soll natürliche Sprache verstehen und daraus kontrollierte Aktionen ableiten. Geplant bzw. teilweise bereits umgesetzt sind:

- natürliche deutschsprachige Texteingaben verstehen
- persönliche Notizen speichern und wiederfinden
- Notizen in eine kontrollierte Ordnerstruktur einsortieren
- Einkaufslisten verwalten
- Todo-Listen mit Themenbezug und Prioritäten verwalten
- Erinnerungen erstellen und verwalten
- einen Nextcloud-Kalender über CalDAV lesen und bearbeiten
- Dateien in PDF umwandeln bzw. zusammenführen
- nächtliche Wartungs- und Aufräumjobs ausführen
- ähnliche oder doppelte Notizen konsolidieren
- ein kleines lokales Sprachmodell ausschließlich zur Intent-Erkennung verwenden
- ohne kostenpflichtige externe KI-APIs arbeiten
- persönliche Daten vollständig außerhalb des öffentlichen Repositorys halten

## Architektur

```text
Messenger-Adapter
       |
       v
Personal-Assistant-Core
       |
       +-- Fast Router
       +-- lokaler LLM-Fallback
       +-- Memory Service ------> Markdown / Obsidian Vault
       +-- Shopping Service
       +-- Todo Service
       +-- Reminder Service
       +-- Calendar Service ----> Nextcloud / CalDAV
       +-- File Service
       +-- Job Manager
```

Die Messenger-Schicht ist bewusst vom eigentlichen Assistant-Core getrennt. Dadurch kann der Kommunikationskanal ausgetauscht werden, ohne Memory-, Routing-, Todo- oder Kalenderlogik neu entwickeln zu müssen.

## Messenger-Entscheidung

Ursprünglich war Matrix als bevorzugtes Frontend vorgesehen. Matrix passt sehr gut zum Datenschutz- und Self-Hosting-Ziel des Projekts, da auch die Kommunikationsinfrastruktur selbst betrieben werden kann.

Der Assistant läuft jedoch auf einem gemeinsam genutzten Homelab-Server, auf dem bereits mehrere andere Dienste betrieben werden. Ein zusätzlicher Matrix-Homeserver inklusive Datenbank hätte dauerhaft zusätzlichen RAM-, CPU- und Wartungsbedarf erzeugt. Für die aktuelle Hardware wurde deshalb Discord als ressourcenschonender Messenger-Adapter gewählt.

Das ist eine bewusste Infrastrukturentscheidung und keine feste Abhängigkeit der Anwendung. Die Messenger-Schicht bleibt modular, sodass später beispielsweise ein Matrix-Adapter ergänzt werden kann, ohne den Assistant-Core umzubauen.

### Datenschutz-Trade-off

Discord ist nicht Ende-zu-Ende-verschlüsselt. Für die aktuelle Implementierung wird deshalb nach dem Prinzip der minimalen Berechtigungen gearbeitet:

- eigener Bot-Account statt Automatisierung eines normalen Benutzerkontos
- nur notwendige Bot-Berechtigungen
- User-ID-Whitelist für zugelassene Benutzer
- Bot-Token ausschließlich über lokale Umgebungsvariablen
- keine Veröffentlichung des internen Assistant-Backends
- lokale Verarbeitung durch Fast Router und Ollama
- keine Shell- oder uneingeschränkten Dateisystemrechte für das Sprachmodell

## Intent-Verarbeitung

Einfache und eindeutige Nachrichten sollen ohne KI verarbeitet werden:

```text
"Ich muss noch Mehl kaufen"
        |
        v
Fast Router
        |
        v
shopping_add
```

Nur wenn die Nachricht nicht eindeutig deterministisch erkannt werden kann, wird ein kleines lokales Sprachmodell verwendet:

```text
"Bei Immich wollte ich noch prüfen, ob das Backup sauber läuft"
        |
        v
Fast Router: kein eindeutiger Treffer
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

Das Sprachmodell führt selbst keine Aktionen aus. Es klassifiziert ausschließlich die Eingabe. Erlaubte Aktionen, Scopes und Zielpfade werden anschließend durch normalen Python-Code validiert.

## Memory-Konzept

Obsidian-kompatible Markdown-Dateien bilden die Source of Truth. Die Ordnerstruktur ist kontrolliert; das System darf nicht beliebig neue Verzeichnisse erzeugen.

Unklare Eingaben landen zunächst in einer Inbox. Geplant ist eine nächtliche Verarbeitung, die unter anderem:

- Inbox-Einträge klassifiziert
- ähnliche Notizen erkennt
- Duplikate konsolidiert
- den aktuellen Wissensstand zusammenfasst
- ältere Rohinformationen sicher archiviert
- Suchindizes aktualisiert
- Backups vor Wartungsschritten ausführt

## Ressourcenstrategie

Der Assistant teilt sich den Server mit anderen Homelab-Diensten. Deshalb werden Aufgaben priorisiert:

```text
HIGH
- Messenger
- Kalender / Erinnerungen
- Memory-Suche
- wichtige laufende Dienste

NORMAL
- Memory-Schreibvorgänge
- kleinere Datei- und Paperless-Aufgaben

BACKGROUND
- lokale LLM-Verarbeitung ohne Zeitdruck
- große OCR-Jobs
- Aufräumen / Reindexierung
- nächtliche Konsolidierung
```

Das lokale Sprachmodell soll nur bei Bedarf geladen werden und darf wichtige Dienste nicht verdrängen.

## Datenschutz und Repository-Trennung

Persönliche Daten werden außerhalb dieses Repositorys gespeichert.

Der Pfad zum privaten Obsidian-Vault wird lokal über `VAULT_PATH` konfiguriert. Tokens, Passwörter und produktive Konfigurationsdateien werden nicht versioniert. Dieses Repository enthält ausschließlich Code und anonymisierte Beispieldaten.

## Aktueller Stand

Bereits umgesetzt bzw. im aktuellen Entwicklungsstand vorhanden:

- kontrollierte Routing-Konfiguration
- Obsidian-/Markdown-Vault-Anbindung
- Einkaufsliste
- Todo-Grundfunktionen
- Fast Router für häufige eindeutige Formulierungen
- lokales LLM als Fallback für freie Sprache
- strukturierte Intent-Validierung
- Schutz vor unbekannten Scopes

Als Nächstes:

1. Discord-Adapter
2. Scope-first Memory-Suche
3. Fuzzy Matching und robustere Todo-Erledigung
4. Erinnerungen und Scheduler
5. Nextcloud-CalDAV-Integration
6. nächtliche Inbox-Verarbeitung und Deduplication
7. Job-Priorisierung und ressourcenschonende Wartung
8. sicherer Neustart nur bei tatsächlichem Idle-Zustand
9. PDF- und Paperless-Integration

## Status

Work in Progress. Das Projekt wird schrittweise erweitert, wobei jede neue Funktion zuerst deterministisch abgesichert und anschließend in die natürliche Sprachverarbeitung integriert wird.
