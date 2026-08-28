# Self-Hosted Personal Assistant

A privacy-focused, self-hosted personal assistant using Telegram as a conversational interface and an Obsidian-compatible Markdown vault as its personal knowledge store.

## Goals

The assistant can:

- understand natural-language messages
- add and retrieve personal notes
- route notes into a controlled folder structure
- maintain shopping lists
- maintain todo lists
- manage reminders
- query a Nextcloud calendar
- convert files to PDF
- perform scheduled maintenance
- use a small local language model for intent classification
- run without paid AI APIs

## Architecture

Telegram
    |
    v
Personal Assistant
    |
    +-- Intent Router
    +-- Memory Service ------> Markdown / Obsidian Vault
    +-- Shopping Service
    +-- Todo Service
    +-- Reminder Service
    +-- Calendar Service ----> Nextcloud / CalDAV
    +-- File Service
    +-- Job Manager
    |
    v
Local LLM

## Privacy

Personal data is stored outside this repository.

The application receives the location of the user's vault through the `VAULT_PATH` environment variable.

This repository contains only example data.

## Status

Work in progress.
