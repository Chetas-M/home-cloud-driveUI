# Home Cloud Drive Backend

FastAPI backend for Home Cloud Drive, providing authentication, file storage APIs, search, sharing, activity tracking, and admin operations.

## Features

- JWT authentication with optional TOTP-based 2FA
- Password reset flow delivered through Resend
- Active session tracking with device labels and session revocation
- File upload, download, preview, thumbnail, copy, move, rename, trash, and restore APIs
- File version history with upload, restore, download, and delete operations
- Folder management and server-backed file search
- Authenticated shared-folder collaboration with viewer, editor, and admin roles
- Storage quotas, version-aware usage accounting, activity logs, and admin management endpoints
- Docker-ready deployment with SQLite and local disk storage
- Startup migrations, search-index backfill, automatic trash cleanup, and activity-log retention cleanup

## Quick Start

### Local development

1. Create and activate a virtual environment:

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate # Linux/macOS
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the environment template:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/macOS
```

4. Start the API server:

```bash
uvicorn app.main:app --reload --port 8000
```

5. Open the API at `http://localhost:8000`.

The current app configuration disables `/docs`, `/redoc`, and `/openapi.json`, so use the route tables below or inspect the router modules directly during local development.
The `/health` endpoint is loopback-only, so it works for the Docker health check and local host requests but intentionally returns `404` for non-local clients.

### Docker deployment

From the repository root:

```bash
docker-compose up -d --build
```

## Authentication and account endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/auth/register` | Register a new user when signups are enabled |
| POST | `/api/auth/login` | Login with email and password |
| POST | `/api/auth/login/2fa` | Complete a login challenge with a 6-digit TOTP code |
| GET | `/api/auth/me` | Return the current user profile |
| POST | `/api/auth/logout` | Revoke the current session |
| GET | `/api/auth/sessions` | List active and recent sessions |
| DELETE | `/api/auth/sessions/{session_id}` | Revoke a specific session |
| PATCH | `/api/auth/password` | Change the current user's password |
| POST | `/api/auth/forgot-password` | Email a password reset link |
| POST | `/api/auth/reset-password` | Set a new password from a reset token |
| POST | `/api/auth/2fa/setup` | Generate a pending TOTP secret and otpauth URL |
| POST | `/api/auth/2fa/enable` | Enable 2FA after verifying a TOTP code |
| POST | `/api/auth/2fa/disable` | Disable 2FA after verifying password and TOTP |

## Core API groups

| Area | Routes |
| --- | --- |
| Files | `/api/files`, upload, resumable upload, preview, thumbnail, copy, trash, restore, download |
| Folders | `/api/folders` |
| Storage | `/api/storage`, `/api/storage/activity`, `/api/storage/trash` |
| Public sharing | `/api/share` |
| Shared folders | `/api/shared-folders` |
| Admin | `/api/admin` |

## Resumable upload endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/api/files/upload/init` | Create or resume a chunked upload session |
| POST | `/api/files/upload/{upload_id}/chunk` | Upload one validated chunk to the temporary session directory |
| GET | `/api/files/upload/{upload_id}/status` | Return uploaded chunk indexes and byte counts for resume support |
| POST | `/api/files/upload/complete` | Verify the upload, assemble the final file, and create the database row |

Resumable uploads are staged under `storage/tmp/<user_id>/<upload_id>` until assembly completes.
The backend validates declared chunk sizes, re-checks quota and max-file-size limits at completion, and best-effort removes the temp directory after success.
Abandoned temp directories are not automatically cleaned up yet, so operators should monitor disk usage under `storage/tmp`.

## File version endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/files/{file_id}/versions` | List version history for a file |
| POST | `/api/files/{file_id}/versions` | Upload a new latest version |
| GET | `/api/files/{file_id}/versions/{version_id}/download` | Download a specific historical version |
| POST | `/api/files/{file_id}/versions/{version_id}/restore` | Restore a historical version as a new latest version |
| DELETE | `/api/files/{file_id}/versions/{version_id}` | Delete a historical version that is not current |

Version history is available only for non-folder files. Existing rows created before the feature landed get a base version record automatically the first time version history is requested.

## Public sharing behavior

- Public share links can be created only for non-trashed files; folders are rejected for anonymous link sharing.
- Public access uses `POST /api/share/{token}` to validate the link and optional password before showing metadata.
- Public downloads use `GET /api/share/{token}/download`.
- Password-protected downloads pass the password in the `X-Share-Password` header.
- Trashing a file deactivates active share links that target it, and later access returns `410 Gone`.
- Download limits are enforced atomically so concurrent consumers cannot overrun the remaining quota.

## Shared-folder collaboration

