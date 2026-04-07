# Home Cloud Drive Backend

FastAPI backend for Home Cloud Drive, providing authentication, file storage APIs, search, sharing, activity tracking, and admin operations.

## Features

- JWT authentication with optional TOTP-based 2FA
- Password reset flow delivered through Resend
- Active session tracking with device labels and session revocation
- File upload, download, preview, thumbnail, copy, move, rename, trash, and restore APIs
- Folder management and server-backed file search
- Storage quotas, activity logs, and admin management endpoints
- Docker-ready deployment with SQLite and local disk storage

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

5. Open interactive API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

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
| Files | `/api/files`, upload, preview, thumbnail, copy, trash, restore, download |
| Folders | `/api/folders` |
| Storage | `/api/storage`, `/api/storage/activity`, `/api/storage/trash` |
| Sharing | `/api/share` |
| Admin | `/api/admin` |

## Configuration

Environment variables in `backend/.env`:

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | - | JWT signing key; use a long random value |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/homecloud.db` | Database connection string |
| `STORAGE_PATH` | `./storage` | Local storage directory |
| `MAX_STORAGE_BYTES` | `107374182400` | Per-user storage quota in bytes |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Login token lifetime |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `30` | Password reset token lifetime |
| `ALLOW_REGISTRATION` | `false` | Enable or disable public signups |
| `RESEND_API_KEY` | - | Resend API key for transactional email |
| `RESEND_FROM_EMAIL` | - | Sender email used for account emails |
| `RESEND_FROM_NAME` | `Home Cloud` | Sender display name |
| `RESEND_API_URL` | `https://api.resend.com/emails` | Resend send-email endpoint |
| `RESEND_TIMEOUT_SECONDS` | `15` | Timeout for Resend requests |
| `PASSWORD_RESET_URL` | - | Preferred frontend reset page, such as `https://cloud.example.com/reset-password` |

Password reset email delivery is enabled only when both `RESEND_API_KEY` and `RESEND_FROM_EMAIL` are set.
If `PASSWORD_RESET_URL` is blank, the backend tries to build a reset link from a trusted request origin or the first configured CORS origin.

## Password reset behavior

- `forgot-password` always returns a generic success message when the email exists, avoiding user enumeration.
- Reset links include a `reset_token` query parameter and are meant for the frontend `/reset-password` route.
- Reset tokens are invalidated when the password changes because they are tied to the user's current password fingerprint.
- Misconfigured email delivery returns a clear 503 error describing the missing Resend setting.

## Project structure

```text
backend/
|-- app/
|   |-- main.py                # FastAPI app entry and startup tasks
|   |-- config.py              # Settings and environment loading
|   |-- database.py            # Async database engine/session setup
|   |-- email_service.py       # Resend email delivery helpers
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
- Root deployment settings in [`../docker-compose.yml`](../docker-compose.yml) must also include the password reset and Resend variables when running in containers.
