# Home Cloud Drive - Backend

A FastAPI backend for the Home Cloud Drive personal cloud storage application.

## Features

- 🔐 **JWT Authentication** - Secure token-based authentication
- 📁 **File Management** - Upload, download, rename, move, delete files
- 📂 **Folder Operations** - Create and organize folders
- ⭐ **Favorites** - Star important files
- 🗑️ **Trash System** - Soft delete with restore capability
- 📊 **Storage Tracking** - Real-time usage statistics
- 📝 **Activity Log** - Track all file operations
- 🐳 **Docker Ready** - Easy deployment with Docker

## Quick Start

### Local Development

1. **Create virtual environment:**
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Copy environment file:**
```bash
copy .env.example .env  # Windows
cp .env.example .env    # Linux/Mac
```

4. **Run the server:**
```bash
uvicorn app.main:app --reload --port 8000
```

5. **Open API docs:** http://localhost:8000/docs

### Docker Deployment

```bash
# From project root
docker-compose up -d --build
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login (get JWT token) |
| POST | `/api/auth/forgot-password` | Send password reset link |
| POST | `/api/auth/reset-password` | Reset password from reset link |
| GET | `/api/auth/me` | Get current user info |

### Files
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/files` | List files |
| POST | `/api/files/upload` | Upload files |
| GET | `/api/files/{id}/download` | Download file |
| PATCH | `/api/files/{id}` | Update (rename/move/star) |
| POST | `/api/files/{id}/trash` | Move to trash |
| POST | `/api/files/{id}/restore` | Restore from trash |
| DELETE | `/api/files/{id}` | Permanently delete |

### Folders
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/folders` | Create folder |
| DELETE | `/api/folders/{id}` | Delete folder |

### Storage
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/storage` | Get storage stats |
| GET | `/api/storage/activity` | Get activity log |
| DELETE | `/api/storage/trash` | Empty trash |

## Configuration

Environment variables (in `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | - | JWT secret key |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/homecloud.db` | Database URL |
| `STORAGE_PATH` | `./storage` | File storage directory |
| `MAX_STORAGE_BYTES` | `107374182400` (100GB) | Max storage per user |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24h) | Token expiration |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `30` | Password reset link expiration |
| `RESEND_API_KEY` | - | Resend API key used for transactional email |
| `RESEND_FROM_EMAIL` | - | Sender address for password reset emails |
| `RESEND_FROM_NAME` | `Home Cloud` | Sender display name |
| `RESEND_API_URL` | `https://api.resend.com/emails` | Resend send-email endpoint |
| `RESEND_TIMEOUT_SECONDS` | `15` | Resend API timeout in seconds |
| `PASSWORD_RESET_URL` | - | Optional frontend URL used in reset emails |

## Project Structure

```
backend/
├── app/
│   ├── main.py          # FastAPI app entry
│   ├── config.py        # Settings
│   ├── database.py      # Database connection
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic schemas
│   ├── auth.py          # Auth utilities
│   └── routers/
│       ├── auth.py      # Auth endpoints
│       ├── files.py     # File endpoints
│       ├── folders.py   # Folder endpoints
│       └── storage.py   # Storage endpoints
├── requirements.txt
├── Dockerfile
└── .env.example
```

## License

MIT