Shared folders are authenticated collaboration grants, separate from anonymous public share links.

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/api/shared-folders` | List folder roots shared with the current user |
| GET | `/api/shared-folders/{folder_id}/access` | List access entries for a shared folder root |
| POST | `/api/shared-folders/{folder_id}/access` | Invite or update a user by username/email with a role |
| PATCH | `/api/shared-folders/{folder_id}/access/{access_id}` | Change a user's shared-folder role |
| DELETE | `/api/shared-folders/{folder_id}/access/{access_id}` | Remove shared-folder access |

Roles are `viewer`, `editor`, and `admin`.
Viewers can read shared content, editors can create and modify files inside the shared tree, and admins can manage access on the shared root.
Owners always retain full access, and public share links can only be created by the file owner.

## Configuration

Environment variables in `backend/.env`:

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | - | JWT signing key; use a long random value |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/homecloud.db` | Database connection string |
| `STORAGE_PATH` | `./storage` | Local storage directory |
| `MAX_STORAGE_BYTES` | `107374182400` | Per-user storage quota in bytes |
| `MAX_FILE_SIZE_BYTES` | `1073741824` | Maximum size allowed for a single file or restored version (`0` disables the limit) |
| `TRASH_AUTO_DELETE_DAYS` | `30` | Permanently delete trashed files older than this many days during startup (`0` disables cleanup) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Login token lifetime |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `30` | Password reset token lifetime |
| `TWO_FACTOR_TEMP_TOKEN_EXPIRE_MINUTES` | `10` | Temporary token lifetime for completing a 2FA login |
| `CORS_ORIGINS` / `CORS_ORIGINS_STR` | `http://localhost:5173,http://localhost:3000,http://localhost` | Comma-separated allowed frontend origins |
| `ALLOW_REGISTRATION` | `false` | Enable or disable public signups |
| `SESSION_LAST_SEEN_UPDATE_INTERVAL_SECONDS` | `60` | Minimum interval between `last_seen_at` writes for a session |
| `TRUST_PROXY_HEADERS` | `false` | Use forwarded proxy headers when resolving client IP addresses |
| `RESEND_API_KEY` | - | Resend API key for transactional email |
| `RESEND_FROM_EMAIL` | - | Sender email used for account emails |
| `RESEND_FROM_NAME` | `Home Cloud` | Sender display name |
| `RESEND_API_URL` | `https://api.resend.com/emails` | Resend send-email endpoint |
| `RESEND_TIMEOUT_SECONDS` | `15` | Timeout for Resend requests |
| `PASSWORD_RESET_URL` | - | Preferred frontend reset page, such as `https://cloud.example.com/reset-password` |

Password reset email delivery is enabled only when both `RESEND_API_KEY` and `RESEND_FROM_EMAIL` are set.
The same email configuration is also used for new-login alert emails after successful session creation.
If `PASSWORD_RESET_URL` is blank, the backend tries to build a reset link from a trusted request origin or the first configured CORS origin.
`SECRET_KEY` is required and validated at startup; placeholder values and keys shorter than 32 characters are rejected before the app finishes booting.

## Password reset behavior

- `forgot-password` always returns a generic success message when the email exists, avoiding user enumeration.
- Reset links include a `reset_token` query parameter and are meant for the frontend `/reset-password` route.
- Reset tokens are invalidated when the password changes because they are tied to the user's current password fingerprint.
- Misconfigured email delivery returns a clear 503 error describing the missing Resend setting.
- When email delivery is configured, successful logins also queue a login alert email with the detected device label and resolved client IP.

## Storage and lifecycle behavior

- Each uploaded file creates an initial `v1` record in `file_versions`.
- Uploading or restoring a version creates a new latest version instead of mutating the old one.
- The storage API adds a `versions` breakdown bucket for archived versions so quota usage reflects historical copies.
- Startup runs lightweight schema migrations, background search-index backfill, and trash cleanup for items older than `TRASH_AUTO_DELETE_DAYS`.
- Activity logs older than 300 days are removed by a daily in-process cleanup task.
- On Linux, the search-index backfill uses a non-blocking file lock so only one worker performs the startup backfill at a time. On Windows, the backfill still runs but without that multi-worker file lock.

## Project structure

```text
backend/
|-- app/
|   |-- main.py                # FastAPI app entry and startup tasks
|   |-- config.py              # Settings and environment loading
|   |-- database.py            # Async database engine/session setup
|   |-- email_service.py       # Resend email delivery helpers
|   |-- shared_access.py       # Shared-folder access resolution
|   |-- models.py              # SQLAlchemy models
|   |-- schemas.py             # Pydantic request/response schemas
|   |-- auth.py                # Auth, JWT, password reset, and 2FA helpers
|   `-- routers/               # API route modules
|-- test_password_reset_config.py
|-- requirements.txt
|-- Dockerfile
`-- .env.example
```

## Notes

- The backend uses background tasks plus thread offloading for blocking email sends.
- Root deployment settings in [`../docker-compose.yml`](../docker-compose.yml) must also include the password reset, email, and storage-limit variables when running in containers.
- Docker Compose keeps the API private by default: the frontend is published on port `3001`, while the backend stays on the internal network and is checked through `http://localhost:8000/health` from inside the container.
