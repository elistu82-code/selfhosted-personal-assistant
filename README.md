# Self-Hosted Personal Assistant

Ein persönlicher Assistent für mein Homelab. Ziel des Projekts ist es, Notizen, Aufgaben und einfache Alltagsfunktionen über einen Messenger zu verwalten und dabei möglichst viel lokal zu verarbeiten.

Der aktuelle Stand ist ein funktionsfähiger Prototyp. Discord dient als Oberfläche, die eigentliche Verarbeitung läuft auf dem Server in Python. Persönliche Daten liegen in einem privaten Obsidian-/Markdown-Vault und werden nicht im öffentlichen Repository gespeichert.

## Aktueller Stand

Umgesetzt sind aktuell:

- Discord-Bot mit User- und Channel-Whitelist
- Betrieb als `systemd`-Service
- Fast Router für eindeutige Nachrichten ohne LLM
- lokaler Ollama-Fallback für freie bzw. mehrdeutige Eingaben
- Einkaufsliste und Todo-Grundfunktionen
- Schreiben in einen kontrollierten Obsidian-/Markdown-Vault
- Scope-first Memory-Suche
- nächtlicher Wartungsjob mit Indexierung, Inbox-Analyse und Duplikaterkennung
- automatischer Start des Nachtjobs über einen `systemd`-Timer

Die wichtigsten Funktionen arbeiten ohne Sprachmodell. Das betrifft zum Beispiel Einkaufsliste, Todos und Memory-Suche. Dadurch reagieren diese Funktionen schnell und bleiben auch dann nutzbar, wenn das lokale Modell langsam ist.

## Umsetzung

Eingehende Nachrichten werden zuerst durch normale Python-Regeln geprüft. Typische Formulierungen können dadurch direkt einem Intent wie `shopping_add`, `todo_add` oder `memory_search` zugeordnet werden.

Nur wenn keine eindeutige Regel greift, wird ein kleines Modell über Ollama verwendet. Das Modell darf keine Aktionen selbst ausführen, sondern liefert lediglich eine strukturierte Klassifikation zurück. Die eigentliche Aktion wird anschließend wieder durch Python-Code geprüft und ausgeführt.

Das lokale Modell ist auf der aktuellen Hardware bewusst stark ressourcenbegrenzt. Die Inferenz ist deshalb deutlich langsamer als das deterministische Routing. Für den praktischen Betrieb ist Ollama aktuell eher ein experimenteller Fallback als der zentrale Bestandteil des Systems.

Die Memory-Funktionen verwenden einen Obsidian-kompatiblen Markdown-Vault. Ordner und Themenbereiche werden über eine Routing-Konfiguration vorgegeben. Der Bot erzeugt nicht beliebig neue Verzeichnisse. Wenn ein Ziel nicht eindeutig zugeordnet werden kann, ist eine Inbox als Fallback vorgesehen.

Bei der Suche wird zuerst der erkannte Themenbereich verwendet. Eine Anfrage zu Immich durchsucht also zunächst nur den registrierten Immich-Bereich und nicht den gesamten Vault. Die Suche selbst läuft lokal ohne LLM.

## Nächtliche Wartung

Der Nachtjob läuft separat vom Discord-Bot. Er scannt die Markdown-Dateien, erstellt einen JSON-Index, prüft die Inbox auf erkennbare Themenbereiche und sucht nach exakten sowie ähnlichen Einträgen. Anschließend wird ein Markdown-Report erzeugt und der Lauf über `journald` protokolliert.

Die Wartung ist derzeit absichtlich nicht destruktiv. Es werden keine Notizen automatisch gelöscht, verschoben oder zusammengeführt. Der Job liefert nur Kandidaten und Auswertungen. So kann die Logik getestet werden, ohne den produktiven Vault unnötig zu verändern.

Der Timer und die Services liegen als Beispiel unter `deploy/systemd/`.

## Warum Discord und nicht Matrix?

Ursprünglich sollte der Assistent über Matrix laufen. Das hätte besser zum Self-Hosting-Ansatz gepasst, weil auch der Messenger vollständig auf eigener Infrastruktur betrieben werden könnte.

Der Server wird allerdings bereits für mehrere andere Homelab-Dienste genutzt. Ein zusätzlicher Matrix-Homeserver mit Datenbank hätte dauerhaft weitere Ressourcen und zusätzlichen Wartungsaufwand benötigt. Für die aktuelle Hardware habe ich deshalb Discord als einfacheren und deutlich leichteren Messenger-Adapter gewählt.

Die Entscheidung ist nicht endgültig. Die Messenger-Anbindung ist vom restlichen Code getrennt, sodass später ein Matrix-Adapter ergänzt oder Discord ersetzt werden kann.

Discord ist dabei ein bewusster Kompromiss beim Datenschutz. Der Bot läuft mit möglichst wenigen Berechtigungen, akzeptiert nur freigegebene User- und Channel-IDs und benötigt keine zusätzlichen öffentlich erreichbaren Ports auf dem Server. Tokens und produktive IDs liegen ausschließlich in lokalen Umgebungsvariablen.

## Datenschutz

Der öffentliche Code enthält keine persönlichen Notizen und keine produktiven Zugangsdaten. Der Pfad zum privaten Vault wird lokal über `VAULT_PATH` gesetzt. `.env`, Bot-Tokens, Discord-IDs, die produktive Routing-Konfiguration und der eigentliche Obsidian-Vault werden nicht versioniert.

## Geplant

Als nächstes soll der Nachtjob um einen sicheren Idle-Check erweitert werden. Ein Server-Neustart darf nur stattfinden, wenn keine wichtigen Streams, Schreibvorgänge oder anderen Jobs laufen.

Danach sind vor allem Erinnerungen und ein Scheduler, Nextcloud-CalDAV für Kalenderzugriff, PDF- und Dateiwerkzeuge sowie eine spätere Paperless-ngx-Integration geplant. Die Duplikaterkennung soll außerdem zu einer kontrollierten Memory-Konsolidierung ausgebaut werden. Wenn später mehr Hardware zur Verfügung steht, ist Matrix weiterhin als möglicher Messenger vorgesehen.

## Status

Work in Progress. Der aktuelle Stand konzentriert sich auf einen kleinen, nachvollziehbaren Kern: Messenger-Anbindung, deterministisches Routing, lokale Memory-Funktionen und eine getrennte nächtliche Wartung.