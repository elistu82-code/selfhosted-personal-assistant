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

Auf der aktuellen Homelab-Hardware ist die lokale LLM-Inferenz bewusst stark ressourcenlimitiert. Der LLM-Pfad ist deshalb als experimenteller Fallback gedacht; deterministische Funktionen bleiben davon unabhängig.

## Memory-Konzept

Obsidian-kompatible Markdown-Dateien bilden die Source of Truth. Die Ordnerstruktur ist kontrolliert; das System darf nicht beliebig neue Verzeichnisse erzeugen.

### Scope-first Memory

Die nächste Kernfunktion ist eine Scope-first-Suche. Wird beispielsweise nach `Immich` gefragt, durchsucht der Assistant zuerst ausschließlich den registrierten Immich-Bereich und nicht den gesamten Vault.

```text
"Was hatte ich zu Immich notiert?"
        |
        v
Scope-Erkennung: immich
        |
        v
20_Homelab/Immich/
        |
        v
lokale Suche und Ranking
```

Das reduziert unnötige Suchräume, verhindert Vermischungen zwischen Themen und bildet die Grundlage für spätere Zusammenfassungen.

### Geplante Nachtjobs

Nach der Scope-first-Suche wird eine nächtliche Wartungspipeline umgesetzt. Sie soll nur Hintergrundarbeiten übernehmen und wichtige Serverdienste nicht verdrängen.

Geplant sind:

- Inbox-Einträge prüfen und nach Möglichkeit vorhandenen Scopes zuordnen
- ähnliche oder doppelte Notizen erkennen
- Duplikat-Kandidaten zusammenführen bzw. konsolidieren
- aktuelle Themenstände zusammenfassen
- Rohinformationen bzw. ältere Versionen sicher erhalten oder archivieren
- Suchindizes aktualisieren
- Wartungsprotokolle schreiben
- Backups vor schreibenden Wartungsschritten berücksichtigen
- Hintergrundjobs mit niedriger Priorität ausführen

Ein automatischer Neustart des Servers ist erst vorgesehen, wenn zuverlässige Idle-Prüfungen für laufende Streams, Schreibvorgänge und andere wichtige Jobs vorhanden sind.

## Ressourcenstrategie

Der Assistant teilt sich den Server mit anderen Homelab-Diensten. Deshalb werden Aufgaben priorisiert:

```text
HIGH
- Messenger
- spätere Kalender- / Erinnerungsfunktionen
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
- lokales LLM als experimenteller Fallback für freie Sprache
- strukturierte Intent-Validierung
- Schutz vor unbekannten Scopes
- Discord als aktueller Messenger-Adapter in der laufenden Entwicklung

### Aktuelle Entwicklungspriorität

1. Scope-first Memory-Suche fertigstellen
2. nächtliche Wartungs-, Inbox- und Konsolidierungsjobs als funktionsfähigen Prototyp umsetzen
3. Projektstand dokumentieren und als reproduzierbare Demo stabilisieren

### Später geplante Erweiterungen

Diese Funktionen gehören weiterhin zum Zielbild, werden aber erst nach dem aktuellen Portfolio-Milestone umgesetzt:

- robustere Todo-Erledigung und erweitertes Fuzzy Matching
- Erinnerungen und Scheduler
- Nextcloud-CalDAV-Integration zum Lesen und Schreiben von Kalendereinträgen
- Datei- und PDF-Funktionen, einschließlich Konvertieren und Zusammenführen
- Paperless-ngx-Integration
- erweiterter Job Manager mit HIGH/NORMAL/BACKGROUND-Prioritäten
- sichere Idle-Prüfung und optionaler kontrollierter Nacht-Neustart
- optionaler Matrix-Adapter als stärker selbst gehostete Messenger-Alternative

## Status

Work in Progress. Der aktuelle Portfolio-Milestone konzentriert sich bewusst auf die Kernarchitektur: Discord als Messenger-Adapter, kontrolliertes Routing, lokales LLM als Fallback, Scope-first Memory sowie eine ressourcenschonende nächtliche Wartungspipeline. Weitere Integrationen sind dokumentiert und für spätere Ausbaustufen vorgesehen.
