# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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