# Home Cloud Drive Development Report

## Latest Updates (Apr 8, 2026)

### File version history and storage visibility
- Added full per-file version history with backend persistence in `file_versions` and a `version` field on file records.
- Shipped version endpoints to list history, upload a new version, download an older version, restore an older version as the new latest copy, and delete non-current versions.
- Added a frontend Version History modal plus details/context-menu entry points for version operations.
- Updated storage accounting so archived versions count toward quota usage and appear in the storage breakdown.
- Added startup migration support for the `files.version` column and the unique `(file_id, version)` index, plus lazy base-version backfill for legacy files.

---

## Latest Updates (Apr 3, 2026)

### Authentication and email delivery
- Switched password reset and account email delivery from SMTP-style configuration to the Resend API.
- Added clearer backend error messages when password reset email delivery is unavailable or incomplete.
- Wired `RESEND_*`, `PASSWORD_RESET_URL`, and `PASSWORD_RESET_EXPIRE_MINUTES` through the root Docker Compose deployment.
- Updated the frontend auth flow to support the dedicated `/reset-password` route and improved reset-related setup messaging.
- Added backend tests covering password reset configuration validation.

---

## Previous Updates (Feb 18-Mar 23, 2026)

### Major Features
- **Server-Backed File Search:** Real database search with background auto-indexing to keep the UI snappy without blocking the main event loop. Added LIKE metacharacter escaping to prevent wildcard injections.
- **Resumable Chunked Uploads:** Upload large files reliably by splitting them into chunks that assemble automatically on the server.
- **Folder Management and Drag-and-Drop:** Drag-and-drop support to move files and folders. Added full folder upload, recursive folder logic, and file copying endpoints.
- **UI Enhancements:** Completely redesigned the sky-themed login page with dynamic cloud animations, glassmorphism, and responsive dual layouts. Added toast notifications, keyboard shortcuts, download progress indicators, and dynamic file sorting.
- **Media Streaming:** Replaced monolithic downloads for previews with HTTP Range requests for seamless video, PDF, and high-quality image viewing inline.
- **Two-Factor Authentication (2FA):** Secure accounts using TOTP authenticator apps.
- **Device and Session Management:** Monitor active sessions mapped to device names and IPs, and remotely revoke untrusted logins.
- **Password Reset Flow:** Added password reset and forgot-password flows with frontend reset-route handling and transactional email delivery.

### Security and Infrastructure
- **Network Stack:** Shifted from local Caddy proxy exposure to secure Cloudflare Tunnels (`cloudflared`). Enforced container immutability by pinning image digests.
- **Auth Hardening:** Public signups disabled by default (`ALLOW_REGISTRATION=false`). Enforced valid `SECRET_KEY` at startup.
- **Vulnerability Patches:** Removed JWT tokens from URL queries and replaced them with authenticated blob fetch requests, mitigated path traversal on shared downloads, fixed password-reset poisoning risks, and enforced max file size after chunk assembly.

### Bug Fixes
- Fixed naive versus timezone-aware datetime validation crashes on initial `/api/auth/me` calls for legacy tokens.
- Fixed 0-byte downloaded files by switching to `StreamingResponse` for downloads.
- Fixed event loop blocking during file chunk assembly in FastAPI via `asyncio.to_thread`.
- Remedied edge-case upload calculation bugs for zero-byte files.
- Wired SlowAPI rate limiter state correctly so login throttling now returns proper 429 responses.

---

## Previous: Feb 15-17, 2026
**Commits:** 6 - **Lines Added:** ~900+

---

## Features Shipped

### 1. Backend Authentication and Deployment Infrastructure
> Commit `98e08c1` - Feb 15

- JWT-based auth system with login, registration, and token refresh using bcrypt password hashing
- `OAuth2PasswordBearer` flow with configurable token expiry and a 24-hour default
- Full deployment stack including `docker-compose.yml`, `Dockerfile`s, `nginx.conf` with security headers, and `deploy.sh`
- Async SQLAlchemy database layer with table creation on startup
- `LocalStorage` service for file persistence on disk
- Frontend `AuthPage.jsx` with login and registration flows and token persistence

