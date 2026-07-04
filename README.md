# Pandora

![Pandora](https://img.shields.io/badge/Status-Active-brightgreen.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Framework-teal.svg)

A self-hosted, fully encrypted media organizer built with Python and FastAPI.

Pandora acts as a "Pandora's Box" — a completely separate, safe environment for your media. Both the media files and the SQLite database are encrypted at rest. Media is streamed directly to your browser in-memory, ensuring no decrypted traces are left on your hard drive.

## ✨ Features

- **Zero-Knowledge Architecture**: Files are encrypted using AES-256-GCM and SQLite data is protected by SQLCipher. The encryption key is derived from your master password and never stored locally.
- **Split-Storage Architecture**: A professionalized storage system that separates "Application Metadata" (DB, Keys, Logs) from "Mass Storage" (Encrypted Media). This allows you to store your heavy video files on an **external disk** while keeping the app configuration on your main drive.
- **Cerberus Universal Downloader**: Directly download and encrypt media from **1,000+ sites** (YouTube, Erome, xhamster, etc.). This infrastructure is powered by our sister project [Cerberus](https://github.com/necrqum/cerberus), integrating robust `yt-dlp` capabilities directly into the vault.
- **Zero-Footprint URL Import**: Downloaded content is streamed directly from the web into the encrypted vault without ever touching your disk in an unencrypted state.
- **Quick-Tagging Import Modal**: A streamlined UI flow that allows you to edit titles, select categories, and apply tags *before* the file is encrypted and stored.
- **Privacy First**: IP addresses and personally identifiable traces are logged as cryptographic hashes, ensuring maximum operational security.
- **Stealth Mode**: A decoy login screen protects the vault.
- **In-Memory Streaming**: Media is never decrypted to a temporary file; it flows directly from encrypted storage to the player with 4MB chunking for optimized seeking.
- **Intelligent Thumbnails**: A secure backend pipeline instantly extracts zero-footprint thumbnails for your videos and images.
- **Offline Mass Importer**: A dedicated offline Python script (`pandora_importer.py`) allows you to seamlessly mass-import gigabytes of files with zero freezing or DB concurrency locking, directly utilizing the core encryption modules.

---

## 🔍 Advanced Search & Filtering

Pandora includes a powerful search bar that allows complex queries using specific prefixes and exclusionary syntax.

**Supported Prefixes:**
- `name:` Filter by filename
- `tag:` Filter by tags
- `cat:` Filter by category
- `artist:` Filter by artist / uploader
- `site:` Filter by origin site (e.g., youtube)
- `favorite:true` or `favorite:false` Filter by favorite status

**Syntax Examples:**
- `tag:milf -tag:amateur` (Find files tagged 'milf' but EXCLUDE those tagged 'amateur')
- `cat:video artist:"John Doe"` (Find videos uploaded by "John Doe" using quotes for spaces)
- `-name:test` (Exclude files with "test" in their name)

---

## 🚀 Installation Guide

There are two ways to run Pandora: using the standalone executable (easiest) or running from source.

### Option A: Standalone Executable (Recommended)

If you just want to run Pandora without installing Python or dealing with environments:
1. Go to the **[Releases](../../releases)** page.
2. Download the executable for your operating system (`pandora.exe` for Windows, `pandora-linux` for Linux).
3. Place the executable in a dedicated folder.
4. Double-click or run the executable from your terminal. The server will start automatically at `http://127.0.0.1:8000`.

### Option B: Install from Source

If you want to modify the code, use the Mass Importer script, or prefer running it via Python:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/necrqum/pandora.git
   cd pandora
   ```
2. **Create and activate a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   # On Windows: venv\Scripts\activate
   # On Linux/macOS: source venv/bin/activate
   ```
3. **Install dependencies and the app:**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```
4. **Run the server:**
   ```bash
   pandora
   ```

### 📦 Using the Offline Mass Importer

If you have hundreds of files (gigabytes of data) to import at once, it is highly recommended to use the **Offline Mass Importer**. This standalone script bypasses the web server to encrypt and import files completely synchronously, completely avoiding system freezing or DB lock issues.

1. Ensure the Pandora web server is **shut down**.
2. Run the importer:
   ```bash
   python pandora_importer.py
   ```
3. Enter your Master Password.
4. Add your folders/files, select tags, and click **START MASS IMPORT**.

---

## 🔄 Updating Guide

### Updating the Standalone Executable
1. Download the latest release from the [Releases](../../releases) tab.
2. Replace your old executable file with the new one.
3. Restart the server. Your vault and database will remain perfectly intact.

### Updating from Source
If you installed Pandora using Git, you can update it with these simple commands:

```bash
# 1. Pull the latest code
git pull origin master

# 2. Activate your virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# 3. Re-install in case there are new dependencies
pip install -r requirements.txt
pip install -e .
```

---

## 🛠️ Contributing

Contributions are welcome! Please check out our [Contributing Guidelines](CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
