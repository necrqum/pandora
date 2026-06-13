# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-06-13

### Added
- **Split-Storage Architecture**: Users can now separate Application Metadata (DB, Salt) from Mass Storage (Blobs). Added support for external disk storage.
- **Cerberus Universal Downloader**: New backend engine using `yt-dlp` for direct web-to-vault streaming from 1,000+ sites.
- **Enhanced Import Flow**: "Confirm Import" modal for rapid categorization and tagging of new media.
- **Metadata Preview**: Automatically fetch suggested titles and thumbnails from URLs before downloading.
- **Smart Setup Flow**: One-click initialization for pre-configured environments (like the test compound).
- **Reset Test Script**: Added `scripts/reset-test.sh` for a clean dev install experience.

### Fixed
- URL import auto-refresh: Files and tags now update instantly in the UI after a download completes.
- SQLAlchemy `DetachedInstanceError` in the categories list.
- Improved path handling to prevent "None" types in storage configuration.

### Changed
- Transitioned internal configuration from plain text to professional `config.json`.
- Updated `requirements.txt` with `yt-dlp`.

## [0.1.1] - 2026-06-12

### Added
- Multi-tag support for media files (backend and frontend).
- Automatic categorization during upload (Video, Image, Document).
- Video duration extraction using `ffprobe` and display in the gallery.
- Tag badges and duration overlays in the frontend gallery.
- `/api/files/{id}/tags` endpoint for bulk tag updates.
- `/api/tags` endpoint to list all available tags.

### Fixed
- Replaced `BaseHTTPMiddleware` with pure ASGI middleware to fix `anyio.EndOfStream` and `anyio.WouldBlock` errors during exception handling and streaming.
- Updated dependencies (`fastapi`, `uvicorn`, `starlette`, `anyio`) to resolve `AttributeError` in `asyncio` on Python 3.12.
- Restored accidentally removed `/api/categories` route.

### Changed
- Database schema updated to include `duration` column in `files` table.
- `generate_thumbnail_from_file` now returns both the thumbnail and the media duration.
- Gallery layout updated with `thumbnail-container` for better information display.