---

### 2. Admin Panel and Secure File Sharing
> Commit `c71f388` - Feb 16

**Admin Panel**
- `routers/admin.py` for listing users, reading and updating accounts, deleting users, and returning system stats
- `get_admin_user` dependency enforcing admin-only access
- `AdminPanel.jsx` dashboard with user table, quotas, storage indicators, and admin controls
- Schemas including `AdminUserResponse`, `AdminUserUpdate`, and `SystemStats`

**File Sharing**
- `ShareLink` model with unique token, optional bcrypt-protected password, expiry, and download limits
- `routers/sharing.py` for creating links, public link access, downloads, listing a user's links, and revocation
- `ShareModal.jsx` for creating and managing links from the UI
- Added a Share action to the file context menu

**Database Migrations**
- Auto-migration support in `main.py` for adding new columns to existing SQLite tables without data loss

---

### 3. Server-Side Thumbnail Generation
> Commit `ce63d0d` - Feb 16

- `thumbnails.py` using Pillow for JPG, PNG, GIF, BMP, TIFF, and WebP thumbnails
- Resizes images to a 300x300 maximum, converts alpha formats to RGB, and saves optimized JPEG output
- Thumbnails auto-generated on upload and stored in per-user `thumbnails/` directories
- `GET /api/files/{id}/thumbnail` endpoint added
- `FileCard.jsx` updated to display server thumbnails
- Thumbnail cleanup added for file deletion
- Backend Docker image updated with required image-processing dependencies

---

### 4. Real-Time Upload Progress
> Commit `df409c7` - Feb 17

- `uploadFileWithProgress()` in `api.js` using `XMLHttpRequest` and real `upload.onprogress` events
- Rolling 5-sample speed average recalculated every 300ms with ETA computation
- Sequential per-file uploads with individual state tracking from `waiting` to `uploading` to `done` or `error`
- `abort()` support for cancelling uploads
- `UploadProgress.jsx` rewritten with live speed display, an overall progress bar, and per-file status details

---

### 5. Mobile Responsiveness Polish
> Commit `df409c7` - Feb 17

- **768px breakpoint:** Admin stats grid reduced to two columns, admin table wrapped for horizontal scrolling, share modal widened, and upload progress expanded
- **480px breakpoint:** Admin stats switch to a single column, email column hides in the admin table, and upload progress becomes edge-to-edge

---

### 6. Sidebar Scroll Fix
> Commit `cbf50e1` - Feb 16

- Added `overflow-y: auto` to sidebar navigation for long nav lists

---

## Bugs Fixed

### Thumbnail Endpoint Crash (FastAPI)
> Commit `a64e9fa` - Feb 16

**Problem:** The thumbnail endpoint originally depended on authenticated headers, but `<img src="...">` requests in the browser cannot send custom `Authorization` headers. That caused thumbnail requests to fail with 401 responses.

**Fix:** Reworked thumbnail delivery so the frontend can fetch protected content without depending on image tag headers.

---

### Fake Upload Progress
> Fixed in commit `df409c7`

**Problem:** Upload progress was simulated rather than tied to real network activity, so users could not trust the progress bar, speed, or time remaining.

**Fix:** Replaced the fake timer-based progress with real `XMLHttpRequest` upload progress events and derived speed and ETA from actual byte counts.

---

### Sidebar Overflow
> Fixed in commit `cbf50e1`

**Problem:** Long navigation lists in the sidebar could overflow and make items inaccessible.

**Fix:** Added vertical scrolling to the sidebar navigation container.

---

### Admin and Share Components Not Mobile-Friendly
> Fixed in commit `df409c7`

**Problem:** `AdminPanel` and `ShareModal` used fixed-width layouts that broke on phones and tablets.

**Fix:** Added responsive breakpoints, horizontal scrolling where needed, and smaller-screen layout adjustments.

---

## Build Verification

- `vite build` completed successfully during the original implementation cycle with no reported build errors
