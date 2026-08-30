# Self-Hosted Personal Assistant

A privacy-focused, self-hosted personal assistant with a controlled Markdown/Obsidian knowledge vault, local intent classification and modular integrations for messaging, tasks, reminders and calendar workflows.

## Goals

The assistant is designed to:

- understand natural-language messages
- add and retrieve personal notes
- route notes into a controlled folder structure
- maintain shopping lists and todo lists
- manage reminders
- query a Nextcloud calendar through CalDAV
- convert files to PDF
- perform scheduled maintenance
- use a small local language model for intent classification
- run without paid AI APIs
- keep personal data outside the public repository

## Architecture

```text
Messenger Adapter
       |
       v
Personal Assistant Core
       |
       +-- Fast Intent Router
       +-- Local LLM Fallback
       +-- Memory Service ------> Markdown / Obsidian Vault
       +-- Shopping Service
       +-- Todo Service
       +-- Reminder Service
       +-- Calendar Service ----> Nextcloud / CalDAV
       +-- File Service
       +-- Job Manager
```

The messaging layer is intentionally separated from the assistant core. This allows the conversational interface to be replaced without changing the memory, task or routing logic.

## Messenger Design Decision

Matrix was initially planned as the preferred messaging frontend because it can be self-hosted and fits the privacy goals of the project very well.

The assistant, however, runs on a shared homelab server together with several other services. Running an additional Matrix homeserver and database would add permanent RAM, CPU and maintenance overhead to an already resource-constrained host. For this reason, Discord was selected as the lightweight messaging frontend for the current deployment.

This is a deliberate infrastructure trade-off rather than an architectural limitation: the messenger is implemented as an adapter, so a future Matrix integration can be added without redesigning the assistant core.

## Privacy

Personal data is stored outside this repository.

The application receives the location of the user's vault through the `VAULT_PATH` environment variable. Secrets and real configuration files are excluded from version control, and this repository contains only example data.

The local language model is used only for intent classification and does not receive unrestricted shell or filesystem access. Application code validates allowed actions and scopes before modifying data.

## Status

Work in progress. The core routing, local intent parsing, shopping-list handling and todo handling are being developed first. Additional integrations such as reminders, calendar access, maintenance jobs and messenger adapters are added incrementally.
