# Project Error Tracking

## Persistent Build/Release Issues (v0.2.x)

### 1. AttributeError: 'NoneType' object has no attribute 'name'
- **Location**: `pandora/backend/main.py` in `list_tags` or `list_categories`.
- **Status**: Potential fix applied (guards added), but still appearing in logs.
- **Hypothesis**: The ORM might be returning a list containing `None` if the database state is inconsistent, or a relationship is not correctly loaded when accessed via a bundled PyInstaller binary.

### 2. GitHub Actions / PyInstaller Build Failure
- **Symptoms**: Release workflow fails (Red X) and binaries are not published.
- **Current Findings**:
    - PyInstaller may have trouble resolving static asset paths (`frontend/`).
    - Hidden imports (`uvicorn`, `fastapi`, `sqlalchemy`, `sqlcipher3-binary`) were initially missing.
    - Possible dependency conflict or missing system library (`libsqlcipher`) on the GitHub Ubuntu runner.
- **Tasks for Future fixing**:
    - [ ] Debug the PyInstaller data mapping (`--add-data`).
    - [ ] Verify `sqlcipher3-binary` installation on fresh environments.
    - [ ] Implement more verbose logging in the build workflow to capture the exact failure point.
    - [ ] Consider using a Docker-based build if PyInstaller remains unstable.

## Known Limitations
- URL import requires a stable network connection for `yt-dlp`.
- Multi-library storage management is limited to one config and one blob directory (for now).
