# Pandora

A self-hosted, fully encrypted media organizer built with Python and FastAPI.

Pandora acts as a "Pandora's Box" - a completely separate, safe environment for your media. Both the media files and the SQLite database are encrypted at rest. Media is streamed directly to your browser in-memory, ensuring no decrypted traces are left on your hard drive.

## Features

- **Zero-Knowledge Architecture**: Files and database are encrypted using AES-256-GCM. The encryption key is derived from your master password and never stored locally.
- **Stealth Mode**: A decoy login screen protects the vault.
- **In-Memory Streaming**: Media is never decrypted to a temporary file; it flows directly from encrypted storage to the player.
- **Modular Scrapers**: Easily plug in custom scrapers to automatically label your media.

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Running the App

```bash
pandora
```
