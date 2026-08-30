# Legacy-Prototyp

Dieses Verzeichnis enthält Code aus einem früheren Prototyp des Memory-Systems.

Der Prototyp verwendete einen scoring-basierten Memory-Manager sowie eine MCP-Schnittstelle.

Die aktuelle Anwendung wird stattdessen um folgende Prinzipien herum neu aufgebaut:

- kontrollierter Markdown-/Obsidian-Vault
- deterministisches Routing
- thematisch begrenzte Memory-Suche
- modularer Messenger-Adapter
- lokales Sprachmodell nur als optionaler Intent-Fallback

Code aus dem Prototyp wird nur selektiv übernommen und für die aktuelle Architektur unter `src/` refaktoriert.

Die Legacy-Implementierung ist kein Bestandteil des aktuellen Produktivbetriebs.
